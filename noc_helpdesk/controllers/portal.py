import odoo.http as http
from odoo.http import request

from odoo.addons.helpdesk_mgmt.controllers.main import HelpdeskTicketController


class NOCHelpdeskPortalController(HelpdeskTicketController):
    @http.route("/new/ticket", type="http", auth="user", website=True)
    def create_new_ticket(self, **kw):
        session_info = http.request.env["ir.http"].session_info()
        email = http.request.env.user.email
        name = http.request.env.user.name

        def _cat_id(xml_id):
            rec = request.env.ref(f"noc_helpdesk.{xml_id}", raise_if_not_found=False)
            return rec.id if rec else 0

        return http.request.render(
            "noc_helpdesk.portal_create_ticket",
            {
                "email": email,
                "name": name,
                "cat_network_config": _cat_id(
                    "helpdesk_ticket_category_network_config"
                ),
                "cat_cpe_livre": _cat_id("helpdesk_ticket_category_cpe_livre"),
                "cat_router_register": _cat_id(
                    "helpdesk_ticket_category_router_register"
                ),
                "cat_password": _cat_id("helpdesk_ticket_category_password"),
                "max_upload_size": session_info["max_file_upload_size"],
                "network_equipments": request.env["network.equipment"]
                .sudo()
                .search(
                    [
                        ("status", "!=", "obsolete"),
                        ("is_danger", "=", False),
                        ("is_deactivating", "=", False),
                    ],
                    order="name",
                ),
            },
        )

    def _prepare_submit_ticket_vals(self, **kw):
        vals = super()._prepare_submit_ticket_vals(**kw)

        portal_type = kw.get("portal_type", "")
        if portal_type:
            vals["portal_type"] = portal_type
            vals["portal_submitter_id"] = request.env.uid
            vals["user_id"] = False

        _TAG_XML_IDS = {
            "network_config": (
                "noc_helpdesk.helpdesk_ticket_tag_portal_network_config"
            ),
            "cpe_livre": "noc_helpdesk.helpdesk_ticket_tag_portal_cpe_livre",
            "router_register": (
                "noc_helpdesk.helpdesk_ticket_tag_portal_router_register"
            ),
            "password": "noc_helpdesk.helpdesk_ticket_tag_portal_password",
        }
        xml_id = _TAG_XML_IDS.get(portal_type)
        if xml_id:
            tag = request.env.ref(xml_id, raise_if_not_found=False)
            if tag:
                vals["tag_id"] = tag.id

        if portal_type == "network_config":
            vals["portal_action_plan"] = kw.get("portal_action_plan", "")
            vals["portal_return_plan"] = kw.get("portal_return_plan", "")
            net_eq = kw.get("portal_net_equipment_id")
            if net_eq:
                try:
                    vals["portal_net_equipment_id"] = int(net_eq)
                except (ValueError, TypeError):
                    pass
        elif portal_type in ("cpe_livre", "router_register"):
            vals["portal_loopback"] = kw.get("portal_loopback", "")
            vals["portal_hostname"] = kw.get("portal_hostname", "")
        elif portal_type == "password":
            vals["portal_password_system"] = (
                kw.get("portal_password_system", "") or False
            )
            vals["portal_corporate_email"] = kw.get("portal_corporate_email", "")
            vals["portal_password_action"] = (
                kw.get("portal_password_action", "") or False
            )

        return vals
