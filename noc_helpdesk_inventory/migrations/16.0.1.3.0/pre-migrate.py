import json
import logging

from lxml import etree

_logger = logging.getLogger(__name__)


def _remove_geo_field(arch_str):
    """Return cleaned arch string, or None if nothing was removed."""
    try:
        tree = etree.fromstring(arch_str.encode())
    except etree.XMLSyntaxError:
        return None
    stale = tree.xpath('.//field[@name="geo_coords_display"]')
    if not stale:
        return None
    for el in stale:
        el.getparent().remove(el)
    return etree.tostring(tree, encoding="unicode")


def migrate(cr, version):
    """Remove stale references to the removed 'geo_coords_display' field.

    The field no longer exists in network.equipment but may still be referenced
    in view arch records in the database, causing frontend JS errors.
    """
    if not version:
        return

    # arch_db is jsonb — cast to text so LIKE works
    cr.execute(
        """
        SELECT id, arch_db
        FROM ir_ui_view
        WHERE arch_db::text LIKE '%%name="geo_coords_display"%%'
          AND model = 'network.equipment'
        """
    )
    rows = cr.fetchall()

    for view_id, arch_db in rows:
        # psycopg2 deserialises jsonb → dict  {"en_US": "<xml>", ...}
        if isinstance(arch_db, dict):
            new_arch_db = dict(arch_db)
            updated = False
            for lang, arch_str in arch_db.items():
                cleaned = _remove_geo_field(arch_str)
                if cleaned is not None:
                    new_arch_db[lang] = cleaned
                    updated = True
            if not updated:
                continue
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                (json.dumps(new_arch_db), view_id),
            )
        else:
            cleaned = _remove_geo_field(arch_db or "")
            if cleaned is None:
                continue
            cr.execute(
                "UPDATE ir_ui_view SET arch_db = %s WHERE id = %s",
                (cleaned, view_id),
            )

        _logger.info(
            "pre-migrate: removed stale"
            " <field name='geo_coords_display'> from view id=%s",
            view_id,
        )
