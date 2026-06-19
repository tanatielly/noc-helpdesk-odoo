from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ticket_ids = fields.Many2many(
        comodel_name="helpdesk.ticket",
        string="Chamados",
        compute="_compute_tickets",
    )

    provider_ticket_ids = fields.One2many(
        comodel_name="helpdesk.ticket",
        string="Chamados da Operadora",
        compute="_compute_provider_ticket_ids",
        store=False,
    )

    @api.depends("ticket_ids", "noc_type")
    def _compute_ticket_count(self):
        ticket_model = self.env["helpdesk.ticket"]
        for record in self:
            if record.noc_type == "provider":
                record.ticket_count = ticket_model.search_count(
                    [("provider_id", "=", record.id)]
                )
            else:
                record.ticket_count = len(record.ticket_ids)

    @api.depends()
    def _compute_tickets(self):
        for partner in self:
            tickets = self.env["helpdesk.ticket"].search(
                [("partner_id", "=", partner.id)]
            )
            partner.ticket_ids = tickets

    @api.depends("noc_type")
    def _compute_provider_ticket_ids(self):
        ticket_model = self.env["helpdesk.ticket"]
        for record in self:
            if record.noc_type == "provider":
                record.provider_ticket_ids = ticket_model.search(
                    [("provider_id", "=", record.id)]
                )
            else:
                record.provider_ticket_ids = ticket_model.search(
                    [("client_id", "=", record.id)]
                )

    @api.depends("child_ids", "child_ids.escalation_type")
    def _compute_sorted_child_ids(self):
        escalation_order = {
            "first_contact": 0,
            "level_one": 1,
            "level_two": 2,
            "level_three": 3,
            "level_four": 4,
        }
        for record in self:
            sorted_children = record.child_ids.sorted(
                key=lambda x: (
                    escalation_order.get(x.escalation_type, 999),
                    x.name,
                ),
                reverse=False,
            )
            record.sorted_child_ids = sorted_children

    def action_view_tickets(self):
        self.ensure_one()
        return {
            "name": _("Chamados — %(name)s", name=self.name),
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket",
            "view_mode": "tree,form",
            "domain": [("provider_id", "=", self.id)],
            "context": {"default_provider_id": self.id},
        }

    def action_view_clients(self):
        self.ensure_one()
        return {
            "name": _("Clientes — %(name)s", name=self.name),
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.client",
            "view_mode": "tree,form",
            "domain": [("provider_id", "=", self.id)],
            "context": {"default_provider_id": self.id},
        }
