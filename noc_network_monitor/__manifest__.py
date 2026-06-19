{
    "name": "NOC Network Monitor",
    "version": "16.0.1.0.0",
    "summary": "Automatic ticket creation from network monitoring alerts",
    "author": "Tanatielly Serafim",
    "category": "Helpdesk",
    "license": "LGPL-3",
    "depends": [
        "helpdesk_mgmt",
        "noc_helpdesk",
        "noc_helpdesk_inventory",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/network_monitor_log_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",
    ],
    "application": False,
    "installable": True,
}
