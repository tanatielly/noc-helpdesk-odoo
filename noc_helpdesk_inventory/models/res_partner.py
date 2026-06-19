from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    circuit_ids = fields.One2many(
        comodel_name="network.circuit",
        inverse_name="provider_id",
        string="Circuitos",
    )
