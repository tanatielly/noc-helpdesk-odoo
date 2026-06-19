import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CircuitApiController(http.Controller):
    def _check_token(self):
        token = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("noc_helpdesk_inventory.circuit_api_token")
        )
        if not token:
            return False
        auth_header = request.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        return auth_header[len("Bearer ") :] == token

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False)
        headers = [("Content-Type", "application/json; charset=utf-8")]
        return request.make_response(body, headers=headers, status=status)

    def _ticket_link(self, ticket_id):
        base_url = (
            request.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        )
        return f"{base_url}/web#model=helpdesk.ticket&id={ticket_id}&view_type=form"

    @http.route(
        "/api/v1/circuitos/<path:designacao>/chamado-aberto",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def chamado_aberto(self, designacao, **kwargs):
        if not self._check_token():
            return self._json_response({"error": "unauthorized"}, status=401)

        circuit = (
            request.env["network.circuit"]
            .sudo()
            .search([("link_designation", "=", designacao)], limit=1)
        )
        if not circuit:
            return self._json_response(
                {"error": "circuito não encontrado", "designacao": designacao},
                status=404,
            )

        open_tickets = (
            request.env["helpdesk.ticket"]
            .sudo()
            .search([("circuit_id", "=", circuit.id), ("closed", "=", False)])
        )

        return self._json_response(
            {
                "designacao": designacao,
                "chamado_aberto": bool(open_tickets),
                "chamados": [
                    {
                        "id": t.id,
                        "nome": t.name,
                        "estagio": t.stage_id.name if t.stage_id else None,
                        "criado_em": (
                            t.create_date.isoformat() if t.create_date else None
                        ),
                        "numero_externo": t.external_ticket_number or None,
                        "link": self._ticket_link(t.id),
                    }
                    for t in open_tickets
                ],
            }
        )

    @http.route(
        "/api/v1/chamados/abertos",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def chamados_abertos(self, **kwargs):
        if not self._check_token():
            return self._json_response({"error": "unauthorized"}, status=401)

        open_tickets = (
            request.env["helpdesk.ticket"]
            .sudo()
            .search([("closed", "=", False), ("circuit_id", "!=", False)])
        )

        return self._json_response(
            {
                "chamados": [
                    {
                        "designacao": t.circuit_id.link_designation,
                        "link": self._ticket_link(t.id),
                    }
                    for t in open_tickets
                ],
            }
        )
