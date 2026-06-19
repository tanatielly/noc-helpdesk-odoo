from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    circuit_api_token = fields.Char(
        string="Token da API de Circuitos",
        config_parameter="noc_helpdesk_inventory.circuit_api_token",
        help="Token que sistemas externos devem enviar em "
        "Authorization: Bearer <token> para consultar chamados por circuito.",
    )
