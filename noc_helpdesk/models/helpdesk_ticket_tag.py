from odoo import fields, models


class HelpdeskTicketTag(models.Model):
    _inherit = "helpdesk.ticket.tag"
    _order = "priority asc, name asc"

    priority = fields.Integer(
        string="Prioridade", default=9999, help="Menor número = maior prioridade"
    )
    alert_limit_minutes = fields.Integer(
        string="Limite de Inatividade (min)",
        default=0,
        help="Minutos sem atualização antes de disparar alerta. 0 = sem alerta.",
    )

    def _name_search(
        self, name="", args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        return super()._name_search(
            name=name,
            args=args,
            operator=operator,
            limit=None,
            name_get_uid=name_get_uid,
        )
