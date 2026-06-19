{
    "name": "NOC User Notes",
    "version": "16.0.1.0.0",
    "summary": "Private notes and drafts per user",
    "author": "Tanatielly Serafim",
    "category": "Technical",
    "license": "AGPL-3",
    "depends": ["noc_contacts", "helpdesk_mgmt"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/user_note_views.xml",
        "views/menu_views.xml",
    ],
    "application": False,
    "installable": True,
}
