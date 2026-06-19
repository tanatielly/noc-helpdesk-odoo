from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("noc_base", "post_install", "-at_install")
class TestResPartner(TransactionCase):
    """Testes para res.partner — noc_contacts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.provider = cls.env["res.partner"].create(
            {
                "name": "Provedora Teste",
                "noc_type": "provider",
            }
        )
        cls.client = cls.env["res.partner"].create(
            {
                "name": "Cliente Teste",
                "noc_type": "client",
                "provider_id": cls.provider.id,
            }
        )
        cls.contact_first = cls.env["res.partner"].create(
            {
                "name": "Contato Primeiro",
                "parent_id": cls.provider.id,
                "escalation_type": "first_contact",
                "contact_type": "email",
                "email": "primeiro@teste.com",
                "phone": "11999990001",
            }
        )
        cls.contact_l1 = cls.env["res.partner"].create(
            {
                "name": "Contato Nivel 1",
                "parent_id": cls.provider.id,
                "escalation_type": "level_one",
                "contact_type": "phone",
            }
        )

    # ------------------------------------------------------------------
    # _compute_client_ids
    # ------------------------------------------------------------------

    def test_client_ids_provider_sees_clients(self):
        """Provedora deve enxergar o cliente vinculado a ela."""
        self.assertIn(self.client, self.provider.client_ids)

    def test_client_ids_client_is_empty(self):
        """Contato do tipo cliente não deve ter client_ids."""
        self.assertFalse(self.client.client_ids)

    def test_client_count(self):
        """client_count deve refletir a quantidade de clientes."""
        self.assertEqual(self.provider.client_count, 1)

    # ------------------------------------------------------------------
    # _compute_sorted_child_ids
    # ------------------------------------------------------------------

    def test_sorted_child_ids_order(self):
        """first_contact deve aparecer antes de level_one."""
        children = self.provider.sorted_child_ids
        types = [c.escalation_type for c in children]
        self.assertIn("first_contact", types)
        self.assertIn("level_one", types)
        self.assertLess(
            types.index("first_contact"),
            types.index("level_one"),
            "first_contact deve ter menor índice que level_one",
        )

    def test_sorted_child_ids_partner_without_children(self):
        """Parceiro sem filhos deve retornar sorted_child_ids vazio."""
        self.assertFalse(self.client.sorted_child_ids)

    # ------------------------------------------------------------------
    # _compute_ticket_count (provider)
    # ------------------------------------------------------------------

    def test_ticket_count_provider_increments(self):
        """ticket_count da provedora deve incrementar ao criar chamado vinculado."""
        initial = self.provider.ticket_count
        team = self.env["helpdesk.ticket.team"].search([], limit=1)
        self.env["helpdesk.ticket"].create(
            {
                "name": "Chamado Contagem",
                "provider_id": self.provider.id,
                "team_id": team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        # Invalidar cache para forçar recompute
        self.provider.invalidate_recordset()
        self.assertEqual(self.provider.ticket_count, initial + 1)

    # ------------------------------------------------------------------
    # action_view_tickets
    # ------------------------------------------------------------------

    def test_action_view_tickets_returns_act_window(self):
        """action_view_tickets deve retornar uma ação do tipo act_window."""
        action = self.provider.action_view_tickets()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "helpdesk.ticket")
        self.assertEqual(action["context"]["default_provider_id"], self.provider.id)
