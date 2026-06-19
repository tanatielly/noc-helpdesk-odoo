import logging
from datetime import timedelta

import odoo.http as http
from odoo import fields, models
from odoo.http import request

_logger = logging.getLogger(__name__)

_TIMEOUT_MINUTES_DEFAULT = 30


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _authenticate(cls, endpoint):
        super()._authenticate(endpoint)
        if not request or not request.session.uid:
            return
        uid = request.session.uid

        if not request.session.get("_session_log_created"):
            cls._ensure_session_log(request.env, uid)
            request.session["_session_log_created"] = True

        user = request.env["res.users"].sudo().browse(uid)
        if not user.exists() or not user.last_activity:
            return
        timeout = int(
            request.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "noc_user_activity.inactivity_timeout_minutes",
                _TIMEOUT_MINUTES_DEFAULT,
            )
        )
        cutoff = fields.Datetime.now() - timedelta(minutes=timeout)
        if user.last_activity < cutoff:
            cls._mark_session_timeout(request.env, uid)
            raise http.SessionExpiredException("Sessão expirada por inatividade")

    @classmethod
    def _ensure_session_log(cls, env, uid):
        """Cria log para sessões restauradas via cookie (não passam por _login)."""
        sid = request.session.sid if request else None
        if not sid:
            return
        existing = (
            env["res.users.session.log"]
            .sudo()
            .search(
                [("session_sid", "=", sid), ("logout_date", "=", False)],
                limit=1,
            )
        )
        if existing:
            return
        ip = request.httprequest.environ.get("REMOTE_ADDR", "n/a") if request else "n/a"
        try:
            # Fechar sessões abertas anteriores sem SID conhecido (
            # browser fechado, etc.)
            stale = (
                env["res.users.session.log"]
                .sudo()
                .search(
                    [
                        ("user_id", "=", uid),
                        ("logout_date", "=", False),
                        ("session_sid", "!=", sid),
                    ]
                )
            )
            if stale:
                stale.write(
                    {"logout_date": fields.Datetime.now(), "logout_type": "unknown"}
                )
            env["res.users.session.log"].sudo().create(
                {"user_id": uid, "ip_address": ip, "session_sid": sid}
            )
            env.cr.execute(
                "UPDATE res_users SET last_activity = NULL WHERE id = %s", (uid,)
            )
        except Exception:
            _logger.warning(
                "Falha ao criar log de sessão recuperada para uid %s",
                uid,
                exc_info=True,
            )

    @classmethod
    def _mark_session_timeout(cls, env, uid):
        try:
            log = (
                env["res.users.session.log"]
                .sudo()
                .search(
                    [("user_id", "=", uid), ("logout_date", "=", False)],
                    order="login_date desc",
                    limit=1,
                )
            )
            if log:
                log.write(
                    {
                        "logout_date": fields.Datetime.now(),
                        "logout_type": "timeout",
                    }
                )
        except Exception:
            _logger.warning(
                "Falha ao registrar timeout de sessão para uid %s", uid, exc_info=True
            )
