import logging
from datetime import timedelta
from urllib.parse import quote

import requests
from pytz import timezone, utc

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .helpdesk_escala import CHEIA_WEEKDAYS

_logger = logging.getLogger(__name__)

_NEW_TICKET_CHECK_INTERVAL_DEFAULT = 30

# Campos que, quando alterados, disparam atualização em tempo real na lista
_LIVE_UPDATE_FIELDS = frozenset(
    {
        "stage_id",
        "tag_id",
        "user_id",
        "partner_id",
        "provider_id",
        "name",
        "traffic_loss",
    }
)

# Canal bus público para broadcast de mudanças de chamados
_BUS_CHANNEL = "noc_helpdesk.ticket_updates"

KEYWORDS = [
    "TESTE",
    "TEST",
    "PROBLEMA",
    "ERRO",
    "FALHA",
    "DEFEITO",
    "BUG",
    "INCIDENTE",
    "PING",
    "SUCCESS",
    "RATE",
    "SOURCE",
    "LOOPBACK",
]


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"
    _order = "tag_priority asc, id asc"

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------

    description = fields.Html(required=False, sanitize_style=True)
    user_id = fields.Many2one(string="1º Responsável")
    number_short = fields.Char(
        string="Nº",
        compute="_compute_number_short",
        store=False,
    )
    user2_id = fields.Many2one(
        comodel_name="res.users",
        string="2º Responsável",
        tracking=True,
        index=True,
        domain=[("share", "=", False)],
    )
    user_short_name = fields.Char(
        string="Usuário Responsável",
        compute="_compute_user_short_name",
        store=False,
    )
    user2_short_name = fields.Char(
        string="2º Responsável",
        compute="_compute_user2_short_name",
        store=False,
    )
    ticket_creator_id = fields.Many2one(
        comodel_name="res.users",
        string="Aberto por",
        compute="_compute_ticket_creator_id",
        store=False,
    )

    # --- Campos de Lista / Exibição ---
    traffic_loss = fields.Char(string="Tráfego/Loss")
    data_origin = fields.Char(string="Origem")
    data_destination = fields.Char(string="Destino")
    designation_speed = fields.Char(
        string="Designação/Velocidade",
        compute="_compute_designation_speed",
        store=False,
    )
    phone_number = fields.Char(string="Número de Telefone")
    last_user_uid = fields.Many2one(
        comodel_name="res.users",
        string="Última Atualização por",
        store=True,
        readonly=True,
        copy=False,
        index=True,
    )
    last_user_date = fields.Datetime(
        string="Data da Última Atualização",
        store=True,
        readonly=True,
        copy=False,
    )
    last_update_info = fields.Char(
        string="Last Update",
        compute="_compute_last_update_info",
        store=False,
    )

    external_ticket_number = fields.Char(
        string="Número do Chamado com a Operadora",
    )

    rma_number = fields.Char(string="Número RMA")
    serial_number = fields.Char(string="Número de Série (NS)")
    product_name = fields.Char(string="Nome do Produto")
    contract_number = fields.Char(string="Nº do Contrato")
    hostname = fields.Char()

    inactivity_limit_minutes = fields.Integer(
        string="Tempo Limite de Inatividade (min)",
        compute="_compute_inactivity_limit_minutes",
        store=True,
        default=0,
    )

    visit_date_time = fields.Datetime(
        string="Data e Hora do agendamento:",
        default=fields.Datetime.now,
        required=True,
    )

    operator_name = fields.Char(
        string="Nome do colaborador:",
        default="",
    )
    visit_equipment_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento da Visita",
    )
    visit_equipment_domain_ids = fields.Many2many(
        comodel_name="network.equipment",
        relation="helpdesk_ticket_visit_equip_domain_rel",
        column1="ticket_id",
        column2="equipment_id",
        compute="_compute_visit_equipment_domain_ids",
        string="Equipamentos Válidos para Visita",
    )
    visit_equipment_address = fields.Char(
        string="Endereço do Equipamento",
        compute="_compute_visit_equipment_address",
        store=False,
    )

    net_origin_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento Origem",
    )
    net_destination_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento Destino",
    )

    tag_id = fields.Many2one(
        comodel_name="helpdesk.ticket.tag",
        string="Tipo de Evento",
        ondelete="restrict",
        store=True,
    )
    tag_priority = fields.Integer(
        compute="_compute_tag_priority",
        store=True,
        index=True,
    )

    is_isp_network_failure = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_high_latency = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_unavailable = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_discarded_packet = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_falha_massiva = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_porta_agregada = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_equipamento_isolado = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_sinergia = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_sistemas_ti = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_intermitente = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_manutencao_programada = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_plano_melhoria = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_falha_hardware = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_falha_software = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_rma_cisco_logicalis = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_fap = fields.Boolean(
        compute="_compute_tag_decorations",
        store=True,
    )
    is_portal_ticket = fields.Boolean(
        compute="_compute_is_portal_ticket",
        store=True,
    )

    activity_start_datetime = fields.Datetime(
        string="Início da Atividade",
    )
    activity_end_datetime = fields.Datetime(
        string="Fim da Atividade",
    )

    client_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="helpdesk_ticket_client_rel",
        column1="ticket_id",
        column2="partner_id",
        string="Clientes",
        domain="[('noc_type', '=', 'client')]",
    )

    provider_id = fields.Many2one(
        comodel_name="res.partner",
        string="Operadora",
        domain="[('noc_type', '=', 'provider'), ('is_company', '=', True)]",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    client_id = fields.Many2one(
        comodel_name="res.partner",
        string="Cliente Cadastrado",
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('provider_id', '=?', provider_id)]",
    )

    client_circuit = fields.Char(
        string="ID do Circuito",
        related="client_id.circuit_id",
        store=False,
        readonly=True,
    )
    client_designation = fields.Char(
        string="Designação",
        related="client_id.designation",
        store=False,
        readonly=True,
    )
    client_bandwidth = fields.Char(
        string="Velocidade",
        related="client_id.bandwidth",
        store=False,
        readonly=True,
    )

    validation_date = fields.Datetime(
        string="Data de Entrada em Validação",
        readonly=True,
    )

    reopen_date = fields.Datetime(
        string="Data de Reabertura",
        readonly=True,
    )

    reopen_count = fields.Integer(
        string="Reincidências",
        default=0,
        readonly=True,
    )

    failure_cause = fields.Char(
        string="Causa da Falha",
        size=500,
    )

    related_ticket_ids = fields.Many2many(
        comodel_name="helpdesk.ticket",
        relation="helpdesk_ticket_correlation_rel",
        column1="ticket_id",
        column2="related_ticket_id",
        string="Chamados Correlacionados",
    )

    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Arquivos",
        compute="_compute_attachment_ids",
        inverse="_inverse_attachment_ids",
    )

    @api.depends("message_ids.attachment_ids")
    def _compute_attachment_ids(self):
        IrAttachment = self.env["ir.attachment"].sudo()
        for ticket in self:
            ticket.attachment_ids = (
                IrAttachment.search(
                    [("res_model", "=", self._name), ("res_id", "=", ticket.id)]
                )
                if ticket.id
                else IrAttachment
            )

    def _inverse_attachment_ids(self):
        for ticket in self:
            ticket.attachment_ids.sudo().write(
                {"res_model": self._name, "res_id": ticket.id}
            )

    traffic_restriction = fields.Boolean(
        string="Restrição de Tráfego",
        default=False,
    )

    # -------------------------------------------------------------------------
    # PORTAL FIELDS
    # -------------------------------------------------------------------------

    portal_type = fields.Selection(
        selection=[
            ("network_config", "Configuração de Rede"),
            ("cpe_livre", "CPE Livre"),
            ("router_register", "Cadastro de Roteador"),
            ("password", "Senha"),
        ],
        string="Tipo (Portal)",
    )
    portal_submitter_id = fields.Many2one(
        comodel_name="res.users",
        string="Aberto por",
        ondelete="set null",
        readonly=True,
        index=True,
    )
    portal_action_plan = fields.Text(string="Plano de Ação")
    portal_return_plan = fields.Text(string="Plano de Retorno")
    portal_net_equipment_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento (Portal)",
        ondelete="set null",
    )
    portal_loopback = fields.Char(string="Loopback")
    portal_hostname = fields.Char(string="Hostname")
    portal_password_system = fields.Selection(
        selection=[
            ("vco_237", "VCO 237"),
            ("tacacs", "TACACS"),
        ],
        string="Sistema de Senha",
    )
    portal_corporate_email = fields.Char(string="Email Corporativo")
    portal_password_action = fields.Selection(
        selection=[
            ("create_user", "Criação de Usuário"),
            ("reset_password", "Reset de Senha"),
            ("delete_user", "Exclusão de Usuário"),
        ],
        string="Ação de Senha",
    )

    first_contact_id = fields.Many2one(
        comodel_name="res.partner",
        string="ID Primeiro Contato",
        compute="_compute_first_contact",
        store=False,
    )

    first_contact_email = fields.Char(
        string="Email do Primeiro Contato",
        compute="_compute_first_contact",
        store=False,
    )
    first_contact_phone = fields.Char(
        string="Telefone do Primeiro Contato",
        compute="_compute_first_contact",
        store=False,
    )
    first_contact_type = fields.Selection(
        string="Tipo do Primeiro Contato",
        selection=lambda self: self.env["res.partner"]
        ._fields["contact_type"]
        .selection,
        compute="_compute_first_contact",
        store=False,
    )
    first_contact_name = fields.Char(
        string="Primeiro Contato",
        compute="_compute_first_contact",
        store=False,
    )

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------

    @api.depends("user_id")
    def _compute_user_short_name(self):
        for ticket in self:
            parts = (ticket.user_id.name or "").split()
            ticket.user_short_name = (
                f"{parts[0]} {parts[-1]}"
                if len(parts) > 1
                else (parts[0] if parts else "")
            )

    @api.depends("user2_id")
    def _compute_user2_short_name(self):
        for ticket in self:
            parts = (ticket.user2_id.name or "").split()
            ticket.user2_short_name = (
                f"{parts[0]} {parts[-1]}"
                if len(parts) > 1
                else (parts[0] if parts else "")
            )

    @api.depends("portal_submitter_id", "create_uid")
    def _compute_ticket_creator_id(self):
        for ticket in self:
            ticket.ticket_creator_id = ticket.portal_submitter_id or ticket.create_uid

    @api.depends("number")
    def _compute_number_short(self):
        for ticket in self:
            raw = ticket.number or ""
            ticket.number_short = raw.lstrip("HT").lstrip("0") or raw

    @api.depends("circuit_id")
    def _compute_designation_speed(self):
        for rec in self:
            circuit = rec.circuit_id
            if circuit:
                designation = circuit.link_designation or ""
                speed = circuit.link_speed or ""
                if designation and speed:
                    rec.designation_speed = f"{designation} / {speed}"
                elif designation or speed:
                    rec.designation_speed = designation or speed
                else:
                    rec.designation_speed = False
            else:
                rec.designation_speed = False

    @api.depends("net_origin_id", "net_destination_id")
    def _compute_visit_equipment_domain_ids(self):
        for rec in self:
            ids = []
            if rec.net_origin_id:
                ids.append(rec.net_origin_id.id)
            if rec.net_destination_id:
                ids.append(rec.net_destination_id.id)
            rec.visit_equipment_domain_ids = [(6, 0, ids)]

    @api.depends("visit_equipment_id")
    def _compute_visit_equipment_address(self):
        for rec in self:
            rec.visit_equipment_address = rec.visit_equipment_id.location or False

    @api.depends("tag_id", "tag_id.priority")
    def _compute_tag_priority(self):
        for ticket in self:
            ticket.tag_priority = ticket.tag_id.priority if ticket.tag_id else 9999

    @api.depends("tag_id")
    def _compute_tag_decorations(self):
        def ref(xml_id):
            return self.env.ref(f"noc_helpdesk.{xml_id}", raise_if_not_found=False)

        tag_isp_network_failure = ref(
            "helpdesk_ticket_tag_isp_network_failure"
        )
        tag_high_latency = ref("helpdesk_ticket_tag_high_latency")
        tag_unavailable = ref("helpdesk_ticket_tag_unavailable")
        tag_discarded_packet = ref("helpdesk_ticket_tag_discarded_packet")
        tag_falha_massiva_backbone = ref("helpdesk_ticket_tag_falha_massiva_backbone")
        tag_falha_massiva_acesso = ref("helpdesk_ticket_tag_falha_massiva_acesso")
        tag_porta_agregada = ref("helpdesk_ticket_tag_porta_agregada")
        tag_equipamento_isolado = ref("helpdesk_ticket_tag_equipamento_isolado")
        tag_sinergia = ref("helpdesk_ticket_tag_sinergia")
        tag_sistemas_ti = ref("helpdesk_ticket_tag_sistemas_ti")
        tag_intermitente = ref("helpdesk_ticket_tag_intermitente")
        tag_manutencao_programada = ref("helpdesk_ticket_tag_manutencao_programada")
        tag_plano_melhoria = ref("helpdesk_ticket_tag_plano_melhoria")
        tag_falha_hardware = ref("helpdesk_ticket_tag_falha_hardware")
        tag_falha_software = ref("helpdesk_ticket_tag_falha_software")
        tag_rma_cisco_logicalis = ref("helpdesk_ticket_tag_rma_cisco_logicalis")
        tag_fap = ref("helpdesk_ticket_tag_fap")
        tag_fanp = ref("helpdesk_ticket_tag_fanp")
        tag_fape = ref("helpdesk_ticket_tag_fape")
        tag_fapi = ref("helpdesk_ticket_tag_fapi")

        for ticket in self:
            t = ticket.tag_id
            ticket.is_isp_network_failure = bool(
                tag_isp_network_failure and t == tag_isp_network_failure
            )
            ticket.is_high_latency = bool(tag_high_latency and t == tag_high_latency)
            ticket.is_unavailable = bool(tag_unavailable and t == tag_unavailable)
            ticket.is_discarded_packet = bool(
                tag_discarded_packet and t == tag_discarded_packet
            )
            ticket.is_falha_massiva = bool(
                (tag_falha_massiva_backbone and t == tag_falha_massiva_backbone)
                or (tag_falha_massiva_acesso and t == tag_falha_massiva_acesso)
            )
            ticket.is_porta_agregada = bool(
                tag_porta_agregada and t == tag_porta_agregada
            )
            ticket.is_equipamento_isolado = bool(
                tag_equipamento_isolado and t == tag_equipamento_isolado
            )
            ticket.is_sinergia = bool(tag_sinergia and t == tag_sinergia)
            ticket.is_sistemas_ti = bool(tag_sistemas_ti and t == tag_sistemas_ti)
            ticket.is_intermitente = bool(tag_intermitente and t == tag_intermitente)
            ticket.is_manutencao_programada = bool(
                tag_manutencao_programada and t == tag_manutencao_programada
            )
            ticket.is_plano_melhoria = bool(
                tag_plano_melhoria and t == tag_plano_melhoria
            )
            ticket.is_falha_hardware = bool(
                tag_falha_hardware and t == tag_falha_hardware
            )
            ticket.is_falha_software = bool(
                tag_falha_software and t == tag_falha_software
            )
            ticket.is_rma_cisco_logicalis = bool(
                tag_rma_cisco_logicalis and t == tag_rma_cisco_logicalis
            )
            ticket.is_fap = bool(
                (tag_fap and t == tag_fap)
                or (tag_fanp and t == tag_fanp)
                or (tag_fape and t == tag_fape)
                or (tag_fapi and t == tag_fapi)
            )

    @api.depends("portal_type")
    def _compute_is_portal_ticket(self):
        for ticket in self:
            ticket.is_portal_ticket = bool(ticket.portal_type)

    @api.depends("team_id", "portal_type")
    def _compute_user_id(self):
        plantao_user = self.get_current_plantao_user()
        for ticket in self:
            if ticket.portal_type:
                # Tickets de portal nunca recebem atribuição automática.
                # O atendente deve assumir manualmente.
                ticket.user_id = False
            elif not ticket.user_id and ticket.team_id:
                ticket.user_id = plantao_user or ticket.team_id.alias_user_id

    @api.depends("tag_id", "tag_id.alert_limit_minutes")
    def _compute_inactivity_limit_minutes(self):
        for ticket in self:
            ticket.inactivity_limit_minutes = (
                ticket.tag_id.alert_limit_minutes if ticket.tag_id else 0
            )

    _EXCLUDED_MSG_TYPES = frozenset(
        {"notification", "auto_comment", "user_notification"}
    )

    @api.depends(
        "last_user_uid",
        "last_user_date",
        "write_uid",
        "write_date",
        "message_ids.date",
        "message_ids.create_uid",
        "activity_ids.write_date",
        "activity_ids.user_id",
        "message_follower_ids",
    )
    def _compute_last_update_info(self):
        for ticket in self:
            candidates = []

            fallback_user = (
                ticket.write_uid
                if ticket.write_uid and ticket.write_uid.id != SUPERUSER_ID
                else None
            )
            user = ticket.last_user_uid or fallback_user
            date = ticket.last_user_date or (
                ticket.write_date if fallback_user else None
            )
            if user and date:
                candidates.append((date, user))

            for msg in ticket.message_ids:
                if (
                    msg.message_type not in self._EXCLUDED_MSG_TYPES
                    and msg.create_uid
                    and msg.create_uid.id != SUPERUSER_ID
                    and msg.date
                ):
                    candidates.append((msg.date, msg.create_uid))

            for act in ticket.activity_ids:
                if act.user_id and act.write_date:
                    candidates.append((act.write_date, act.user_id))

            if candidates:
                best_date, best_user = max(candidates, key=lambda x: x[0])
                parts = (best_user.name or "").split()
                short_name = (
                    f"{parts[0]} {parts[-1]}"
                    if len(parts) > 1
                    else parts[0]
                    if parts
                    else ""
                )
                ticket.last_update_info = (
                    f"{short_name} at {fields.Datetime.to_string(best_date)}"
                )
            else:
                ticket.last_update_info = "No updates yet"

    @api.depends(
        "provider_id",
        "provider_id.child_ids.escalation_type",
        "provider_id.child_ids.email",  # ← adicionar para o Odoo rastrear corretamente
        "provider_id.child_ids.phone",
        "provider_id.child_ids.contact_type",
    )
    def _compute_first_contact(self):
        for ticket in self:
            provider = ticket.provider_id._origin if ticket.provider_id else None
            if not provider or not provider.id:
                ticket.first_contact_id = False
                ticket.first_contact_name = False
                ticket.first_contact_email = False
                ticket.first_contact_phone = False
                ticket.first_contact_type = False
                continue

            contact = provider.child_ids.filtered(
                lambda c: c.escalation_type == "first_contact"
            )[:1]

            ticket.first_contact_id = contact or False
            ticket.first_contact_name = contact.name if contact else False
            ticket.first_contact_email = contact.email if contact else False
            ticket.first_contact_phone = contact.phone if contact else False
            ticket.first_contact_type = contact.contact_type if contact else False

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if "user_id" in fields_list and "user_id" not in defaults:
            plantao_user = self.get_current_plantao_user()
            defaults["user_id"] = plantao_user.id if plantao_user else self.env.uid
        if "user2_id" in fields_list and "user2_id" not in defaults:
            entry = self._get_duty_entry_from_escala()
            if entry:
                _, user2 = entry.get_effective_users()
                if user2:
                    defaults["user2_id"] = user2.id
        return defaults

    # -------------------------------------------------------------------------
    # ONCHANGE
    # -------------------------------------------------------------------------

    @api.onchange("net_origin_id", "net_destination_id")
    def _onchange_network_equipment(self):
        valid_ids = []
        if self.net_origin_id:
            valid_ids.append(self.net_origin_id.id)
        if self.net_destination_id:
            valid_ids.append(self.net_destination_id.id)
        if self.visit_equipment_id and self.visit_equipment_id.id not in valid_ids:
            self.visit_equipment_id = False

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        self.provider_id = self.partner_id

    @api.onchange("provider_id")
    def _onchange_provider_id(self):
        """Limpa o cliente ao trocar de operadora."""
        if not self.client_id:
            return
        # FIX: _origin acessa o registro persistido dentro do onchange,
        # evitando navegação em registros virtuais que retornam _unknown.
        client_provider = self.client_id._origin.provider_id
        if client_provider and client_provider != self.provider_id._origin:
            self.client_id = False

    @api.onchange("client_id")
    def _onchange_client_id(self):
        """Preenche campos do ticket com dados do cliente ao selecioná-lo."""
        if not self.client_id:
            return
        # FIX: _origin garante leitura do registro real do banco.
        # Sem isso, navegar client_id.provider_id dentro do onchange
        # pode retornar _unknown para registros recém-selecionados.
        client = self.client_id._origin
        if not client.id:
            return
        if client.provider_id and not self.provider_id:
            self.provider_id = client.provider_id
        if client.designation:
            self.designation_speed = client.designation
        if client.phone:
            self.phone_number = client.phone

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def _get_critical_teams_tags(self):
        """Retorna o recordset das tags que disparam alerta no Teams."""

        def ref(xml_id):
            return self.env.ref(f"noc_helpdesk.{xml_id}", raise_if_not_found=False)

        tags = [
            ref("helpdesk_ticket_tag_equipamento_isolado"),
            ref("helpdesk_ticket_tag_falha_massiva_backbone"),
            ref("helpdesk_ticket_tag_falha_massiva_acesso"),
        ]
        return self.env["helpdesk.ticket.tag"].browse([t.id for t in tags if t])

    def _send_teams_critical_alert(self):
        """Envia mensagem no canal Teams para chamados abertos com tags críticas.

        O webhook é configurado em:
        Configurações > Técnico > Parâmetros > Parâmetros do Sistema
        Chave: noc_helpdesk.teams_critical_webhook_url
        """
        webhook_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("noc_helpdesk.teams_critical_webhook_url")
        )
        if not webhook_url:
            return

        critical_tags = self._get_critical_teams_tags()
        if not critical_tags:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")

        for ticket in self:
            if ticket.tag_id not in critical_tags:
                continue

            ticket_url = (
                f"{base_url}/web"
                f"#model=helpdesk.ticket&id={ticket.id}&view_type=form"
            )
            tag_name = ticket.tag_id.name or ""

            payload = {
                "ticket_id": ticket.id,
                "ticket_name": f"#{ticket.id} — {ticket.name}",
                "tag": tag_name,
                "link": ticket_url,
                "create_date": fields.Datetime.to_string(
                    ticket.create_date or fields.Datetime.now()
                ),
            }

            try:
                resp = requests.post(webhook_url, json=payload, timeout=10)
                if not resp.ok:
                    _logger.warning(
                        "Teams webhook retornou HTTP %s para chamado #%s: %s",
                        resp.status_code,
                        ticket.id,
                        resp.text[:200],
                    )
            except Exception:
                _logger.exception(
                    "Falha ao enviar alerta Teams para chamado #%s", ticket.id
                )

    def _bus_notify_ticket_change(self, action):
        """Envia notificação bus para todos os usuários internos.
        Usa canais de parceiro (sempre subscritos) em vez de canal customizado.
        Deduplica dentro da mesma transação."""
        key = f"_noc_bus_notify_{action}"
        if getattr(self.env.cr, key, False):
            return
        setattr(self.env.cr, key, True)
        bus = self.env["bus.bus"].sudo()
        all_users = self.env["res.users"].sudo().search([("share", "=", False)])
        for user in all_users:
            if not user.partner_id:
                continue
            bus._sendone(
                user.partner_id,
                "noc_helpdesk/ticket_update",
                {"action": action},
            )

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        portal = records.filtered("portal_type")
        if portal:
            portal.sudo().write({"user_id": False})
            self.sudo()._notify_new_portal_tickets(portal)
        records._send_teams_critical_alert()
        return records

    def _notify_new_portal_tickets(self, tickets):
        tickets_payload = [
            {
                "ticket_id": ticket.id,
                "ticket_name": ticket.display_name,
                "alert_key": f"{ticket.id}: {ticket.create_date}",
            }
            for ticket in tickets
        ]
        team_users = self._get_support_team_users()
        bus = self.env["bus.bus"].sudo()
        for user in team_users:
            if not user.partner_id:
                continue
            bus._sendone(
                user.partner_id,
                "noc_helpdesk/new_ticket_alert",
                {
                    "check_interval_minutes": self._get_new_ticket_check_interval(),
                    "tickets": tickets_payload,
                },
            )

    # -------------------------------------------------------------------------
    # CREATE / WRITE
    # -------------------------------------------------------------------------

    @api.model
    def read_group(
        self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True
    ):
        """Reordena grupos por prioridade da tag quando agrupado por tag_id.

        O Odoo ordena grupos de Many2one pelo ID do registro (ordem de criação),
        ignorando o _order do modelo relacionado. Aqui fazemos o sort no Python
        após o read_group usando o campo priority da tag.
        """
        result = super().read_group(
            domain,
            fields,
            groupby,
            offset=offset,
            limit=limit,
            orderby=orderby,
            lazy=lazy,
        )
        if groupby and groupby[0] == "tag_id":
            tag_ids = [g["tag_id"][0] for g in result if g.get("tag_id")]
            if tag_ids:
                priority_map = {
                    tag.id: tag.priority
                    for tag in self.env["helpdesk.ticket.tag"].browse(tag_ids)
                }
                result.sort(
                    key=lambda g: priority_map.get(
                        g["tag_id"][0] if g.get("tag_id") else None, 9999
                    )
                )
        return result

    def write(self, vals):
        if self.env.uid != SUPERUSER_ID and "last_user_uid" not in vals:
            vals = dict(vals)
            vals["last_user_uid"] = self.env.uid
            vals["last_user_date"] = fields.Datetime.now()

        if "stage_id" in vals:
            validation_stage = self.env.ref(
                "noc_helpdesk.helpdesk_ticket_stage_waiting",
                raise_if_not_found=False,
            )
            if validation_stage and vals["stage_id"] == validation_stage.id:
                vals.setdefault("validation_date", fields.Datetime.now())

            reopen_stage = self.env.ref(
                "noc_helpdesk.helpdesk_ticket_stage_reopen",
                raise_if_not_found=False,
            )
            if reopen_stage and vals["stage_id"] == reopen_stage.id:
                vals.setdefault("reopen_date", fields.Datetime.now())
                for ticket in self:
                    vals_with_count = dict(vals)
                    vals_with_count["reopen_count"] = ticket.reopen_count + 1
                    super(HelpdeskTicket, ticket).write(vals_with_count)
                if vals.keys() & _LIVE_UPDATE_FIELDS:
                    self._bus_notify_ticket_change("update")
                return True

            done_stage = self.env.ref(
                "helpdesk_mgmt.helpdesk_ticket_stage_done",
                raise_if_not_found=False,
            )
            if done_stage and vals["stage_id"] == done_stage.id:
                for ticket in self:
                    if not ticket.portal_type and not vals.get(
                        "failure_cause", ticket.failure_cause
                    ):
                        raise ValidationError(
                            _(
                                "Preencha o campo 'Causa da Falha'"
                                " antes de concluir o chamado."
                            )
                        )
                    if vals.get("traffic_restriction", ticket.traffic_restriction):
                        raise ValidationError(
                            _(
                                "Desative a 'Restrição de Tráfego'"
                                " antes de concluir o chamado."
                            )
                        )

        res = super().write(vals)

        if vals.keys() & _LIVE_UPDATE_FIELDS:
            self._bus_notify_ticket_change("update")

        return res

    def action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_share_on_teams(self):
        self.ensure_one()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        ticket_url = (
            f"{base_url}/web" f"#model=helpdesk.ticket&id={self.id}&view_type=form"
        )
        teams_url = (
            "https://teams.microsoft.com/share"
            f"?href={quote(ticket_url, safe='')}"
            f"&text={quote(f'Chamado #{self.id} - {self.name}', safe='')}"
            "&preview=true"
        )
        return {
            "type": "ir.actions.act_url",
            "url": teams_url,
            "target": "new",
        }

    def unlink(self):
        self._bus_notify_ticket_change("delete")
        return super().unlink()

    def message_post(self, **kwargs):
        subtype = kwargs.get("subtype_xmlid", "") or ""
        subtype_id = kwargs.get("subtype_id")

        is_internal_note = "note" in subtype

        if not is_internal_note and subtype_id:
            subtype_rec = self.env["mail.message.subtype"].browse(subtype_id)
            is_internal_note = subtype_rec.internal

        # Notas geradas ao concluir atividades carregam mail_activity_type_id;
        # a validação do ClarEnzo deve se aplicar apenas a notas manuais do chamado.
        is_activity_note = bool(kwargs.get("mail_activity_type_id"))

        is_plantao_note = self.env.context.get("plantao_message")

        if is_internal_note and not is_activity_note and not is_plantao_note:
            body = kwargs.get("body", "") or ""
            if not any(kw.upper() in body.upper() for kw in KEYWORDS):
                raise ValidationError(
                    _(
                        "A nota interna deve conter"
                        " o diagnóstico atualizado do ClarEnzo"
                    )
                )

            existing_notes = self.env["mail.message"].search(
                [
                    ("res_id", "=", self.id),
                    ("model", "=", self._name),
                    ("subtype_id.internal", "=", True),
                    ("body", "=", body),
                ],
                limit=1,
            )

            if existing_notes:
                raise ValidationError(
                    _(
                        "A nota interna deve conter"
                        " o diagnóstico atualizado do ClarEnzo"
                    )
                )

        result = super().message_post(**kwargs)

        if is_internal_note:
            self.write(
                {
                    "last_user_uid": self.env.uid,
                    "last_user_date": fields.Datetime.now(),
                }
            )

        return result

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        result = super().message_subscribe(
            partner_ids=partner_ids, subtype_ids=subtype_ids
        )
        if self.env.uid != SUPERUSER_ID:
            self.write(
                {
                    "last_user_uid": self.env.uid,
                    "last_user_date": fields.Datetime.now(),
                }
            )
        return result

    def _check_can_update_message_content(self, messages):
        if messages.tracking_value_ids:
            raise UserError(_("Messages with tracking values cannot be modified"))
        if any(message.message_type != "comment" for message in messages):
            raise UserError(
                _("Only messages type comment can have their content updated")
            )

    # -------------------------------------------------------------------------
    # CRON / MODEL METHODS
    # -------------------------------------------------------------------------

    @api.model
    def _get_support_team_users(self):
        """Retorna os usuários membros do time helpdesk_team_support.
        Se o time não tiver membros, retorna todos os usuários internos ativos."""
        team = self.env.ref(
            "noc_helpdesk.helpdesk_team_support", raise_if_not_found=False
        )
        if team and team.user_ids:
            return team.user_ids
        return (
            self.env["res.users"]
            .sudo()
            .search([("share", "=", False), ("active", "=", True)])
        )

    @api.model
    def _is_current_user_in_support_team(self):
        """Retorna True se o usuário atual é membro do time helpdesk_team_support.
        Se o time não tiver membros, qualquer usuário interno é considerado membro."""
        return self.env.user in self._get_support_team_users()

    # -------------------------------------------------------------------------
    # PLANTÃO
    # -------------------------------------------------------------------------

    @api.model
    def _get_shift_hours(self):
        """Retorna (day_start_hour, night_start_hour) lidos das configurações."""
        ICP = self.env["ir.config_parameter"].sudo()
        day_h = int(ICP.get_param("noc_helpdesk.shift_day_start_hour", 7))
        night_h = int(ICP.get_param("noc_helpdesk.shift_night_start_hour", 19))
        return day_h, night_h

    @api.model
    def _get_current_shift_start(self):
        """Retorna o datetime UTC do início do turno corrente."""
        day_h, night_h = self._get_shift_hours()
        try:
            tz_name = self.env.company.timezone or "UTC"
        except AttributeError:
            tz_name = "UTC"
        tz = timezone(tz_name)
        now_utc = fields.Datetime.now()
        now_local = utc.localize(now_utc).astimezone(tz)
        if day_h <= now_local.hour < night_h:
            shift_local = now_local.replace(
                hour=day_h, minute=0, second=0, microsecond=0
            )
        elif now_local.hour >= night_h:
            shift_local = now_local.replace(
                hour=night_h, minute=0, second=0, microsecond=0
            )
        else:
            yesterday = now_local - timedelta(days=1)
            shift_local = yesterday.replace(
                hour=night_h, minute=0, second=0, microsecond=0
            )
        return shift_local.astimezone(utc).replace(tzinfo=None)

    @api.model
    def _get_current_shift_plantao(self):
        """Retorna o registro helpdesk.plantao do turno atual, se houver."""
        shift_start = self._get_current_shift_start()
        return (
            self.env["helpdesk.plantao"]
            .sudo()
            .search([("start_datetime", ">=", shift_start)], limit=1)
        )

    @api.model
    def _is_in_shift_change_window(self):
        """True se estivermos dentro da janela configurada após o início do turno."""
        ICP = self.env["ir.config_parameter"].sudo()
        window = int(ICP.get_param("noc_helpdesk.shift_change_window_minutes", 30))
        now = fields.Datetime.now()
        shift_start = self._get_current_shift_start()
        return (now - shift_start).total_seconds() / 60 < window

    @api.model
    def _get_duty_entry_from_escala(self):
        """Retorna o registro helpdesk.escala do turno atual, ou vazio.
        O tipo de semana (Cheia/Vazia) alterna toda segunda-feira às 07h com base
        na segunda-feira de referência configurada em helpdesk.escala.config.
        Dias pesados (Seg/Qua/Sex/Sáb/Dom) recebem o tipo da semana atual;
        dias leves (Ter/Qui) recebem o tipo oposto."""
        try:
            tz_name = self.env.company.timezone or "UTC"
        except AttributeError:
            tz_name = "UTC"
        tz = timezone(tz_name)
        now_local = utc.localize(fields.Datetime.now()).astimezone(tz)

        day_h, night_h = self._get_shift_hours()

        # Turno noturno cruza a meia-noite;
        # antes do turno diurno ainda é o turno de ontem
        if 0 <= now_local.hour < day_h:
            logical_date = (now_local - timedelta(days=1)).date()
        else:
            logical_date = now_local.date()

        monday_of_week = logical_date - timedelta(days=logical_date.weekday())

        config = self.env["helpdesk.escala.config"].sudo().get_config()
        if config and config.reference_monday:
            weeks_offset = (monday_of_week - config.reference_monday).days // 7
            is_cheia_week = weeks_offset % 2 == 0
        else:
            is_cheia_week = True  # sem config, trata como semana cheia

        if logical_date.weekday() in CHEIA_WEEKDAYS:
            current_week_type = "cheia" if is_cheia_week else "vazia"
        else:
            current_week_type = "vazia" if is_cheia_week else "cheia"

        current_shift = "day" if day_h <= now_local.hour < night_h else "night"

        return (
            self.env["helpdesk.escala"]
            .sudo()
            .search(
                [("week_type", "=", current_week_type), ("shift", "=", current_shift)],
                limit=1,
            )
        )

    @api.model
    def _get_duty_user_from_escala(self):
        """Retorna o 1º responsável da escala do turno atual, ou recordset vazio."""
        entry = self._get_duty_entry_from_escala()
        if not entry:
            return self.env["res.users"]
        user1, _ = entry.get_effective_users()
        return user1

    @api.model
    def get_current_plantao_user(self):
        """Retorna o res.users de plantão:
        1. Plantão assumido manualmente no turno atual
        2. 1º responsável da escala automática
        3. Último plantão registrado"""
        plantao = self._get_current_shift_plantao()
        if plantao:
            return plantao.user_id
        escala_user = self._get_duty_user_from_escala()
        if escala_user:
            return escala_user
        last_plantao = self.env["helpdesk.plantao"].sudo().search([], limit=1)
        return last_plantao.user_id if last_plantao else self.env["res.users"]

    @api.model
    def _auto_assumir_plantao(self, user1, user2=None):
        """Assume o plantão automaticamente com base na escala."""
        now = fields.Datetime.now()
        self.env["helpdesk.plantao"].sudo().create(
            {"user_id": user1.id, "start_datetime": now}
        )

        try:
            tz_name = self.env.company.timezone or "UTC"
        except AttributeError:
            tz_name = "UTC"
        tz = timezone(tz_name)
        now_local = utc.localize(now).astimezone(tz)
        formatted_date = now_local.strftime("%d/%m/%Y %H:%M")

        names = user1.name
        if user2:
            names = f"{user1.name} e {user2.name}"
        message_body = (
            f"Plantão assumido automaticamente por <b>{names}</b> em {formatted_date}."
        )

        ticket_vals = {"user_id": user1.id, "user2_id": user2.id if user2 else False}
        open_tickets = self.sudo().search([("stage_id.closed", "=", False)])
        for ticket in open_tickets:
            ticket.with_context(tracking_disable=True).write(ticket_vals)
            ticket.sudo().with_context(plantao_message=True).message_post(
                body=message_body,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

        bus = self.env["bus.bus"].sudo()
        for u in self._get_support_team_users():
            if u.partner_id:
                bus._sendone(
                    u.partner_id,
                    "noc_helpdesk/plantao_assumed",
                    {"user_name": names, "user_id": user1.id},
                )

    @api.model
    def get_plantao_shift_alert_for_current_user(self):
        """Verifica se o usuário deve ver o popup de plantão ao carregar a página."""
        if not self._is_current_user_in_support_team():
            return {"show": False}
        if not self._is_in_shift_change_window():
            return {"show": False}
        if self._get_current_shift_plantao():
            return {"show": False}
        return {"show": True}

    @api.model
    def action_assumir_plantao(self):
        """Registra o plantão, atualiza tickets abertos e posta mensagem no chatter."""
        user = self.env.user
        now = fields.Datetime.now()
        self.env["helpdesk.plantao"].sudo().create(
            {"user_id": user.id, "start_datetime": now}
        )

        try:
            tz_name = self.env.company.timezone or "UTC"
        except AttributeError:
            tz_name = "UTC"
        tz = timezone(tz_name)
        now_local = utc.localize(now).astimezone(tz)
        formatted_date = now_local.strftime("%d/%m/%Y %H:%M")
        message_body = f"<b>{user.name}</b> assumiu o plantão em {formatted_date}."

        open_tickets = self.sudo().search([("stage_id.closed", "=", False)])
        for ticket in open_tickets:
            ticket.with_context(tracking_disable=True).write(
                {"user_id": user.id, "user2_id": False}
            )
            ticket.sudo().with_context(plantao_message=True).message_post(
                body=message_body,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )

        bus = self.env["bus.bus"].sudo()
        for u in self._get_support_team_users():
            if u.partner_id:
                bus._sendone(
                    u.partner_id,
                    "noc_helpdesk/plantao_assumed",
                    {"user_name": user.name, "user_id": user.id},
                )
        return {"user_name": user.name}

    @api.model
    def cron_notify_plantao_shift_change(self):
        """A cada minuto, verifica se é hora de trocar o plantão.
        Se a escala automática estiver configurada, assume o plantão automaticamente.
        Caso contrário, notifica o time para assumir manualmente."""
        try:
            tz_name = self.env.company.timezone or "UTC"
        except AttributeError:
            tz_name = "UTC"
        tz = timezone(tz_name)
        now_utc = fields.Datetime.now()
        now_local = utc.localize(now_utc).astimezone(tz)
        day_h, night_h = self._get_shift_hours()
        if now_local.hour not in (day_h, night_h) or now_local.minute != 0:
            return
        if self._get_current_shift_plantao():
            return

        entry = self._get_duty_entry_from_escala()
        if entry:
            user1, user2 = entry.get_effective_users()
            self._auto_assumir_plantao(user1, user2)
            return

        bus = self.env["bus.bus"].sudo()
        for user in self._get_support_team_users():
            if user.partner_id:
                bus._sendone(user.partner_id, "noc_helpdesk/plantao_alert", {})

    @api.model
    def _get_inactive_tickets_for_alert(self):
        """Retorna tickets inativos respeitando o limite individual por tipo de tag.
        Exclui tickets sem limite definido (sinergia, sistemas_ti, sem tag).
        Apenas notifica chamados nos estágios:
        Novo, Aguardando Operadora e Visita Técnica.
        """
        now = fields.Datetime.now()
        allowed_stage_xmlids = [
            "helpdesk_mgmt.helpdesk_ticket_stage_new",
            "noc_helpdesk.helpdesk_ticket_stage_waiting_provider",
            "noc_helpdesk.helpdesk_ticket_stage_visit",
        ]
        allowed_stage_ids = [
            stage.id
            for xmlid in allowed_stage_xmlids
            for stage in [self.env.ref(xmlid, raise_if_not_found=False)]
            if stage
        ]
        if not allowed_stage_ids:
            return self.browse()

        base_domain = [
            ("user_id", "!=", False),
            ("inactivity_limit_minutes", ">", 0),
            ("stage_id", "in", allowed_stage_ids),
        ]

        candidates = self.sudo().search(base_domain)

        visit_stage = self.env.ref(
            "noc_helpdesk.helpdesk_ticket_stage_visit", raise_if_not_found=False
        )

        return candidates.filtered(
            lambda t: t.write_date
            and (now - t.write_date).total_seconds() / 60 >= t.inactivity_limit_minutes
            and not (
                visit_stage
                and t.stage_id == visit_stage
                and t.visit_date_time
                and t.visit_date_time > now
            )
        )

    @api.model
    def get_inactivity_alert_payload_for_current_user(self):
        """Retorna tickets inativos do usuário atual para popup no carregamento.
        Se houver plantão ativo, apenas o usuário de plantão recebe os alertas."""
        current_user = self.env.user
        if not current_user or not self._is_current_user_in_support_team():
            return {"tickets": []}

        plantao_user = self.get_current_plantao_user()
        if plantao_user and current_user != plantao_user:
            return {"tickets": []}

        tickets = self._get_inactive_tickets_for_alert().filtered(
            lambda t: t.user_id.id == current_user.id
        )
        return {
            "tickets": [
                {
                    "ticket_id": t.id,
                    "ticket_name": t.display_name,
                    "alert_key": f"{t.id}: {t.write_date}",
                    "inactivity_minutes": t.inactivity_limit_minutes,
                }
                for t in tickets
            ],
        }

    @api.model
    def cron_notify_inactive_tickets(self):
        """Notifica sobre tickets inativos além do limite por tipo de tag.
        Se houver plantão ativo, notifica apenas o usuário de plantão."""
        tickets = self._get_inactive_tickets_for_alert()
        if not tickets:
            return

        tickets_payload = [
            {
                "ticket_id": t.id,
                "ticket_name": t.display_name,
                "alert_key": f"{t.id}: {t.write_date}",
                "inactivity_minutes": t.inactivity_limit_minutes,
            }
            for t in tickets
        ]

        bus = self.env["bus.bus"].sudo()
        plantao_user = self.get_current_plantao_user()

        if plantao_user:
            if plantao_user.partner_id:
                bus._sendone(
                    plantao_user.partner_id,
                    "noc_helpdesk/inactivity_alert",
                    {"tickets": tickets_payload},
                )
        else:
            for user in self._get_support_team_users():
                if not user.partner_id:
                    continue
                bus._sendone(
                    user.partner_id,
                    "noc_helpdesk/inactivity_alert",
                    {"tickets": tickets_payload},
                )

    @api.model
    def _get_new_ticket_check_interval(self):
        """Retorna o intervalo (minutos) de verificação de novos chamados."""
        ICP = self.env["ir.config_parameter"].sudo()
        return int(
            ICP.get_param(
                "noc_helpdesk.new_ticket_check_interval_minutes",
                _NEW_TICKET_CHECK_INTERVAL_DEFAULT,
            )
        )

    @api.model
    def _get_new_tickets_domain(self):
        last_check = fields.Datetime.now() - timedelta(
            minutes=self._get_new_ticket_check_interval()
        )
        new_stage = self.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_stage_new",
            raise_if_not_found=False,
        )
        domain = [
            ("user_id", "=", False),
            ("create_date", ">=", last_check),
        ]
        if new_stage:
            domain.append(("stage_id", "=", new_stage.id))
        return domain

    @api.model
    def get_new_tickets_alert_payload_for_current_user(self):
        """Return new unassigned tickets for immediate popup on page load."""
        current_user = self.env.user
        if not current_user or not self._is_current_user_in_support_team():
            return {
                "check_interval_minutes": self._get_new_ticket_check_interval(),
                "tickets": [],
            }

        tickets = self.sudo().search(self._get_new_tickets_domain())
        return {
            "check_interval_minutes": self._get_new_ticket_check_interval(),
            "tickets": [
                {
                    "ticket_id": ticket.id,
                    "ticket_name": ticket.display_name,
                    "alert_key": f"{ticket.id}: {ticket.create_date}",
                }
                for ticket in tickets
            ],
        }

    @api.model
    def cron_notify_new_tickets(self):
        """Notify ALL users about new tickets created in the last interval."""
        tickets = self.sudo().search(self._get_new_tickets_domain())
        if not tickets:
            return

        tickets_payload = [
            {
                "ticket_id": ticket.id,
                "ticket_name": ticket.display_name,
                "alert_key": f"{ticket.id}: {ticket.create_date}",
            }
            for ticket in tickets
        ]

        team_users = self._get_support_team_users()
        bus = self.env["bus.bus"].sudo()

        for user in team_users:
            if not user.partner_id:
                continue
            bus._sendone(
                user.partner_id,
                "noc_helpdesk/new_ticket_alert",
                {
                    "check_interval_minutes": self._get_new_ticket_check_interval(),
                    "tickets": tickets_payload,
                },
            )

    @api.model
    def action_force_escala_plantao(self):
        """Força a assumção de plantão pela escala agora, sem esperar o cron."""
        entry = self._get_duty_entry_from_escala()
        if not entry:
            raise UserError(
                _(
                    "Nenhuma entrada de escala encontrada para o turno atual."
                    " Verifique a configuração."
                )
            )
        user1, user2 = entry.get_effective_users()
        self._auto_assumir_plantao(user1, user2)
        names = f"{user1.name} e {user2.name}"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Plantão assumido"),
                "message": _("Plantão atribuído a %(names)s.", names=names),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def action_reassign_odoobot_tickets(self):
        """Reatribui tickets abertos com OdooBot para o último responsável de plantão.
        Se não houver plantão cadastrado, usa o usuário que executou a ação."""
        plantao_user = self.get_current_plantao_user()
        if not plantao_user:
            plantao_user = self.env.user

        odoobot_tickets = self.sudo().search(
            [("stage_id.closed", "=", False), ("user_id", "=", SUPERUSER_ID)]
        )

        count = len(odoobot_tickets)
        if odoobot_tickets:
            odoobot_tickets.with_context(tracking_disable=True).write(
                {"user_id": plantao_user.id}
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reatribuição concluída"),
                "message": _(
                    "%(count)s chamado(s) reatribuído(s) para %(name)s.",
                    count=count,
                    name=plantao_user.name,
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def cron_notify_manutencao_programada(self):
        """Notifica TODOS os usuários internos sobre início e fim de
        manutenções programadas cujo horário está dentro da janela do último minuto."""
        now = fields.Datetime.now()
        window_start = now - timedelta(minutes=1)

        def ref(xml_id):
            return self.env.ref(f"noc_helpdesk.{xml_id}", raise_if_not_found=False)

        tags_to_notify = [
            ref("helpdesk_ticket_tag_manutencao_programada"),
            ref("helpdesk_ticket_tag_fanp"),
            ref("helpdesk_ticket_tag_fap"),
            ref("helpdesk_ticket_tag_fape"),
            ref("helpdesk_ticket_tag_fapi"),
        ]
        tag_ids = [t.id for t in tags_to_notify if t]
        if not tag_ids:
            return

        candidates = self.sudo().search([("tag_id", "in", tag_ids)])

        start_tickets = candidates.filtered(
            lambda t: t.activity_start_datetime
            and window_start <= t.activity_start_datetime <= now
        )
        end_tickets = candidates.filtered(
            lambda t: t.activity_end_datetime
            and window_start <= t.activity_end_datetime <= now
        )

        if not start_tickets and not end_tickets:
            return

        all_users = self.env["res.users"].sudo().search([("share", "=", False)])
        bus = self.env["bus.bus"].sudo()

        for ticket in start_tickets:
            payload = {
                "ticket_id": ticket.id,
                "ticket_name": ticket.display_name,
                "event": "start",
                "datetime": fields.Datetime.to_string(ticket.activity_start_datetime),
            }
            for user in all_users:
                if not user.partner_id:
                    continue
                bus._sendone(
                    user.partner_id,
                    "noc_helpdesk/manutencao_alert",
                    payload,
                )

        for ticket in end_tickets:
            payload = {
                "ticket_id": ticket.id,
                "ticket_name": ticket.display_name,
                "event": "end",
                "datetime": fields.Datetime.to_string(ticket.activity_end_datetime),
            }
            for user in all_users:
                if not user.partner_id:
                    continue
                bus._sendone(
                    user.partner_id,
                    "noc_helpdesk/manutencao_alert",
                    payload,
                )
