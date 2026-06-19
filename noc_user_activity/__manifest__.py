{
    "name": "NOC User Activity",
    "version": "16.0.1.0.0",
    "summary": "Automatic logout on inactivity and user activity reports",
    "author": "Tanatielly Serafim",
    "category": "Technical",
    "license": "AGPL-3",
    "depends": ["noc_contacts", "web", "helpdesk_mgmt"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/res_users_session_log_views.xml",
        "views/res_users_views.xml",
        "views/menu_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "noc_user_activity/static/src/js/idle_timeout_service.js",
        ],
    },
    "application": False,
    "installable": True,
}
