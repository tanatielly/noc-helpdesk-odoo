from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("noc_base", "post_install", "-at_install")
class TestHelpdeskTicket(TransactionCase):
    """Testes para helpdesk.ticket — noc_helpdesk."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.team = cls.env["helpdesk.ticket.team"].search([], limit=1)

        cls.provider = cls.env["res.partner"].create(
            {"name": "Provedora HelpDesk", "noc_type": "provider"}
        )
        cls.client = cls.env["res.partner"].create(
            {
                "name": "Cliente HelpDesk",
                "noc_type": "client",
                "provider_id": cls.provider.id,
                "circuit_id": "CRC-001",
                "designation": "ISP-SP-001",
                "phone": "11988880001",
            }
        )
        cls.first_contact = cls.env["res.partner"].create(
            {
                "name": "João Primeiro",
                "parent_id": cls.provider.id,
                "escalation_type": "first_contact",
                "contact_type": "email",
                "email": "joao@provedor.com",
                "phone": "11977770001",
            }
        )

        cls.tag_unavailable = cls.env.ref(
            "noc_helpdesk.helpdesk_ticket_tag_unavailable",
            raise_if_not_found=False,
        )
        cls.tag_high_latency = cls.env.ref(
            "noc_helpdesk.helpdesk_ticket_tag_high_latency",
            raise_if_not_found=False,
        )
        cls.tag_discarded = cls.env.ref(
            "noc_helpdesk.helpdesk_ticket_tag_discarded_packet",
            raise_if_not_found=False,
        )

        cls.ticket = cls.env["helpdesk.ticket"].create(
            {
                "name": "Chamado Teste",
                "provider_id": cls.provider.id,
                "team_id": cls.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )

    # ------------------------------------------------------------------
    # _compute_first_contact
    # ------------------------------------------------------------------

    def test_first_contact_populated(self):
        """Campos do primeiro contato devem ser preenchidos a partir da provedora."""
        self.assertEqual(self.ticket.first_contact_id, self.first_contact)
        self.assertEqual(self.ticket.first_contact_name, "João Primeiro")
        self.assertEqual(self.ticket.first_contact_email, "joao@provedor.com")
        self.assertEqual(self.ticket.first_contact_phone, "11977770001")
        self.assertEqual(self.ticket.first_contact_type, "email")

    def test_first_contact_empty_without_provider(self):
        """Sem provedora, todos os campos de primeiro contato devem ser False."""
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Sem Provedora",
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertFalse(ticket.first_contact_id)
        self.assertFalse(ticket.first_contact_name)
        self.assertFalse(ticket.first_contact_email)
        self.assertFalse(ticket.first_contact_phone)
        self.assertFalse(ticket.first_contact_type)

    def test_first_contact_empty_when_no_escalation_type(self):
        """Provedora sem contato first_contact deve deixar campos vazios."""
        provider_sem_contato = self.env["res.partner"].create(
            {"name": "Provedora Sem Contato", "noc_type": "provider"}
        )
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Sem Primeiro Contato",
                "provider_id": provider_sem_contato.id,
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertFalse(ticket.first_contact_id)

    # ------------------------------------------------------------------
    # _compute_tag_decorations
    # ------------------------------------------------------------------

    def test_tag_decoration_unavailable(self):
        """Tag de indisponibilidade deve ativar is_unavailable."""
        if not self.tag_unavailable:
            self.skipTest("Tag unavailable não encontrada")
        self.ticket.write({"tag_id": self.tag_unavailable.id})
        self.assertTrue(self.ticket.is_unavailable)
        self.assertFalse(self.ticket.is_high_latency)
        self.assertFalse(self.ticket.is_discarded_packet)

    def test_tag_decoration_high_latency(self):
        """Tag de latência deve ativar is_high_latency."""
        if not self.tag_high_latency:
            self.skipTest("Tag high_latency não encontrada")
        self.ticket.write({"tag_id": self.tag_high_latency.id})
        self.assertTrue(self.ticket.is_high_latency)
        self.assertFalse(self.ticket.is_unavailable)

    def test_tag_decoration_discarded_packet(self):
        """Tag de descarte deve ativar is_discarded_packet."""
        if not self.tag_discarded:
            self.skipTest("Tag discarded_packet não encontrada")
        self.ticket.write({"tag_id": self.tag_discarded.id})
        self.assertTrue(self.ticket.is_discarded_packet)
        self.assertFalse(self.ticket.is_unavailable)

    def test_tag_renames_ticket_name_unavailable(self):
        """Aplicar tag de queda deve renomear o ticket para 'Queda de Link'."""
        if not self.tag_unavailable:
            self.skipTest("Tag unavailable não encontrada")
        self.ticket.write({"tag_id": self.tag_unavailable.id})
        self.assertEqual(self.ticket.name, "Queda de Link")

    # ------------------------------------------------------------------
    # _compute_tag_priority
    # ------------------------------------------------------------------

    def test_tag_priority_default_when_no_tag(self):
        """Sem tag, a prioridade deve ser 9999."""
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Sem Tag",
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertEqual(ticket.tag_priority, 9999)

    def test_tag_priority_set_from_tag(self):
        """tag_priority deve espelhar a prioridade da tag."""
        tag = self.env["helpdesk.ticket.tag"].create(
            {"name": "Tag Prioritária", "priority": 5}
        )
        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Com Tag",
                "tag_id": tag.id,
                "team_id": self.team.id,
                "description": "Descrição do chamado para testes.",
            }
        )
        self.assertEqual(ticket.tag_priority, 5)

    # ------------------------------------------------------------------
    # message_post — validação de nota interna
    # ------------------------------------------------------------------

    def test_message_post_internal_note_requires_keyword(self):
        """Nota interna sem keyword deve lançar ValidationError."""
        subtype = self.env.ref("mail.mt_note")
        with self.assertRaises(ValidationError):
            self.ticket.message_post(
                body="Sem nenhuma palavra reservada aqui.",
                subtype_id=subtype.id,
            )

    def test_message_post_internal_note_with_keyword_succeeds(self):
        """Nota interna com keyword deve ser aceita."""
        subtype = self.env.ref("mail.mt_note")
        # Não deve lançar exceção
        self.ticket.message_post(
            body="TESTE de diagnóstico do ClarEnzo.",
            subtype_id=subtype.id,
        )

    def test_message_post_duplicate_internal_note_rejected(self):
        """Nota interna duplicada (mesmo body) deve ser rejeitada."""
        subtype = self.env.ref("mail.mt_note")
        body = "PROBLEMA identificado no circuito."
        self.ticket.message_post(body=body, subtype_id=subtype.id)
        with self.assertRaises(ValidationError):
            self.ticket.message_post(body=body, subtype_id=subtype.id)

    def test_message_post_non_internal_skips_validation(self):
        """Mensagem não-interna não deve passar pela validação de keyword."""
        subtype = self.env.ref("mail.mt_comment")
        # Não deve lançar exceção mesmo sem keyword
        self.ticket.message_post(
            body="Atualização simples para o cliente.",
            subtype_id=subtype.id,
        )

    # ------------------------------------------------------------------
    # _onchange_client_id
    # ------------------------------------------------------------------

    def test_onchange_client_fills_designation(self):
        """Selecionar cliente deve preencher designation_speed."""
        ticket = self.env["helpdesk.ticket"].new(
            {"name": "Onchange Teste", "team_id": self.team.id}
        )
        ticket.client_id = self.client
        ticket._onchange_client_id()
        self.assertEqual(ticket.designation_speed, self.client.designation)

    def test_onchange_client_fills_phone(self):
        """Selecionar cliente deve preencher phone_number."""
        ticket = self.env["helpdesk.ticket"].new(
            {"name": "Onchange Phone", "team_id": self.team.id}
        )
        ticket.client_id = self.client
        ticket._onchange_client_id()
        self.assertEqual(ticket.phone_number, self.client.phone)

    # ------------------------------------------------------------------
    # _onchange_provider_id
    # ------------------------------------------------------------------

    def test_onchange_provider_clears_client_from_different_provider(self):
        """Trocar provedora deve limpar o cliente se ele pertence à outra."""
        other_provider = self.env["res.partner"].create(
            {"name": "Outra Provedora", "noc_type": "provider"}
        )
        ticket = self.env["helpdesk.ticket"].new(
            {
                "name": "Troca Provedora",
                "team_id": self.team.id,
                "provider_id": self.provider.id,
                "client_id": self.client.id,
            }
        )
        ticket.provider_id = other_provider
        ticket._onchange_provider_id()
        self.assertFalse(ticket.client_id)
