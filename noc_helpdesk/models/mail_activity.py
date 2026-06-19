from datetime import timedelta

from odoo import api, fields, models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    date_deadline = fields.Date(
        string="Data Limite",
        required=True,
        index=True,
        default=fields.Date.today,
    )

    date_start = fields.Datetime(
        string="Data de Início",
        index=True,
    )

    @api.model
    def cron_notify_activity_start(self):
        now = fields.Datetime.now()
        window_start = now - timedelta(minutes=1)
        activities = self.sudo().search(
            [("date_start", ">=", window_start), ("date_start", "<=", now)]
        )
        if not activities:
            return

        bus = self.env["bus.bus"].sudo()
        for activity in activities:
            user = activity.user_id
            if not user or not user.partner_id:
                continue
            bus._sendone(
                user.partner_id,
                "noc_helpdesk/activity_start_alert",
                {
                    "activity_id": activity.id,
                    "activity_summary": activity.summary
                    or activity.activity_type_id.name
                    or "Atividade",
                    "res_model": activity.res_model,
                    "res_id": activity.res_id,
                    "res_name": activity.res_name or "",
                },
            )
