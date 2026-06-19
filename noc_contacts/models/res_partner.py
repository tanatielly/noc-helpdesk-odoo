from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    contact_type = fields.Selection(
        selection=[
            ("email", "Email"),
            ("phone", "Telefone"),
        ],
        string="Tipo de Contato",
    )

    noc_type = fields.Selection(
        selection=[
            ("client", "Cliente"),
            ("provider", "Operadora"),
        ],
        string="Empresa",
        default="provider",
        help="Indica se este contato é um cliente, uma Operadora ou ambos.",
    )

    ticket_count = fields.Integer(
        string="Nº de Chamados",
        compute="_compute_ticket_count",
    )

    circuit_id = fields.Char(
        string="ID do Circuito",
        help="Identificador do circuito / designação do link.",
    )
    designation = fields.Char(
        string="Designação",
        help="Designação técnica do link (e.g.: ISP-SP-001).",
    )
    bandwidth = fields.Char(
        string="Velocidade Contratada",
        help="Ex: 100 Mbps, 1 Gbps.",
    )

    provider_id = fields.Many2one(
        comodel_name="res.partner",
        string="Operadora",
        domain=[("noc_type", "=", "provider")],
        help="Operadora responsável por este contato.",
    )

    escalation_type = fields.Selection(
        selection=[
            ("first_contact", "Primeiro Contato"),
            ("level_one", "Nível 1"),
            ("level_two", "Nível 2"),
            ("level_three", "Nível 3"),
            ("level_four", "Nível 4"),
        ],
        string="Tipo de Escalation",
    )

    client_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="res_partner_provider_client_rel",
        column1="provider_id",
        column2="client_id",
        string="Clientes",
        compute="_compute_client_ids",
    )
    client_count = fields.Integer(
        string="Nº de Clientes",
        compute="_compute_client_count",
    )

    sorted_child_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Contatos (Ordenados por Escalation)",
        compute="_compute_sorted_child_ids",
    )

    @api.depends("client_ids")
    def _compute_client_count(self):
        for provider in self:
            provider.client_count = len(provider.client_ids)

    def _compute_client_ids(self):
        for record in self:
            if record.noc_type == "provider":
                record.client_ids = self.env["res.partner"].search(
                    [
                        ("provider_id", "=", record.id),
                        ("noc_type", "=", "client"),
                    ]
                )
            else:
                record.client_ids = False
