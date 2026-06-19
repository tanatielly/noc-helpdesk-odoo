import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migra site_id (Many2one) para a tabela M2M network_site_equipment_rel.

    O campo site_id em network_equipment foi substituído por site_ids (Many2many).
    Esta migração cria a tabela de relação e popula com os dados existentes.
    """
    if not version:
        return

    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS network_site_equipment_rel (
            site_id      INTEGER NOT NULL,
            equipment_id INTEGER NOT NULL,
            PRIMARY KEY (site_id, equipment_id)
        )
        """
    )

    cr.execute(
        """
        INSERT INTO network_site_equipment_rel (site_id, equipment_id)
        SELECT site_id, id
        FROM network_equipment
        WHERE site_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    cr.execute("SELECT COUNT(*) FROM network_site_equipment_rel")
    count = cr.fetchone()[0]
    _logger.info(
        "pre-migrate 16.0.1.4.0: %d vínculo(s) equipamento↔site migrado(s)", count
    )
