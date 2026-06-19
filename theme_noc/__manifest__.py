{
    "name": "Theme NOC",
    "version": "16.0.3.0.0",
    "summary": "Custom color theme for NOC Helpdesk",
    "category": "Themes/Backend",
    "author": "Tanatielly Serafim",
    "depends": ["web"],
    "license": "LGPL-3",
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "theme_noc/static/src/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "theme_noc/static/src/scss/theme.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
