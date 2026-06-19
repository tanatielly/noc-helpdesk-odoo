{
    "name": "NOC Helpdesk Graphics",
    "version": "16.0.0.0.0",
    "summary": "Gráfico de latência do link na aba Gráficos do ticket",
    "category": "Helpdesk",
    "author": "Tanatielly Serafim",
    "license": "LGPL-3",
    "depends": ["helpdesk_mgmt", "noc_helpdesk"],
    "auto_install_module_dependencies": False,
    "external_dependencies": {},
    "data": [
        "security/ir.model.access.csv",
        "views/helpdesk_ticket_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "noc_helpdesk_graphics/static/src/css/latency_chart.css",
            "noc_helpdesk_graphics/static/src/xml/latency_chart.xml",
            "noc_helpdesk_graphics/static/src/components/latency_chart.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
