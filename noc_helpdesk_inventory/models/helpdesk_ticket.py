from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    description = fields.Html(required=False, default="")

    # ── Campos originais do noc_helpdesk_inventory ──────────────────
    net_origin_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento Origem",
        tracking=True,
        ondelete="set null",
        help="Equipamento de rede de origem do tráfego / problema",
    )
    net_destination_id = fields.Many2one(
        comodel_name="network.equipment",
        string="Equipamento Destino",
        tracking=True,
        ondelete="set null",
        help="Equipamento de rede de destino do tráfego / problema",
    )
    network_path = fields.Char(
        string="Caminho de Rede",
        compute="_compute_network_path",
        store=True,
    )

    net_origin_interface = fields.Char(
        string="Interface de Origem",
        related="circuit_id.origin_interface",
        readonly=True,
    )

    net_destination_interface = fields.Char(
        string="Interface de Destino",
        related="circuit_id.destination_interface",
        readonly=True,
    )

    # ── Novo campo — vínculo com circuito ────────────────────────────
    circuit_id = fields.Many2one(
        comodel_name="network.circuit",
        string="Circuito",
        tracking=True,
        ondelete="set null",
        index=True,
        help="Circuito de rede relacionado a este chamado.",
    )

    # ── Computes originais ───────────────────────────────────────────

    @api.depends(
        "net_origin_id",
        "net_destination_id",
        "circuit_id.origin_interface",
        "circuit_id.destination_interface",
    )
    def _compute_network_path(self):
        for ticket in self:
            parts = []
            if ticket.net_origin_id:
                origin = ticket.net_origin_id.name
                if ticket.circuit_id.origin_interface:
                    origin += f" ({ticket.circuit_id.origin_interface})"
                parts.append(origin)
            if ticket.net_destination_id:
                destination = ticket.net_destination_id.name
                if ticket.circuit_id.destination_interface:
                    destination += f" ({ticket.circuit_id.destination_interface})"
                parts.append(destination)
            ticket.network_path = " → ".join(parts) if parts else ""

    # ── Onchange novo ────────────────────────────────────────────────

    @api.onchange("circuit_id")
    def _onchange_circuit_id(self):
        if self.circuit_id:
            self.net_origin_id = (
                self.circuit_id.origin_id
            )  # ← _unknown se circuit_id for novo
            self.net_destination_id = self.circuit_id.destination_id

    falha_massiva_equipment_ids = fields.Many2many(
        comodel_name="network.equipment",
        relation="helpdesk_ticket_falha_massiva_equip_rel",
        column1="ticket_id",
        column2="equipment_id",
        string="Equipamentos Afetados",
    )
    falha_massiva_site_ids = fields.Many2many(
        comodel_name="network.site",
        relation="helpdesk_ticket_falha_massiva_site_rel",
        column1="ticket_id",
        column2="site_id",
        string="Sites Afetados",
    )
    falha_massiva_circuit_ids = fields.Many2many(
        comodel_name="network.circuit",
        relation="helpdesk_ticket_falha_massiva_circuit_rel",
        column1="ticket_id",
        column2="circuit_id",
        string="Circuitos Afetados",
    )

    reopen_count = fields.Integer(string="Vezes Reaberto", default=0)

    @api.constrains(
        "circuit_id", "is_unavailable", "is_high_latency", "is_discarded_packet"
    )
    def _check_circuit_required(self):
        for ticket in self:
            if (
                ticket.is_unavailable
                or ticket.is_high_latency
                or ticket.is_discarded_packet
            ) and not ticket.circuit_id:
                raise ValidationError(
                    _(
                        "Circuito é obrigatório para chamados de "
                        "Indisponível, Alta Latência e Descarte de Pacotes."
                    )
                )

    @api.constrains("net_origin_id", "is_equipamento_isolado")
    def _check_net_origin_required(self):
        for ticket in self:
            if ticket.is_equipamento_isolado and not ticket.net_origin_id:
                raise ValidationError(
                    _(
                        """Equipamento Origem é obrigatório
                        para chamados de Equipamento Isolado."""
                    )
                )

    def write(self, vals):
        if "stage_id" in vals:
            stage = self.env["helpdesk.ticket.stage"].browse(vals["stage_id"])
            if "reopen" in (stage.name or "").lower():
                for ticket in self:
                    self.env.cr.execute(
                        "UPDATE helpdesk_ticket "
                        "SET reopen_count = reopen_count + 1 WHERE id = %s",
                        (ticket.id,),
                    )
        result = super().write(vals)
        equipments = self.mapped("net_origin_id") | self.mapped("net_destination_id")
        equipments._compute_reopen_count()
        return result
