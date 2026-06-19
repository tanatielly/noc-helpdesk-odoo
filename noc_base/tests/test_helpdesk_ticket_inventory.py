from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("noc_base", "post_install", "-at_install")
class ModelName(TransactionCase):
    """This class contains the unit tests for 'ModelName'.

    Tests:
      - item_name: Checks if the item_name works properly
    """

    def setUp(self):
        super(ModelName, self).setUp()

    def test_item_name(self):
        """Checks if the item_name works properly"""

        pass


class TestHelpdeskTicketInventory(TransactionCase):
    """Testes para helpdesk.ticket — noc_helpdesk_inventory."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.team = cls.env["helpdesk.ticket.team"].search([], limit=1)

        cls.origin = cls.env["network.equipment"].create(
            {
                "name": "SW-Core-01",
                "equipment_type": "switch",
                "ip_address": "192.168.10.1",
            }
        )
        cls.destination = cls.env["network.equipment"].create(
            {
                "name": "RT-Border-01",
                "equipment_type": "router",
                "ip_address": "192.168.10.2",
            }
        )
        cls.circuit = cls.env["network.circuit"].create(
            {
                "code": "INV-CRC-001",
                "name": "Circuito Inventário",
                "origin_id": cls.origin.id,
                "destination_id": cls.destination.id,
                "origin_interface": "GigabitEthernet0/1",
                "destination_interface": "GigabitEthernet0/0",
            }
        )

    # ------------------------------------------------------------------
    # _compute_network_path
    # ------------------------------------------------------------------

    def test_network_path_with_both_endpoints(self):
        """network_path deve mostrar origem → destino com IPs."""
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Path Completo",
                "net_origin_id": self.origin.id,
                "net_destination_id": self.destination.id,
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertIn("SW-Core-01", ticket.network_path)
        self.assertIn("RT-Border-01", ticket.network_path)
        self.assertIn("→", ticket.network_path)
        self.assertIn("192.168.10.1", ticket.network_path)

    def test_network_path_only_origin(self):
        """network_path com apenas origem não deve conter '→'."""
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Path Só Origem",
                "net_origin_id": self.origin.id,
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertIn("SW-Core-01", ticket.network_path)
        self.assertNotIn("→", ticket.network_path)

    def test_network_path_empty_without_endpoints(self):
        """Sem origem e destino, network_path deve ser string vazia."""
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Path Vazio",
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertEqual(ticket.network_path, "")

    # ------------------------------------------------------------------
    # circuit_id → net_origin_id / net_destination_id (onchange)
    # ------------------------------------------------------------------

    def test_onchange_circuit_fills_equipments(self):
        """Selecionar circuito deve preencher origem e destino via onchange."""
        ticket = self.env["helpdesk.ticket"].new(
            {"name": "Onchange Circuito", "team_id": self.team.id}
        )
        ticket.circuit_id = self.circuit
        ticket._onchange_circuit_id()
        self.assertEqual(ticket.net_origin_id, self.origin)
        self.assertEqual(ticket.net_destination_id, self.destination)

    def test_onchange_circuit_none_clears_nothing(self):
        """Com circuit_id False, onchange não deve alterar equipamentos."""
        ticket = self.env["helpdesk.ticket"].new(
            {
                "name": "Onchange None",
                "team_id": self.team.id,
                "net_origin_id": self.origin.id,
            }
        )
        ticket.circuit_id = False
        ticket._onchange_circuit_id()
        # Equipamento deve permanecer inalterado
        self.assertEqual(ticket.net_origin_id, self.origin)

    # ------------------------------------------------------------------
    # reopen_count
    # ------------------------------------------------------------------

    def test_reopen_count_increments_on_reopen_stage(self):
        """Mover para estágio 'reopen' deve incrementar reopen_count."""
        reopen_stage = self.env["helpdesk.ticket.stage"].search(
            [("name", "ilike", "reopen")], limit=1
        )
        if not reopen_stage:
            self.skipTest("Estágio 'reopen' não encontrado")

        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Ticket Reopen",
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        initial = ticket.reopen_count
        ticket.write({"stage_id": reopen_stage.id})
        self.env.cr.execute(
            "SELECT reopen_count FROM helpdesk_ticket WHERE id = %s", (ticket.id,)
        )
        row = self.env.cr.fetchone()
        self.assertEqual(row[0], initial + 1)

    def test_reopen_count_not_incremented_on_other_stage(self):
        """Mover para estágio que não é 'reopen' não deve incrementar reopen_count."""
        done_stage = self.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_stage_done", raise_if_not_found=False
        )
        if not done_stage:
            self.skipTest("Estágio 'done' não encontrado")

        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Ticket Done",
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        initial = ticket.reopen_count
        ticket.write({"stage_id": done_stage.id})
        self.env.cr.execute(
            "SELECT reopen_count FROM helpdesk_ticket WHERE id = %s", (ticket.id,)
        )
        row = self.env.cr.fetchone()
        self.assertEqual(row[0], initial)

    # ------------------------------------------------------------------
    # net_origin_interface / net_destination_interface (related ao circuit)
    # ------------------------------------------------------------------

    def test_interface_fields_from_circuit(self):
        """Interfaces devem ser lidas do circuito via related."""
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Interfaces Circuito",
                "circuit_id": self.circuit.id,
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertEqual(ticket.net_origin_interface, "GigabitEthernet0/1")
        self.assertEqual(ticket.net_destination_interface, "GigabitEthernet0/0")
