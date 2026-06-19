import logging

_logger = logging.getLogger(__name__)

_TAG_ALERT_MAP = {
    "helpdesk_ticket_tag_isp_network_failure": 30,
    "helpdesk_ticket_tag_unavailable": 30,
    "helpdesk_ticket_tag_discarded_packet": 30,
    "helpdesk_ticket_tag_falha_massiva_backbone": 30,
    "helpdesk_ticket_tag_falha_massiva_acesso": 30,
    "helpdesk_ticket_tag_equipamento_isolado": 30,
    "helpdesk_ticket_tag_intermitente": 30,
    "helpdesk_ticket_tag_porta_agregada": 120,
    "helpdesk_ticket_tag_high_latency": 120,
    # tags sem alerta já têm default=0, não precisam ser listadas
}


def migrate(cr, version):
    env = None
    try:
        from odoo.api import Environment
        from odoo.tools.misc import mute_logger

        with mute_logger("odoo.models"):
            env = Environment(cr, 1, {})

        for xml_id, limit in _TAG_ALERT_MAP.items():
            tag = env.ref(f"noc_helpdesk.{xml_id}", raise_if_not_found=False)
            if tag:
                tag.alert_limit_minutes = limit
                _logger.info(
                    "Migration 16.0.0.7.0: tag '%s' → alert_limit_minutes=%s",
                    tag.name,
                    limit,
                )
            else:
                _logger.warning(
                    "Migration 16.0.0.7.0: tag XML ID '%s' não encontrada, ignorada.",
                    xml_id,
                )
    except Exception:
        _logger.exception("Erro na migração 16.0.0.7.0 ao popular alert_limit_minutes")
