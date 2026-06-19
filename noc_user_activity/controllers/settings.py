import odoo.http as http
from odoo.http import request


class UserActivitySettings(http.Controller):
    @http.route(
        "/noc_user_activity/get_settings",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def get_settings(self):
        ICP = request.env["ir.config_parameter"].sudo()
        timeout = int(
            ICP.get_param("noc_user_activity.inactivity_timeout_minutes", 30)
        )
        warning = int(
            ICP.get_param("noc_user_activity.warning_before_logout_minutes", 2)
        )
        return {"timeout_minutes": timeout, "warning_minutes": warning}
