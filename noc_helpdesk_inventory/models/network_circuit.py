from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class NetworkCircuit(models.Model):
    _name = "network.circuit"
    _description = "Circuito de Rede"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "link_designation asc"
    _rec_name = "link_designation"

    # ------------------------------------------------------------------
    # FIELDS
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Nome / Descrição",
        tracking=True,
    )
    display_name = fields.Char(
        string="Nome Exibido",
        compute="_compute_display_name",
        store=True,
    )

    origin_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento Origem",
        required=True,
        tracking=True,
        ondelete="restrict",
        index=True,
    )
    destination_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento Destino",
        required=True,
        tracking=True,
        ondelete="restrict",
        index=True,
    )

    origin_interface = fields.Char(
        string="Interface de Origem",
        required=True,
    )

    destination_interface = fields.Char(
        string="Interface de Destino",
        required=True,
    )

    circuit_type_id = fields.Many2one(
        comodel_name="network.circuit.type",
        string="Tipo de Circuito",
        tracking=True,
        ondelete="set null",
        index=True,
    )

    provider_id = fields.Many2one(
        comodel_name="res.partner",
        string="Operadora",
        domain="[('noc_type', '=', 'provider'), ('is_company', '=', True)]",
        tracking=True,
        ondelete="set null",
        index=True,
        help="Operadora de internet responsável por este circuito.",
    )

    link_designation = fields.Char(string="Designação")

    link_speed = fields.Char(string="Velocidade contratada")

    active = fields.Boolean(default=True, tracking=True)

    notes = fields.Text(string="Observações")

    centro_funcional = fields.Char()

    # Chamados relacionados a este circuito
    ticket_ids = fields.One2many(
        comodel_name="helpdesk.ticket",
        inverse_name="circuit_id",
        string="Chamados Relacionados",
        readonly=True,
    )
    ticket_count = fields.Integer(
        string="Qtd. Chamados",
        compute="_compute_ticket_count",
    )

    # ------------------------------------------------------------------
    # COMPUTE
    # ------------------------------------------------------------------

    @api.depends("link_designation", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.link_designation or rec.name or ""

    @api.depends("ticket_ids")
    def _compute_ticket_count(self):
        for rec in self:
            rec.ticket_count = len(rec.ticket_ids)

    # ------------------------------------------------------------------
    # CONSTRAINTS
    # ------------------------------------------------------------------

    @api.constrains("origin_id", "destination_id")
    def _check_different_endpoints(self):
        for rec in self:
            if rec.origin_id and rec.destination_id:
                if rec.origin_id == rec.destination_id:
                    raise ValidationError(
                        _("O equipamento de origem e " "destino não podem ser o mesmo.")
                    )

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def action_view_tickets(self):
        self.ensure_one()

        name = _("Chamados — %(name)s")
        name = name % {
            "name": self.display_name,
        }

        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket",
            "view_mode": "tree,form",
            "domain": [("circuit_id", "=", self.id)],
            "context": {"default_circuit_id": self.id},
        }


class NetworkEquipment(models.Model):
    """Extend network.equipment para expor os circuitos dos quais faz parte."""

    _inherit = "network.equipment"

    circuit_ids = fields.One2many(
        comodel_name="network.circuit",
        string="Circuitos de Rede",
        compute="_compute_circuit_ids",
        help="Todos os circuitos em que este equipamento "
        "atua como origem ou destino.",
    )
    circuit_count = fields.Integer(
        string="Qtd. Circuitos",
        compute="_compute_circuit_ids",
    )

    def _compute_circuit_ids(self):
        Circuit = self.env["network.circuit"]
        for rec in self:
            circuits = Circuit.search(
                [
                    "|",
                    ("origin_id", "=", rec.id),
                    ("destination_id", "=", rec.id),
                ]
            )
            rec.circuit_ids = circuits
            rec.circuit_count = len(circuits)

    def action_view_circuits(self):
        self.ensure_one()

        name = _("Circuitos — %(name)s")
        name = name % {
            "name": self.name,
        }

        return {
            "name": name,
            "type": "ir.actions.act_window",
            "res_model": "network.circuit",
            "view_mode": "tree,form",
            "domain": [
                "|",
                ("origin_id", "=", self.id),
                ("destination_id", "=", self.id),
            ],
        }
