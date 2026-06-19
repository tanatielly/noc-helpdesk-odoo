from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ata_page = env.ref(
        "noc_helpdesk.document_page_category_ata", raise_if_not_found=False
    )
    group_ata = env.ref("noc_helpdesk.group_document_ata", raise_if_not_found=False)
    if ata_page and group_ata:
        ata_page.write({"groups_id": [(6, 0, [group_ata.id])]})
