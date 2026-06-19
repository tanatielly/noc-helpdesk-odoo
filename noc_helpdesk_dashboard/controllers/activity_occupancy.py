import calendar
import logging
from datetime import datetime

import pytz

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class NOCActivityOccupancyController(http.Controller):
    @http.route(
        "/network_helpdesk_dashboard/ocupacao_report",
        type="json",
        auth="user",
    )
    def ocupacao_report(self, mes=None, ano=None, **kwargs):
        try:
            return self._compute_ocupacao(mes=mes, ano=ano)
        except Exception as e:
            _logger.exception("Erro no relatório de ocupação: %s", e)
            return {"error": str(e)}

    def _user_tz(self):
        return pytz.timezone(request.env.user.tz or "UTC")

    def _month_range_utc(self, mes, ano):
        user_tz = self._user_tz()
        dt_from_local = user_tz.localize(datetime(ano, mes, 1, 0, 0, 0))
        last_day = calendar.monthrange(ano, mes)[1]
        dt_to_local = user_tz.localize(datetime(ano, mes, last_day, 23, 59, 59))
        dt_from_utc = dt_from_local.astimezone(pytz.utc).replace(tzinfo=None)
        dt_to_utc = dt_to_local.astimezone(pytz.utc).replace(tzinfo=None)
        return (
            dt_from_utc.strftime("%Y-%m-%d %H:%M:%S"),
            dt_to_utc.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _compute_ocupacao(self, mes=None, ano=None):
        today = datetime.now(self._user_tz())
        mes = int(mes) if mes else today.month
        ano = int(ano) if ano else today.year

        date_from_utc, date_to_utc = self._month_range_utc(mes, ano)

        Categoria = request.env["noc.activity.category"].sudo()
        Ticket = request.env["helpdesk.ticket"]

        categorias = Categoria.search([("active", "=", True)])
        rows = []
        for cat in categorias:
            if cat.tipo_contagem == "plantao_count":
                # 2 turnos de 12h por dia × dias do mês
                quantidade = calendar.monthrange(ano, mes)[1] * 2
            else:
                if not cat.tag_ids:
                    quantidade = 0
                else:
                    quantidade = Ticket.search_count(
                        [
                            ("create_date", ">=", date_from_utc),
                            ("create_date", "<=", date_to_utc),
                            ("tag_id", "in", cat.tag_ids.ids),
                        ]
                    )

            rows.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "sequence": cat.sequence,
                    "quantidade": quantidade,
                    "capacidade_mensal": cat.capacidade_mensal,
                }
            )

        return {"mes": mes, "ano": ano, "rows": rows}

    @http.route(
        "/network_helpdesk_dashboard/ocupacao_annual",
        type="json",
        auth="user",
    )
    def ocupacao_annual(self, ano=None, **kwargs):
        try:
            return self._compute_ocupacao_annual(ano=ano)
        except Exception as e:
            _logger.exception("Erro no relatório anual de ocupação: %s", e)
            return {"error": str(e)}

    def _compute_ocupacao_annual(self, ano=None):
        today = datetime.now(self._user_tz())
        ano = int(ano) if ano else today.year

        Categoria = request.env["noc.activity.category"].sudo()
        Ticket = request.env["helpdesk.ticket"]
        categorias = Categoria.search([("active", "=", True)])

        rows = []
        for cat in categorias:
            meses = []
            for mes in range(1, 13):
                date_from_utc, date_to_utc = self._month_range_utc(mes, ano)
                if cat.tipo_contagem == "plantao_count":
                    quantidade = calendar.monthrange(ano, mes)[1] * 2
                else:
                    if not cat.tag_ids:
                        quantidade = 0
                    else:
                        quantidade = Ticket.search_count(
                            [
                                ("create_date", ">=", date_from_utc),
                                ("create_date", "<=", date_to_utc),
                                ("tag_id", "in", cat.tag_ids.ids),
                            ]
                        )
                meses.append(quantidade)
            rows.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "sequence": cat.sequence,
                    "capacidade_mensal": cat.capacidade_mensal,
                    "meses": meses,
                }
            )

        return {"ano": ano, "rows": rows}
