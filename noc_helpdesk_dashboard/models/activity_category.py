from odoo import fields, models


class NOCActivityCategory(models.Model):
    _name = "noc.activity.category"
    _description = "Activity Category"
    _order = "sequence, id"

    name = fields.Char(string="Activity", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    capacidade_mensal = fields.Integer(string="Monthly Capacity", default=0)
    tag_ids = fields.Many2many(
        comodel_name="helpdesk.ticket.tag",
        relation="noc_activity_cat_tag_rel",
        column1="categoria_id",
        column2="tag_id",
        string="Event Types",
    )
    tipo_contagem = fields.Selection(
        selection=[
            ("ticket_count", "Ticket Count"),
            ("plantao_count", "Shift Handover Count"),
        ],
        string="Count Type",
        required=True,
        default="ticket_count",
    )
    active = fields.Boolean(default=True)