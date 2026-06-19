from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("noc_base", "post_install", "-at_install")
class TestNetworkMonitorLog(TransactionCase):
    """Testes para network.monitor.log — noc_network_monitor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.team = cls.env["helpdesk.ticket.team"].search([], limit=1)

        cls.origin = cls.env["network.equipment"].create(
            {
                "name": "Eq Mon Origem",
                "equipment_type": "switch",
                "ip_address": "10.10.0.1",
            }
        )
        cls.destination = cls.env["network.equipment"].create(
            {
                "name": "Eq Mon Destino",
                "equipment_type": "router",
                "ip_address": "10.10.0.2",
            }
        )
        cls.provider = cls.env["res.partner"].create(
            {"name": "Provedora Monitor", "noc_type": "provider"}
        )
        cls.circuit = cls.env["network.circuit"].create(
            {
                "code": "MON-CRC-001",
                "name": "Circuito Monitor",
                "origin_id": cls.origin.id,
                "destination_id": cls.destination.id,
                "origin_interface": "eth0",
                "destination_interface": "eth1",
                "provider_id": cls.provider.id,
            }
        )

        # Referências das tags
        cls.tag_unavailable = cls.env.ref(
            "noc_helpdesk.helpdesk_ticket_tag_unavailable",
            raise_if_not_found=False,
        )
        cls.tag_latency = cls.env.ref(
            "noc_helpdesk.helpdesk_ticket_tag_high_latency",
            raise_if_not_found=False,
        )
        cls.tag_discarded = cls.env.ref(
            "noc_helpdesk.helpdesk_ticket_tag_discarded_packet",
            raise_if_not_found=False,
        )

    def _make_item(self, ping=False, latency=False, lpkts=False):
        """Helper: retorna um dict simulando um item do JSON do monitor."""
        return {
            "code_db": "MON-CRC-001",
            "source": "10.10.0.1",
            "destiny": "10.10.0.2",
            "send_packets": 10,
            "receive_packets": 8,
            "round_trip_min_ms": 1.0,
            "round_trip_avg_ms": 5.0,
            "round_trip_max_ms": 20.0,
            "latency_threshold": 100.0,
            "ping_status": "ping_down" if ping else "ping_up",
            "show_ping_alarm": ping,
            "show_latency_alarm": latency,
            "show_lpkts_alarm": lpkts,
        }

    # ------------------------------------------------------------------
    # _compute_packet_loss
    # ------------------------------------------------------------------

    def test_packet_loss_computed_correctly(self):
        """packet_loss_pct deve ser (send - receive) / send * 100."""
        log = self.env["network.monitor.log"].create(
            {
                "circuit_code": "MON-CRC-001",
                "send_packets": 10,
                "receive_packets": 8,
                "round_trip_avg_ms": 5.0,
            }
        )
        self.assertAlmostEqual(log.packet_loss_pct, 20.0)

    def test_packet_loss_zero_when_no_packets_sent(self):
        """Sem pacotes enviados, packet_loss_pct deve ser 0."""
        log = self.env["network.monitor.log"].create(
            {
                "circuit_code": "MON-CRC-001",
                "send_packets": 0,
                "receive_packets": 0,
            }
        )
        self.assertEqual(log.packet_loss_pct, 0.0)

    # ------------------------------------------------------------------
    # _get_dominant_alarm
    # ------------------------------------------------------------------

    def test_dominant_alarm_ping_wins_over_latency(self):
        """ping (prioridade 1) deve ganhar de latency (prioridade 3)."""
        Log = self.env["network.monitor.log"]
        item = self._make_item(ping=True, latency=True)
        result = Log._get_dominant_alarm(item)
        self.assertEqual(result, "ping")

    def test_dominant_alarm_ping_wins_over_lpkts(self):
        """ping (prioridade 1) deve ganhar de lpkts (prioridade 2)."""
        Log = self.env["network.monitor.log"]
        item = self._make_item(ping=True, lpkts=True)
        result = Log._get_dominant_alarm(item)
        self.assertEqual(result, "ping")

    def test_dominant_alarm_lpkts_wins_over_latency(self):
        """lpkts (prioridade 2) deve ganhar de latency (prioridade 3)."""
        Log = self.env["network.monitor.log"]
        item = self._make_item(lpkts=True, latency=True)
        result = Log._get_dominant_alarm(item)
        self.assertEqual(result, "lpkts")

    def test_dominant_alarm_none_when_no_alarm(self):
        """Sem alarmes ativos, deve retornar None."""
        Log = self.env["network.monitor.log"]
        item = self._make_item()
        result = Log._get_dominant_alarm(item)
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # _process_result — criação de ticket
    # ------------------------------------------------------------------

    def test_process_result_creates_ticket_on_alarm(self):
        """Resultado com alarme ativo deve criar um chamado."""
        Log = self.env["network.monitor.log"]
        item = self._make_item(ping=True)
        Log._process_result(item)

        ticket = self.env["helpdesk.ticket"].search(
            [
                ("circuit_id", "=", self.circuit.id),
                ("monitor_origin", "=", "network_monitor"),
            ],
            limit=1,
        )
        self.assertTrue(ticket, "Chamado não foi criado pelo monitor")
        self.assertEqual(ticket.name, "Queda de Link")

    def test_process_result_no_duplicate_ticket(self):
        """Segundo alarme no mesmo circuito não deve criar novo ticket."""
        Log = self.env["network.monitor.log"]
        item = self._make_item(ping=True)

        Log._process_result(item)
        Log._process_result(item)

        tickets = self.env["helpdesk.ticket"].search(
            [
                ("circuit_id", "=", self.circuit.id),
                ("monitor_origin", "=", "network_monitor"),
            ]
        )
        self.assertEqual(len(tickets), 1, "Dois alarmes criaram tickets duplicados")

    def test_process_result_no_ticket_on_normalization(self):
        """Resultado sem alarme não deve criar chamado se não há ticket aberto."""
        Log = self.env["network.monitor.log"]
        # Garante que não há ticket aberto para este circuito antes do teste
        existing = self.env["helpdesk.ticket"].search(
            [
                ("circuit_id", "=", self.circuit.id),
                ("monitor_origin", "=", "network_monitor"),
            ]
        )
        existing.write(
            {
                "stage_id": self.env.ref(
                    "helpdesk_mgmt.helpdesk_ticket_stage_done",
                    raise_if_not_found=False,
                ).id
            }
        )
        count_before = self.env["helpdesk.ticket"].search_count(
            [
                ("circuit_id", "=", self.circuit.id),
                ("monitor_origin", "=", "network_monitor"),
            ]
        )
        item = self._make_item()  # sem alarme
        Log._process_result(item)

        count_after = self.env["helpdesk.ticket"].search_count(
            [
                ("circuit_id", "=", self.circuit.id),
                ("monitor_origin", "=", "network_monitor"),
            ]
        )
        self.assertEqual(
            count_before, count_after, "Normalização criou ticket indevido"
        )

    # ------------------------------------------------------------------
    # _escalate_ticket_if_needed
    # ------------------------------------------------------------------

    def test_escalate_updates_tag_when_more_severe(self):
        """Alarme mais grave deve atualizar a tag do ticket aberto."""
        if not self.tag_latency or not self.tag_unavailable:
            self.skipTest("Tags necessárias não encontradas")

        Log = self.env["network.monitor.log"]

        # Cria ticket com latência (prioridade 3)
        item_latency = self._make_item(latency=True)
        Log._process_result(item_latency)

        ticket = self.env["helpdesk.ticket"].search(
            [
                ("circuit_id", "=", self.circuit.id),
                ("monitor_origin", "=", "network_monitor"),
            ],
            limit=1,
        )
        self.assertTrue(ticket)

        # Escalona para ping (prioridade 1)
        item_ping = self._make_item(ping=True)
        Log._process_result(item_ping)

        ticket.invalidate_recordset()
        self.assertEqual(ticket.tag_id, self.tag_unavailable)

    # ------------------------------------------------------------------
    # _invalidate_ticket_latency_graph
    # ------------------------------------------------------------------

    def test_invalidate_ticket_latency_graph_does_not_raise(self):
        """_invalidate_ticket_latency_graph não deve lançar exceção."""
        team = self.env["helpdesk.ticket.team"].search([], limit=1)
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Ticket Invalidação",
                "team_id": team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        # Não deve lançar exceção mesmo se os campos de gráfico não existirem
        self.env["network.monitor.log"]._invalidate_ticket_latency_graph([ticket.id])
