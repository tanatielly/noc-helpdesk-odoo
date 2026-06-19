from odoo import fields, models


class NetworkCircuitType(models.Model):
    _name = "network.circuit.type"
    _description = "Tipo de Circuito"
    _order = "name asc"

    name = fields.Char(string="Nome", required=True, translate=True)
    active = fields.Boolean(default=True)
