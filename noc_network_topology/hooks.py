import logging
import time

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    """Geocodifica equipamentos existentes com location mas sem coordenadas."""
    from odoo import SUPERUSER_ID
    from odoo.api import Environment

    with Environment.manage():
        env = Environment(cr, SUPERUSER_ID, {})
        records = env["network.equipment"].search(
            [
                ("location", "!=", False),
                ("latitude", "=", 0.0),
                ("longitude", "=", 0.0),
            ]
        )
        total = len(records)
        _logger.info(
            "noc_network_topology: geocodificando %d equipamento(s)...",
            total,
        )
        success = 0
        for i, rec in enumerate(records):
            if i > 0:
                time.sleep(1.1)
            lat, lng = rec._geocode(rec.location)
            if lat is not None:
                rec.write({"latitude": lat, "longitude": lng})
                success += 1
        _logger.info(
            "noc_network_topology: %d/%d geocodificado(s).",
            success,
            total,
        )
