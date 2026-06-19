import logging
import time

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

_NOMINATIM_URL_DEFAULT = "https://nominatim.openstreetmap.org/search"


class NetworkSite(models.Model):
    _inherit = "network.site"

    geo_coords_display = fields.Char(
        string="Coordenadas",
        compute="_compute_geo_coords_display",
    )

    def _compute_geo_coords_display(self):
        for rec in self:
            if rec.latitude or rec.longitude:
                rec.geo_coords_display = f"{rec.latitude:.7f}, {rec.longitude:.7f}"
            else:
                rec.geo_coords_display = "Sem coordenadas"

    def _get_geocoding_config(self):
        """Retorna as configurações de geocodificação lidas de ir.config_parameter."""
        ICP = self.env["ir.config_parameter"].sudo()
        url = ICP.get_param(
            "noc_network_topology.nominatim_url", _NOMINATIM_URL_DEFAULT
        )
        email = ICP.get_param("noc_network_topology.contact_email", "")
        country_codes = ICP.get_param("noc_network_topology.country_codes", "")
        timeout = int(ICP.get_param("noc_network_topology.geocoding_timeout", 8))
        rate_delay = float(
            ICP.get_param("noc_network_topology.geocoding_rate_delay", 1.1)
        )
        user_agent = (
            f"noc-helpdesk-odoo/1.0 ({email})" if email else "noc-helpdesk-odoo/1.0"
        )
        return url, {"User-Agent": user_agent}, country_codes, timeout, rate_delay

    def _geocode(self, address):
        """Retorna (lat, lng) ou (None, None) via Nominatim."""
        if not address:
            return None, None

        url, headers, country_codes, timeout, _rate_delay = self._get_geocoding_config()

        parts = [p.strip() for p in address.split(",") if p.strip()]
        attempts = [address]
        if len(parts) >= 2:
            attempts.append(", ".join(parts[-2:]))
        if parts:
            attempts.append(parts[-1])

        params = {"q": None, "format": "json", "limit": 1}
        if country_codes:
            params["countrycodes"] = country_codes

        for query in attempts:
            try:
                params["q"] = query
                resp = requests.get(
                    url, params=params, headers=headers, timeout=timeout
                )
                resp.raise_for_status()
                data = resp.json()
                if data:
                    _logger.info("Site geocodificado %r via query %r", address, query)
                    return float(data[0]["lat"]), float(data[0]["lon"])
            except Exception as exc:
                _logger.warning("Geocoding falhou para %r: %s", query, exc)

        _logger.warning("Sem resultado de geocoding para site %r", address)
        return None, None

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("address")
                and not vals.get("latitude")
                and not vals.get("longitude")
            ):
                lat, lng = self._geocode(vals["address"])
                if lat is not None:
                    vals["latitude"] = lat
                    vals["longitude"] = lng
        return super().create(vals_list)

    def write(self, vals):
        if "address" in vals and vals.get("address"):
            if not vals.get("latitude") and not vals.get("longitude"):
                lat, lng = self._geocode(vals["address"])
                if lat is not None:
                    vals["latitude"] = lat
                    vals["longitude"] = lng
        return super().write(vals)

    def action_geocode(self):
        """Re-geocodifica este site e exibe notificação."""
        success, failed = 0, 0
        for rec in self:
            lat, lng = self._geocode(rec.address)
            if lat is not None:
                super(NetworkSite, rec).write({"latitude": lat, "longitude": lng})
                success += 1
            else:
                failed += 1

        if failed and not success:
            msg = _(
                "Não foi possível geocodificar o endereço."
                " Verifique a conexão ou o formato do endereço."
            )
            notif_type = "warning"
        elif failed:
            msg = _(
                "%(success)d geocodificado(s), %(failed)d falhou(ram).",
                success=success,
                failed=failed,
            )
            notif_type = "warning"
        else:
            msg = _("%(count)d site(s) geocodificado(s) com sucesso.", count=success)
            notif_type = "success"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Geocodificação"),
                "message": msg,
                "type": notif_type,
                "sticky": False,
            },
        }

    def action_geocode_all_sites(self):
        """Geocodifica todos os sites sem coordenadas (1 req/s)."""
        records = self.search(
            [
                ("address", "!=", False),
                ("latitude", "=", 0.0),
                ("longitude", "=", 0.0),
            ]
        )
        _url, _headers, _cc, _timeout, rate_delay = self._get_geocoding_config()
        success, failed = 0, 0
        for i, rec in enumerate(records):
            if i > 0:
                time.sleep(rate_delay)
            lat, lng = self._geocode(rec.address)
            if lat is not None:
                super(NetworkSite, rec).write({"latitude": lat, "longitude": lng})
                success += 1
            else:
                failed += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Geocodificação em lote"),
                "message": _(
                    "%(success)d geocodificado(s), %(failed)d falhou(ram).",
                    success=success,
                    failed=failed,
                ),
                "type": "success" if not failed else "warning",
                "sticky": True,
            },
        }
