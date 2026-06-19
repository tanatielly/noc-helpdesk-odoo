from odoo import fields, models


class HelpdeskPlantao(models.Model):
    _name = "helpdesk.plantao"
    _description = "Plantão de Atendimento"
    _order = "start_datetime desc"

    user_id = fields.Many2one("res.users", string="Responsável", required=True)
    start_datetime = fields.Datetime(
        string="Início", required=True, default=fields.Datetime.now
    )
