# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "NOC Suite",
    "summary": "NOC Helpdesk base configuration",
    "version": "16.0.0.0.0",
    "license": "AGPL-3",
    "author": "Tanatielly Serafim",
    "website": "https://github.com/OCA/helpdesk",
    "depends": [
        "web_company_color",
        "noc_helpdesk",
        "noc_contacts",
        "noc_helpdesk_dashboard",
        "noc_helpdesk_graphics",
        "noc_helpdesk_inventory",
        "noc_network_topology",
        "noc_network_monitor",
        "noc_user_activity",
        "theme_noc",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "noc_base/static/src/js/clipboard_patch.js",
            "noc_base/static/src/js/ctrl_click_list.js",
        ],
    },
    "application": True,
    "installable": True,
}
