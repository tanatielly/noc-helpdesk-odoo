from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    noc_user_activity_inactivity_timeout_minutes = fields.Integer(
        string="Timeout de Inatividade (min)",
        default=30,
        config_parameter="noc_user_activity.inactivity_timeout_minutes",
        help=(
            "Minutos sem atividade após os quais a sessão é encerrada automaticamente. "
            "Padrão: 30."
        ),
    )
    noc_user_activity_warning_before_logout_minutes = fields.Integer(
        string="Aviso antes do Logout (min)",
        default=2,
        config_parameter="noc_user_activity.warning_before_logout_minutes",
        help=(
            "Minutos de antecedência com que o aviso de logout é exibido ao usuário. "
            "Padrão: 2."
        ),
    )
