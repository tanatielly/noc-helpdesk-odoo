import logging

from lxml import etree

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove stale references to the removed 'code' field of network.circuit.

    The 'code' field was removed from network.circuit in v16.0.1.0.0.
    Views stored in the database may still reference it, causing view
    validation errors during the module update.  This script strips those
    references before any data files are loaded.
    """
    if not version:
        return

    cr.execute(
        """
        SELECT id, arch_db
        FROM ir_ui_view
        WHERE arch_db LIKE '%%name="code"%%'
          AND model IN ('network.circuit', 'network.equipment')
        """
    )
    rows = cr.fetchall()

    for view_id, arch_db in rows:
        try:
            tree = etree.fromstring(arch_db.encode())
        except etree.XMLSyntaxError:
            _logger.warning("Could not parse arch for view id=%s — skipping", view_id)
            continue

        stale_fields = tree.xpath('.//field[@name="code"]')
        if not stale_fields:
            continue

        for field_el in stale_fields:
            field_el.getparent().remove(field_el)

        new_arch = etree.tostring(tree, encoding="unicode")
        cr.execute(
            "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
            (new_arch, view_id),
        )
        _logger.info(
            "pre-migrate: removed stale <field name='code'> from view id=%s", view_id
        )
