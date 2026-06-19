import logging

from lxml import etree

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove stale portal_acs_type field references from stored view arches.

    portal_acs_type was removed from helpdesk.ticket when the ACS portal type
    was replaced by cpe_livre and router_register. Views stored in the database
    may still reference it, causing validation errors during module update.
    """
    if not version:
        return

    cr.execute(
        """
        SELECT id, arch_db
        FROM ir_ui_view
        WHERE arch_db::text LIKE '%%portal_acs_type%%'
          AND model IN ('helpdesk.ticket')
        """
    )
    rows = cr.fetchall()

    for view_id, arch_db in rows:
        # arch_db is jsonb: either a dict {"en_US": "<xml>"} or a plain string
        if isinstance(arch_db, dict):
            langs = arch_db
        else:
            langs = {"_": arch_db}

        changed = False
        for lang, xml_src in langs.items():
            try:
                tree = etree.fromstring(xml_src.encode())
            except etree.XMLSyntaxError:
                _logger.warning(
                    "Could not parse arch for view id=%s lang=%s — skipping",
                    view_id, lang,
                )
                continue

            stale_fields = tree.xpath('.//field[@name="portal_acs_type"]')
            if not stale_fields:
                continue

            for field_el in stale_fields:
                field_el.getparent().remove(field_el)

            langs[lang] = etree.tostring(tree, encoding="unicode")
            changed = True

        if not changed:
            continue

        if "_" in langs:
            new_arch = langs["_"]
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                (new_arch, view_id),
            )
        else:
            import json
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s::jsonb WHERE id = %s",
                (json.dumps(langs), view_id),
            )
        _logger.info(
            "pre-migrate: removed stale <field name='portal_acs_type'> from view id=%s",
            view_id,
        )
