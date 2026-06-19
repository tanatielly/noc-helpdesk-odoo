import logging
from datetime import timedelta

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Mapeamento alarme JSON → XMLID da tag já existente no noc_helpdesk
ALARM_TAG_MAP = {
    "ping": "noc_helpdesk.helpdesk_ticket_tag_unavailable",
    "latency": "noc_helpdesk.helpdesk_ticket_tag_high_latency",
    "lpkts": "noc_helpdesk.helpdesk_ticket_tag_discarded_packet",
}

# Prioridade de escalonamento (menor = mais grave)
ALARM_PRIORITY = {"ping": 1, "latency": 3, "lpkts": 2}


class NetworkMonitorLog(models.Model):
    """Registro de cada resultado recebido do servidor de monitoramento."""

    _name = "network.monitor.log"
    _description = "Log de Monitoramento de Rede"
    _order = "collected_at desc"
    _rec_name = "circuit_code"

    # ------------------------------------------------------------------
    # FIELDS — dados brutos do JSON
    # ------------------------------------------------------------------

    collected_at = fields.Datetime(
        string="Coletado em",
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    circuit_code = fields.Char(
        string="Código do Circuito (code_db)",
        readonly=True,
        index=True,
    )
    circuit_id = fields.Many2one(
        comodel_name="network.circuit",
        string="Circuito",
        readonly=True,
        ondelete="set null",
        index=True,
    )

    source_ip = fields.Char(string="IP Origem", readonly=True)
    destiny_ip = fields.Char(string="IP Destino", readonly=True)

    send_packets = fields.Integer(string="Pacotes Enviados", readonly=True)
    receive_packets = fields.Integer(string="Pacotes Recebidos", readonly=True)
    packet_loss_pct = fields.Float(
        string="Perda de Pacotes (%)",
        compute="_compute_packet_loss",
        store=True,
    )

    round_trip_min_ms = fields.Float(string="RTT Mín (ms)", readonly=True)
    round_trip_avg_ms = fields.Float(string="RTT Méd (ms)", readonly=True)
    round_trip_max_ms = fields.Float(string="RTT Máx (ms)", readonly=True)
    latency_threshold = fields.Float(string="Threshold Latência (ms)", readonly=True)

    ping_status = fields.Selection(
        selection=[("ping_up", "Up"), ("ping_down", "Down")],
        string="Status Ping",
        readonly=True,
    )
    show_ping_alarm = fields.Boolean(string="Alarme Ping", readonly=True)
    show_latency_alarm = fields.Boolean(string="Alarme Latência", readonly=True)
    show_lpkts_alarm = fields.Boolean(string="Alarme Perda de Pacotes", readonly=True)

    ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket",
        string="Chamado Relacionado",
        readonly=True,
        ondelete="set null",
    )

    # ------------------------------------------------------------------
    # COMPUTE
    # ------------------------------------------------------------------

    @api.depends("send_packets", "receive_packets")
    def _compute_packet_loss(self):
        for rec in self:
            if rec.send_packets:
                lost = rec.send_packets - rec.receive_packets
                rec.packet_loss_pct = (lost / rec.send_packets) * 100
            else:
                rec.packet_loss_pct = 0.0

    # ------------------------------------------------------------------
    # CRON ENTRY POINT
    # ------------------------------------------------------------------

    @api.model
    def cron_pull_monitor(self):
        """Ponto de entrada do ir.cron —
        faz o pull e processa os resultados."""
        ICP = self.env["ir.config_parameter"].sudo()
        url = ICP.get_param("noc_network_monitor.url", "")
        token = ICP.get_param("noc_network_monitor.token", "")

        if not url:
            _logger.warning(
                "noc_network_monitor: URL do servidor não configurada. "
                "Acesse Configurações > Monitor de Rede."
            )
            return

        try:
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            _logger.error("noc_network_monitor: Erro ao consultar servidor — %s", exc)
            return
        except ValueError as exc:
            _logger.error("noc_network_monitor: Resposta não é JSON válido — %s", exc)
            return

        # Aceita tanto lista quanto envelope {"results": [...]}
        if isinstance(data, dict):
            results = data.get("results", data.get("data", [data]))
        else:
            results = data

        for item in results:
            try:
                self._process_result(item)
            except Exception as exc:
                _logger.error(
                    "noc_network_monitor: Erro ao processar item %s — %s",
                    item.get("code_db"),
                    exc,
                )

    # ------------------------------------------------------------------
    # PROCESSAMENTO DE CADA ITEM DO JSON
    # ------------------------------------------------------------------

    @api.model
    def _process_result(self, item):
        """Processa um único resultado do JSON e gerencia o ticket."""
        code_db = item.get("code_db", "")
        if not code_db:
            _logger.warning("noc_network_monitor: item sem code_db — ignorado.")
            return

        # Busca o circuito pelo código
        circuit = self.env["network.circuit"].search([("code", "=", code_db)], limit=1)
        if not circuit:
            _logger.warning(
                "noc_network_monitor: Circuito '%s' não encontrado no Odoo.", code_db
            )

        # Cria o log da coleta
        log = self.create(
            {
                "circuit_code": code_db,
                "circuit_id": circuit.id if circuit else False,
                "source_ip": item.get("source", ""),
                "destiny_ip": item.get("destiny", ""),
                "send_packets": item.get("send_packets", 0),
                "receive_packets": item.get("receive_packets", 0),
                "round_trip_min_ms": item.get("round_trip_min_ms", 0.0),
                "round_trip_avg_ms": item.get("round_trip_avg_ms", 0.0),
                "round_trip_max_ms": item.get("round_trip_max_ms", 0.0),
                "latency_threshold": item.get("latency_threshold", 0.0),
                "ping_status": item.get("ping_status", "ping_up"),
                "show_ping_alarm": bool(item.get("show_ping_alarm", False)),
                "show_latency_alarm": bool(item.get("show_latency_alarm", False)),
                "show_lpkts_alarm": bool(item.get("show_lpkts_alarm", False)),
            }
        )

        # Determina o alarme ativo mais grave
        active_alarm = self._get_dominant_alarm(item)

        if active_alarm:
            self._handle_alarm(log, circuit, active_alarm)
        else:
            self._handle_normalization(log, circuit)

    # ------------------------------------------------------------------
    # LÓGICA DE ALARMES
    # ------------------------------------------------------------------

    @api.model
    def _get_dominant_alarm(self, item):
        """Retorna o tipo do alarme mais grave ativo, ou None se não houver."""
        active = []
        if item.get("show_ping_alarm"):
            active.append("ping")
        if item.get("show_lpkts_alarm"):
            active.append("lpkts")
        if item.get("show_latency_alarm"):
            active.append("latency")

        if not active:
            return None
        # Retorna o mais grave (menor prioridade numérica)
        return min(active, key=lambda a: ALARM_PRIORITY[a])

    @api.model
    def _get_tag(self, alarm_type):
        """Retorna o record da tag correspondente ao tipo de alarme."""
        xmlid = ALARM_TAG_MAP.get(alarm_type)
        if not xmlid:
            return False
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.model
    def _handle_alarm(self, log, circuit, alarm_type):
        """Abre ou atualiza um chamado para o circuito com alarme."""
        if not circuit:
            return

        ICP = self.env["ir.config_parameter"].sudo()
        reopen_hours = int(ICP.get_param("noc_network_monitor.reopen_window", 6))
        tag = self._get_tag(alarm_type)

        # Busca chamado aberto para este circuito
        open_ticket = self._find_open_ticket(circuit)

        if open_ticket:
            self._escalate_ticket_if_needed(open_ticket, alarm_type, tag)
            log.ticket_id = open_ticket
            return

        # Busca chamado fechado recentemente para possível reabertura
        closed_ticket = self._find_recently_closed_ticket(circuit, reopen_hours)

        if closed_ticket:
            self._reopen_ticket(closed_ticket, alarm_type, tag, log=log)
            log.ticket_id = closed_ticket
            return

        # Cria novo chamado
        new_ticket = self._create_ticket(circuit, alarm_type, tag, log=log)
        log.ticket_id = new_ticket

    @api.model
    def _handle_normalization(self, log, circuit):
        """Marca o chamado aberto como normalizado para fechar após delay."""
        if not circuit:
            return

        open_ticket = self._find_open_ticket(circuit)
        if not open_ticket:
            return

        ICP = self.env["ir.config_parameter"].sudo()
        close_delay = int(ICP.get_param("noc_network_monitor.close_delay", 30))

        now = fields.Datetime.now()

        # Se ainda não tem hora de normalização, registra agora
        if not open_ticket.monitor_normalized_since:
            open_ticket.sudo().write({"monitor_normalized_since": now})
            body = _(
                "✅ <b>Circuito normalizado</b><br/>"
                "O monitoramento não detecta mais alarmes"
                " para este circuito.<br/>"
                "O chamado será fechado automaticamente"
                " em <b>%(minutes)s minutos</b> "
                "se a normalização se mantiver."
            )

            body = body % {
                "minutes": close_delay,
            }
            open_ticket.sudo().message_post(
                body=body,
                subtype_xmlid="mail.mt_comment",
            )
            log.ticket_id = open_ticket
            return

        # Verifica se já passou o delay configurado
        normalized_since = open_ticket.monitor_normalized_since
        if now >= normalized_since + timedelta(minutes=close_delay):
            self._close_ticket(open_ticket)

        log.ticket_id = open_ticket

    # ------------------------------------------------------------------
    # HELPERS DE TICKET
    # ------------------------------------------------------------------

    @api.model
    def _find_open_ticket(self, circuit):
        """Retorna o chamado aberto para o circuito, se houver."""
        done_stage = self.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_stage_done", raise_if_not_found=False
        )
        domain = [
            ("circuit_id", "=", circuit.id),
            ("monitor_origin", "=", "network_monitor"),
        ]
        if done_stage:
            domain.append(("stage_id", "!=", done_stage.id))
        return self.env["helpdesk.ticket"].sudo().search(domain, limit=1)

    @api.model
    def _find_recently_closed_ticket(self, circuit, reopen_hours):
        """Retorna chamado fechado dentro da janela de reabertura."""
        done_stage = self.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_stage_done", raise_if_not_found=False
        )
        if not done_stage:
            return False

        since = fields.Datetime.now() - timedelta(hours=reopen_hours)
        return (
            self.env["helpdesk.ticket"]
            .sudo()
            .search(
                [
                    ("circuit_id", "=", circuit.id),
                    ("monitor_origin", "=", "network_monitor"),
                    ("stage_id", "=", done_stage.id),
                    ("monitor_closed_at", ">=", since),
                ],
                limit=1,
                order="monitor_closed_at desc",
            )
        )

    # Mapeamento equipment_type → xmlid de categoria
    _EQUIPMENT_CATEGORY_MAP = {
        "switch": "noc_helpdesk.helpdesk_ticket_category_switch",
        "router": "noc_helpdesk.helpdesk_ticket_category_router",
        "access_point": "noc_helpdesk.helpdesk_ticket_category_ap",
    }

    @api.model
    def _get_category_id(self, circuit):
        """Retorna o id da categoria com base no equipment_type da origem."""
        eq_type = circuit.origin_id.equipment_type if circuit.origin_id else False
        xmlid = self._EQUIPMENT_CATEGORY_MAP.get(eq_type)
        if not xmlid:
            return False
        cat = self.env.ref(xmlid, raise_if_not_found=False)
        return cat.id if cat else False

    @api.model
    def _build_traffic_loss(self, log):
        """Formata o campo traffic_loss a partir dos dados do log."""
        return (
            f"{log.round_trip_max_ms} ms / {log.round_trip_avg_ms} ms"
            f" | {log.receive_packets} de {log.send_packets} pacotes recebidos"
        )

    @api.model
    def _create_ticket(self, circuit, alarm_type, tag, log=None):
        """Cria um novo chamado para o circuito."""
        ICP = self.env["ir.config_parameter"].sudo()
        team_id = int(ICP.get_param("noc_network_monitor.team_id", 0))

        new_stage = self.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_stage_new", raise_if_not_found=False
        )

        title_map = {
            "ping": _("Queda de Link"),
            "latency": _("Latência de Link"),
            "lpkts": _("Link com Descarte de Pacotes"),
        }

        vals = {
            "name": title_map.get(alarm_type, _("Alarme de Rede")),
            "circuit_id": circuit.id,
            "description": circuit.id,
            "net_origin_id": circuit.origin_id.id,
            "net_destination_id": circuit.destination_id.id,
            "tag_id": tag.id if tag else False,
            "monitor_origin": "network_monitor",
            "monitor_normalized_since": False,
            "monitor_closed_at": False,
            "provider_id": (circuit.provider_id.id if circuit.provider_id else False),
            "category_id": self._get_category_id(circuit),
        }
        if team_id:
            vals["team_id"] = team_id
        if new_stage:
            vals["stage_id"] = new_stage.id

        ticket = self.env["helpdesk.ticket"].sudo().create(vals)

        if log:
            ticket.sudo().write({"traffic_loss": self._build_traffic_loss(log)})

        body = _(
            "🔴 <b>Chamado aberto automaticamente"
            " pelo Monitor de Rede</b><br/>"
            "Circuito: <b>%(circuito)s</b><br/>"
            "Tipo de alarme: <b>%(tipo)s</b><br/>"
            "Origem: %(origem)s | Destino: %(destino)s"
        )

        body = body % {
            "circuito": circuit.display_name,
            "tipo": tag.name if tag else alarm_type,
            "origem": circuit.origin_id.name,
            "destino": circuit.destination_id.name,
        }

        ticket.message_post(
            body=body,
            subtype_xmlid="mail.mt_comment",
        )
        return ticket

    @api.model
    def _escalate_ticket_if_needed(self, ticket, alarm_type, tag):
        """Atualiza a tag se o novo alarme for mais grave que o atual."""
        current_priority = ALARM_PRIORITY.get(
            self._tag_to_alarm_type(ticket.tag_id), 9999
        )
        new_priority = ALARM_PRIORITY.get(alarm_type, 9999)

        if new_priority < current_priority:
            old_tag_name = ticket.tag_id.name if ticket.tag_id else _("sem tag")
            ticket.sudo().write(
                {
                    "tag_id": tag.id if tag else False,
                    # cancela normalização em curso
                    "monitor_normalized_since": False,
                }
            )
            body = _(
                "⬆️ <b>Escalonamento de alarme</b><br/>"
                "O circuito <b>%(circuito)s</b>"
                " escalou de <b>%(de)s</b> para <b>%(para)s</b>."
            )

            body = body % {
                "circuito": ticket.circuit_id.display_name,
                "de": old_tag_name,
                "para": tag.name if tag else alarm_type,
            }
            ticket.message_post(
                body=body,
                subtype_xmlid="mail.mt_comment",
            )

    @api.model
    def _reopen_ticket(self, ticket, alarm_type, tag, log=None):
        """Reabre um chamado fechado recentemente."""
        new_stage = self.env.ref(
            "noc_helpdesk.helpdesk_ticket_stage_reopen", raise_if_not_found=False
        )
        vals = {
            "tag_id": tag.id if tag else False,
            "monitor_normalized_since": False,
            "monitor_closed_at": False,
        }
        if log:
            vals["traffic_loss"] = self._build_traffic_loss(log)
        if new_stage:
            vals["stage_id"] = new_stage.id

        ticket.sudo().write(vals)
        body = _(
            "🔁 <b>Chamado reaberto automaticamente "
            "pelo Monitor de Rede</b><br/>"
            "O circuito <b>%(circuito)s</b> voltou a apresentar alarme do tipo "
            "<b>%(tipo)s</b> dentro da janela de reabertura."
        )

        body = body % {
            "circuito": ticket.circuit_id.display_name,
            "tipo": tag.name if tag else alarm_type,
        }
        ticket.message_post(
            body=body,
            subtype_xmlid="mail.mt_comment",
        )

    @api.model
    def _close_ticket(self, ticket):
        """Fecha o chamado normalizado."""
        done_stage = self.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_stage_done", raise_if_not_found=False
        )
        now = fields.Datetime.now()
        vals = {"monitor_closed_at": now}
        if done_stage:
            vals["stage_id"] = done_stage.id

        ticket.sudo().write(vals)
        body = _(
            "✅ <b>Chamado fechado automaticamente "
            "pelo Monitor de Rede</b><br/>"
            "O circuito <b>%(circuito)s</b> "
            "permaneceu normalizado pelo tempo configurado."
        )
        body = (
            body
            % {
                "circuito": ticket.circuit_id.display_name,
            },
        )
        ticket.message_post(
            body=body,
            subtype_xmlid="mail.mt_comment",
        )

    @api.model
    def _tag_to_alarm_type(self, tag):
        """Converte uma tag de volta para o tipo de alarme."""
        if not tag:
            return None
        for alarm_type, xmlid in ALARM_TAG_MAP.items():
            ref = self.env.ref(xmlid, raise_if_not_found=False)
            if ref and ref.id == tag.id:
                return alarm_type
        return None

    # ------------------------------------------------------------------
    # INVALIDACAO DO GRAFICO DE LATENCIA
    # ------------------------------------------------------------------

    def _invalidate_ticket_latency_graph(self, ticket_ids):
        """Invalida os campos computados de latencia nos chamados informados,
        forcando o grafico do noc_helpdesk_graphics a recalcular
        a partir dos logs mais recentes do monitor."""
        if not ticket_ids:
            return
        tickets = self.env["helpdesk.ticket"].browse(ticket_ids).filtered("id")
        if not tickets:
            return
        # Invalida somente os campos que existem no modelo
        # (noc_helpdesk_graphics pode nao estar instalado)
        fnames_to_invalidate = [
            f
            for f in [
                "latency_data_json",
                "latency_avg",
                "latency_max",
                "latency_min",
                "latency_last",
                "latency_samples",
            ]
            if f in self.env["helpdesk.ticket"]._fields
        ]
        if fnames_to_invalidate:
            tickets.invalidate_recordset(fnames=fnames_to_invalidate)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        ticket_ids = records.filtered("ticket_id").mapped("ticket_id").ids
        self._invalidate_ticket_latency_graph(ticket_ids)
        return records

    def write(self, vals):
        res = super().write(vals)
        if "round_trip_avg_ms" in vals or "collected_at" in vals or "ticket_id" in vals:
            ticket_ids = self.filtered("ticket_id").mapped("ticket_id").ids
            self._invalidate_ticket_latency_graph(ticket_ids)
        return res
