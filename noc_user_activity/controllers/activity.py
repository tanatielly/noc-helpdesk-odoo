import logging

import odoo.http as http
from odoo import fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class UserActivityController(http.Controller):
    @http.route(
        "/noc_user_activity/heartbeat",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def heartbeat(self, **kwargs):
        request.env.user.sudo().write({"last_activity": fields.Datetime.now()})
        return {"status": "ok"}


class UserActivitySession(http.Controller):
    @http.route("/web/session/logout", type="http", auth="none")
    def logout(self, redirect="/web"):
        uid = request.session.uid
        sid = request.session.sid
        if uid and sid:
            try:
                log = (
                    request.env["res.users.session.log"]
                    .sudo()
                    .search(
                        [("session_sid", "=", sid), ("logout_date", "=", False)],
                        limit=1,
                    )
                )
                if log:
                    log.write(
                        {
                            "logout_date": fields.Datetime.now(),
                            "logout_type": "manual",
                        }
                    )
            except Exception:
                _logger.warning(
                    "Falha ao registrar logout manual para uid %s", uid, exc_info=True
                )
        request.session.logout(keep_db=True)
        return request.redirect(redirect, 303)

    @http.route("/web/session/destroy", type="json", auth="user")
    def destroy(self):
        uid = request.session.uid
        sid = request.session.sid
        if uid and sid:
            try:
                log = (
                    request.env["res.users.session.log"]
                    .sudo()
                    .search(
                        [("session_sid", "=", sid), ("logout_date", "=", False)],
                        limit=1,
                    )
                )
                if log:
                    log.write(
                        {
                            "logout_date": fields.Datetime.now(),
                            "logout_type": "manual",
                        }
                    )
            except Exception:
                _logger.warning(
                    "Falha ao registrar logout manual para uid %s", uid, exc_info=True
                )
        request.session.logout()
