import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recomputa network_path para exibir a interface do circuito no lugar do IP.

    O compute de network_path passou a usar circuit_id.origin_interface e
    circuit_id.destination_interface em vez de net_origin_id.ip_address e
    net_destination_id.ip_address.  Como o campo é stored, os registros
    existentes precisam ser recomputados.
    """
    if not version:
        return

    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    tickets = env["helpdesk.ticket"].search([("net_origin_id", "!=", False)])
    if not tickets:
        return

    tickets._compute_network_path()
    _logger.info(
        "post-migrate 16.0.1.2.0: network_path recomputado em %d chamado(s)",
        len(tickets),
    )
