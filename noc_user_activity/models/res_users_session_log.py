from datetime import timedelta

from odoo import api, fields, models


class ResUsersSessionLog(models.Model):
    _name = "res.users.session.log"
    _description = "Log de Sessão de Usuário"
    _order = "login_date desc"

    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Usuário",
        required=True,
        ondelete="cascade",
        index=True,
    )
    login_date = fields.Datetime(
        string="Login",
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    logout_date = fields.Datetime(string="Logout", readonly=True)
    logout_type = fields.Selection(
        selection=[
            ("active", "Ativa"),
            ("manual", "Manual"),
            ("timeout", "Timeout"),
            ("unknown", "Desconhecido"),
        ],
        string="Tipo de Logout",
        default="active",
        readonly=True,
    )
    ip_address = fields.Char(string="Endereço IP", readonly=True)
    session_sid = fields.Char(string="Session SID", index=True, readonly=True)
    duration_minutes = fields.Float(
        string="Duração (min)",
        compute="_compute_duration",
        store=True,
    )

    @api.depends("login_date", "logout_date")
    def _compute_duration(self):
        for rec in self:
            if rec.login_date and rec.logout_date:
                delta = rec.logout_date - rec.login_date
                rec.duration_minutes = delta.total_seconds() / 60
            else:
                rec.duration_minutes = 0.0

    @api.model
    def cron_mark_timed_out_sessions(self):
        timeout = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("noc_user_activity.inactivity_timeout_minutes", 30)
        )
        cutoff = fields.Datetime.now() - timedelta(minutes=timeout)
        open_logs = self.sudo().search(
            [("logout_date", "=", False), ("login_date", "<", cutoff)]
        )
        for log in open_logs:
            user = log.user_id
            if not user.last_activity or user.last_activity < cutoff:
                log.write(
                    {
                        "logout_date": fields.Datetime.now(),
                        "logout_type": "timeout",
                    }
                )
