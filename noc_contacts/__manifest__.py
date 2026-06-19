{
    "name": "NOC Contacts",
    "version": "16.0.0.0.0",
    "category": "Helpdesk",
    "summary": "ISP providers and clients registry for the NOC helpdesk",
    "author": "Tanatielly Serafim",
    "depends": ["contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_menu_actions.xml",
        "views/res_partner_view.xml",
        "views/res_users_views.xml",
        "views/login_template.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
