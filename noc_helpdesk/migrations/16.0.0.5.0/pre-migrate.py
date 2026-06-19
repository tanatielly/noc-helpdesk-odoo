import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,)
    )
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _ref(env, xmlid):
    """env.ref com fallback silencioso."""
    return env.ref(xmlid, raise_if_not_found=False)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # ── 1. Parceiro isp_partner / first_contact ────────────────────────────────────
    # Tenta pelo xmlid; se a ir_model_data já foi limpa por uma migration
    # anterior, busca pelo nome como fallback.

    isp_partner = _ref(env, "noc_helpdesk.isp_partner") or env["res.partner"].search(
        [
            (("name", "=", "ISP Partner")),
            ("noc_type", "=", "provider"),
            ("is_company", "=", True),
        ],
        limit=1,
    )

    if isp_partner:
        main_partner = env.ref("base.main_company").partner_id

        if _column_exists(cr, "helpdesk_ticket", "provider_id"):
            cr.execute(
                "UPDATE helpdesk_ticket SET provider_id = %s WHERE provider_id = %s",
                (main_partner.id, isp_partner.id),
            )

        if _table_exists(cr, "network_circuit") and _column_exists(
            cr, "network_circuit", "provider_id"
        ):
            cr.execute(
                "UPDATE network_circuit SET provider_id = %s WHERE provider_id = %s",
                (main_partner.id, isp_partner.id),
            )

        if _column_exists(cr, "res_partner", "provider_id"):
            cr.execute(
                "UPDATE res_partner SET provider_id = %s WHERE provider_id = %s",
                (main_partner.id, isp_partner.id),
            )

        first_contact = _ref(env, "noc_helpdesk.first_contact") or env[
            "res.partner"
        ].search(
            [("name", "=", "Suporte"), ("parent_id", "=", isp_partner.id)],
            limit=1,
        )
        if first_contact:
            first_contact.with_context(active_test=False).unlink()
            _logger.info("first_contact excluído")

        isp_partner.with_context(active_test=False).unlink()
        _logger.info("parceiro isp_partner excluído")
    else:
        _logger.info("parceiro isp_partner não encontrado — pulando")

    # ── 2. Circuito circuit_a_b ──────────────────────────────────────────────

    circuit = _ref(env, "noc_helpdesk.circuit_a_b")

    if circuit:
        if _column_exists(cr, "helpdesk_ticket", "circuit_id"):
            cr.execute(
                "UPDATE helpdesk_ticket SET circuit_id = NULL WHERE circuit_id = %s",
                (circuit.id,),
            )
        if _table_exists(cr, "network_monitor_log"):
            cr.execute(
                "UPDATE network_monitor_log"
                " SET circuit_id = NULL WHERE circuit_id = %s",
                (circuit.id,),
            )
        circuit.unlink()
        _logger.info("circuit_a_b excluído")

    # ── 3. Equipamentos switch_a / switch_b ──────────────────────────────────

    for xmlid in ("noc_helpdesk.switch_a", "noc_helpdesk.switch_b"):
        eq = _ref(env, xmlid)
        if not eq:
            continue
        if _column_exists(cr, "helpdesk_ticket", "net_origin_id"):
            cr.execute(
                "UPDATE helpdesk_ticket SET net_origin_id = NULL"
                " WHERE net_origin_id = %s",
                (eq.id,),
            )
        if _column_exists(cr, "helpdesk_ticket", "net_destination_id"):
            cr.execute(
                "UPDATE helpdesk_ticket SET net_destination_id = NULL"
                " WHERE net_destination_id = %s",
                (eq.id,),
            )
        eq.unlink()
        _logger.info("%s excluído", xmlid)

    # ── 4. VLANs ─────────────────────────────────────────────────────────────

    for xmlid in (
        "noc_helpdesk.vlan_10",
        "noc_helpdesk.vlan_20",
        "noc_helpdesk.vlan_30",
        "noc_helpdesk.vlan_100",
        "noc_helpdesk.vlan_200",
    ):
        vlan = _ref(env, xmlid)
        if vlan:
            vlan.unlink()
            _logger.info("%s excluído", xmlid)
