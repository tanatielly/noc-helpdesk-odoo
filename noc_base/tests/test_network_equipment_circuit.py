from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("noc_base", "post_install", "-at_install")
class TestNetworkEquipment(TransactionCase):
    """Testes para network.equipment — noc_network_monitor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.equipment_origin = cls.env["network.equipment"].create(
            {
                "name": "Switch Origem",
                "equipment_type": "switch",
                "ip_address": "192.168.1.1",
            }
        )
        cls.equipment_dest = cls.env["network.equipment"].create(
            {
                "name": "Roteador Destino",
                "equipment_type": "router",
                "ip_address": "192.168.1.2",
            }
        )

    # ------------------------------------------------------------------
    # _check_ip_address
    # ------------------------------------------------------------------

    def test_valid_ip_address(self):
        """IP no formato correto deve ser aceito sem exceção."""
        eq = self.env["network.equipment"].create(
            {
                "name": "Eq IP Válido",
                "equipment_type": "switch",
                "ip_address": "10.0.0.1",
            }
        )
        self.assertEqual(eq.ip_address, "10.0.0.1")

    def test_invalid_ip_address_raises(self):
        """IP fora do formato xxx.xxx.xxx.xxx deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["network.equipment"].create(
                {
                    "name": "Eq IP Inválido",
                    "equipment_type": "switch",
                    "ip_address": "999.999.999",
                }
            )

    def test_invalid_ip_letters_raises(self):
        """IP com letras deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["network.equipment"].create(
                {
                    "name": "Eq IP Letras",
                    "equipment_type": "switch",
                    "ip_address": "abc.def.ghi.jkl",
                }
            )

    # ------------------------------------------------------------------
    # _check_mac_address
    # ------------------------------------------------------------------

    def test_valid_mac_address(self):
        """MAC no formato correto deve ser aceito."""
        eq = self.env["network.equipment"].create(
            {
                "name": "Eq MAC Válido",
                "equipment_type": "switch",
                "ip_address": "10.0.0.2",
                "mac_address": "AA:BB:CC:DD:EE:FF",
            }
        )
        self.assertEqual(eq.mac_address, "AA:BB:CC:DD:EE:FF")

    def test_invalid_mac_address_raises(self):
        """MAC fora do formato AA:BB:CC:DD:EE:FF deve lançar ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["network.equipment"].create(
                {
                    "name": "Eq MAC Inválido",
                    "equipment_type": "switch",
                    "ip_address": "10.0.0.3",
                    "mac_address": "AABBCCDDEEGG",
                }
            )

    # ------------------------------------------------------------------
    # _compute_ticket_count
    # ------------------------------------------------------------------

    def test_ticket_count_increments(self):
        """ticket_count deve somar chamados como origem e destino."""
        team = self.env["helpdesk.ticket.team"].search([], limit=1)
        initial = self.equipment_origin.ticket_count
        self.env["helpdesk.ticket"].create(
            {
                "name": "Chamado Equip",
                "net_origin_id": self.equipment_origin.id,
                "team_id": team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.equipment_origin.invalidate_recordset()
        self.assertEqual(self.equipment_origin.ticket_count, initial + 1)

    # ------------------------------------------------------------------
    # action_set_maintenance / action_set_active
    # ------------------------------------------------------------------

    def test_action_set_maintenance(self):
        """action_set_maintenance deve alterar o status para 'maintenance'."""
        self.equipment_origin.action_set_maintenance()
        self.assertEqual(self.equipment_origin.status, "maintenance")

    def test_action_set_active(self):
        """action_set_active deve restaurar o status para 'active'."""
        self.equipment_origin.action_set_maintenance()
        self.equipment_origin.action_set_active()
        self.assertEqual(self.equipment_origin.status, "active")


class TestNetworkCircuit(TransactionCase):
    """Testes para network.circuit — noc_network_monitor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.origin = cls.env["network.equipment"].create(
            {
                "name": "Eq Origem",
                "equipment_type": "switch",
                "ip_address": "172.16.0.1",
            }
        )
        cls.destination = cls.env["network.equipment"].create(
            {
                "name": "Eq Destino",
                "equipment_type": "router",
                "ip_address": "172.16.0.2",
            }
        )
        cls.circuit = cls.env["network.circuit"].create(
            {
                "code": "CRC-TEST-001",
                "name": "Circuito Teste",
                "origin_id": cls.origin.id,
                "destination_id": cls.destination.id,
                "origin_interface": "eth0",
                "destination_interface": "eth1",
            }
        )

    # ------------------------------------------------------------------
    # _compute_display_name
    # ------------------------------------------------------------------

    def test_display_name_with_name(self):
        """display_name deve ser 'CODE — nome' quando name está preenchido."""
        self.assertEqual(self.circuit.display_name, "CRC-TEST-001 — Circuito Teste")

    def test_display_name_without_name(self):
        """display_name deve ser apenas o code quando name está vazio."""
        circuit = self.env["network.circuit"].create(
            {
                "code": "CRC-TEST-002",
                "origin_id": self.origin.id,
                "destination_id": self.destination.id,
                "origin_interface": "eth0",
                "destination_interface": "eth1",
            }
        )
        self.assertEqual(circuit.display_name, "CRC-TEST-002")

    # ------------------------------------------------------------------
    # _check_different_endpoints
    # ------------------------------------------------------------------

    def test_same_origin_and_destination_raises(self):
        """Origem e destino iguais devem lançar ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["network.circuit"].create(
                {
                    "code": "CRC-SAME-001",
                    "origin_id": self.origin.id,
                    "destination_id": self.origin.id,  # mesmo equipamento
                    "origin_interface": "eth0",
                    "destination_interface": "eth1",
                }
            )

    # ------------------------------------------------------------------
    # SQL constraint — code único
    # ------------------------------------------------------------------

    def test_duplicate_code_raises(self):
        """Dois circuitos com o mesmo code devem lançar erro de constraint."""
        from psycopg2 import IntegrityError

        with self.assertRaises(IntegrityError):
            self.env["network.circuit"].create(
                {
                    "code": "CRC-TEST-001",  # já existe
                    "origin_id": self.origin.id,
                    "destination_id": self.destination.id,
                    "origin_interface": "eth0",
                    "destination_interface": "eth1",
                }
            )

    # ------------------------------------------------------------------
    # action_view_tickets
    # ------------------------------------------------------------------

    def test_action_view_tickets(self):
        """action_view_tickets deve retornar act_window filtrada pelo circuito."""
        action = self.circuit.action_view_tickets()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertIn(("circuit_id", "=", self.circuit.id), action["domain"])
