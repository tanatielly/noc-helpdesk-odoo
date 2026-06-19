import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    last_activity = fields.Datetime(
        string="Última Atividade",
        readonly=True,
        index=True,
        copy=False,
    )
    session_log_ids = fields.One2many(
        comodel_name="res.users.session.log",
        inverse_name="user_id",
        string="Histórico de Sessões",
    )
    session_log_count = fields.Integer(
        string="Sessões",
        compute="_compute_session_log_count",
    )

    def _compute_session_log_count(self):
        for user in self:
            user.session_log_count = self.env["res.users.session.log"].search_count(
                [("user_id", "=", user.id)]
            )
