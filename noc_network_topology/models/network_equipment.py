import logging
import time

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

_NOMINATIM_URL_DEFAULT = "https://nominatim.openstreetmap.org/search"


class NetworkEquipment(models.Model):
    _inherit = "network.equipment"

    latitude = fields.Float(digits=(10, 7), tracking=True)
    longitude = fields.Float(digits=(10, 7), tracking=True)
    geo_coords_display = fields.Char(
        string="Coordenadas",
        compute="_compute_geo_coords_display",
    )

    topology_node_id = fields.Integer(
        compute="_compute_topology_node_id",
        string="Topology",
    )

    def _compute_topology_node_id(self):
        for rec in self:
            rec.topology_node_id = rec.id

    def _compute_geo_coords_display(self):
        for rec in self:
            if rec.latitude or rec.longitude:
                rec.geo_coords_display = f"{rec.latitude:.7f}, {rec.longitude:.7f}"
            else:
                rec.geo_coords_display = "Sem coordenadas"

    # ------------------------------------------------------------------
    # Geocodificação via Nominatim (OpenStreetMap)
    # ------------------------------------------------------------------

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

    def _geocode(self, location):
        """Retorna (lat, lng) ou (None, None).

        Tenta consultas progressivamente mais simples:
        endereço completo → últimas partes → último token.
        """
        if not location:
            return None, None

        url, headers, country_codes, timeout, _rate_delay = self._get_geocoding_config()

        parts = [p.strip() for p in location.split(",") if p.strip()]
        attempts = [location]
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
                    _logger.info("Geocoded %r using query %r", location, query)
                    return float(data[0]["lat"]), float(data[0]["lon"])
            except Exception as exc:
                _logger.warning("Geocoding attempt failed for %r: %s", query, exc)

        _logger.warning("No geocoding result for %r", location)
        return None, None

    # ------------------------------------------------------------------
    # Hooks de create/write: geocodifica automaticamente ao salvar
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("location")
                and not vals.get("latitude")
                and not vals.get("longitude")
            ):
                lat, lng = self._geocode(vals["location"])
                if lat is not None:
                    vals["latitude"] = lat
                    vals["longitude"] = lng
        return super().create(vals_list)

    def write(self, vals):
        if "location" in vals and vals.get("location"):
            if not vals.get("latitude") and not vals.get("longitude"):
                lat, lng = self._geocode(vals["location"])
                if lat is not None:
                    vals["latitude"] = lat
                    vals["longitude"] = lng
        return super().write(vals)

    # ------------------------------------------------------------------
    # Ações de geocodificação manual
    # ------------------------------------------------------------------

    def action_geocode(self):
        """Re-geocodifica este equipamento e mostra notificação."""
        success, failed = 0, 0
        for rec in self:
            lat, lng = self._geocode(rec.location)
            if lat is not None:
                super(NetworkEquipment, rec).write({"latitude": lat, "longitude": lng})
                success += 1
            else:
                failed += 1

        if failed and not success:
            msg = _(
                "Não foi possível geocodificar o endereço."
                " Verifique a conexão com a internet"
                " ou o formato do endereço."
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
            msg = _(
                "%(count)d equipamento(s) geocodificado(s) com sucesso.",
                count=success,
            )
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

    def action_geocode_all(self):
        """Geocodifica todos os equipamentos sem coordenadas (1 req/s)."""
        records = self.search(
            [
                ("location", "!=", False),
                ("latitude", "=", 0.0),
                ("longitude", "=", 0.0),
            ]
        )
        _url, _headers, _cc, _timeout, rate_delay = self._get_geocoding_config()
        success, failed = 0, 0
        for i, rec in enumerate(records):
            if i > 0:
                time.sleep(rate_delay)
            lat, lng = self._geocode(rec.location)
            if lat is not None:
                super(NetworkEquipment, rec).write({"latitude": lat, "longitude": lng})
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
