import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move closed tickets (without failure_cause) back to their previous stage.

    Uses mail.tracking.value history to find the stage each ticket was in
    immediately before being moved to done. Falls back to 'Em Day After'
    for tickets with no tracking record.
    """
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'helpdesk_mgmt' AND name = 'helpdesk_ticket_stage_done'
    """
    )
    row = cr.fetchone()
    if not row:
        _logger.warning("Estágio 'done' não encontrado — migração ignorada")
        return
    done_stage_id = row[0]

    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'noc_helpdesk' AND name = 'helpdesk_ticket_stage_dayafter'
    """
    )
    row = cr.fetchone()
    if not row:
        _logger.warning(
            "Estágio fallback 'dayafter' não encontrado — migração ignorada"
        )
        return
    fallback_stage_id = row[0]

    cr.execute(
        """
        SELECT id FROM ir_model_fields
        WHERE model = 'helpdesk.ticket' AND name = 'stage_id'
    """
    )
    row = cr.fetchone()
    if not row:
        _logger.warning("Campo stage_id não encontrado em ir_model_fields")
        return
    field_id = row[0]

    # Tickets com histórico: restaura o estágio anterior à conclusão
    cr.execute(
        """
        WITH last_transition AS (
            SELECT DISTINCT ON (mm.res_id)
                mm.res_id        AS ticket_id,
                tv.old_value_integer AS prev_stage_id
            FROM mail_message mm
            JOIN mail_tracking_value tv ON tv.mail_message_id = mm.id
            WHERE mm.model = 'helpdesk.ticket'
              AND tv.field     = %(field_id)s
              AND tv.new_value_integer = %(done_id)s
            ORDER BY mm.res_id, mm.date DESC
        )
        UPDATE helpdesk_ticket t
           SET stage_id = COALESCE(
                   NULLIF(lt.prev_stage_id, %(done_id)s),
                   %(fallback_id)s
               ),
               closed_date = NULL
          FROM last_transition lt
         WHERE t.id = lt.ticket_id
           AND t.stage_id = %(done_id)s
           AND (t.failure_cause IS NULL OR t.failure_cause = '')
    """,
        {
            "field_id": field_id,
            "done_id": done_stage_id,
            "fallback_id": fallback_stage_id,
        },
    )
    with_history = cr.rowcount

    # Tickets sem histórico de tracking: vai direto para o fallback
    cr.execute(
        """
        UPDATE helpdesk_ticket
           SET stage_id    = %(fallback_id)s,
               closed_date = NULL
         WHERE stage_id = %(done_id)s
           AND (failure_cause IS NULL OR failure_cause = '')
    """,
        {"done_id": done_stage_id, "fallback_id": fallback_stage_id},
    )
    without_history = cr.rowcount

    _logger.info(
        "Migração failure_cause: %d chamados reabertos "
        "(com histórico: %d | sem histórico/fallback: %d)",
        with_history + without_history,
        with_history,
        without_history,
    )
