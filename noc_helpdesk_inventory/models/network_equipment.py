import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class NetworkEquipment(models.Model):
    _name = "network.equipment"
    _description = "Equipamento de Rede"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name asc"

    name = fields.Char(string="Nome / Hostname", required=True, tracking=True)
    equipment_type = fields.Selection(
        selection=[
            ("switch", "Switch"),
            ("router", "Roteador"),
            ("firewall", "Firewall"),
            ("access_point", "Access Point"),
            ("server", "Servidor"),
            ("other", "Outro"),
        ],
        string="Tipo",
        required=True,
        default="switch",
        tracking=True,
    )
    brand = fields.Char(string="Marca", tracking=True)
    model_name = fields.Char(string="Modelo", tracking=True)

    ip_address = fields.Char(string="Endereço IP", required=True, tracking=True)
    mac_address = fields.Char(string="MAC Address", tracking=True)
    port_count = fields.Integer(string="Qtd. Portas", default=0)
    vlan_ids = fields.Many2many(
        comodel_name="network.vlan",
        relation="equipment_vlan_rel",
        column1="equipment_id",
        column2="vlan_id",
        string="Interfaces e VLANs",
    )

    site_ids = fields.Many2many(
        comodel_name="network.site",
        relation="network_site_equipment_rel",
        column1="equipment_id",
        column2="site_id",
        string="Sites",
    )
    location = fields.Char(string="Localização", tracking=True)
    is_danger = fields.Boolean(string="Perigo", default=False, tracking=True)
    is_deactivating = fields.Boolean(
        string="Equipamento em Desativação", default=False, tracking=True
    )
    status = fields.Selection(
        selection=[
            ("active", "Ativo"),
            ("inactive", "Inativo"),
            ("maintenance", "Manutenção"),
            ("obsolete", "Obsoleto"),
        ],
        default="active",
        required=True,
        tracking=True,
    )
    notes = fields.Text(string="Observações")

    origin_ticket_ids = fields.One2many(
        comodel_name="helpdesk.ticket",
        inverse_name="net_origin_id",
        string="Chamados como Origem",
    )
    destination_ticket_ids = fields.One2many(
        comodel_name="helpdesk.ticket",
        inverse_name="net_destination_id",
        string="Chamados como Destino",
    )
    ticket_count = fields.Integer(
        string="Chamados",
        compute="_compute_ticket_count",
    )

    @api.depends("origin_ticket_ids", "destination_ticket_ids")
    def _compute_ticket_count(self):
        for rec in self:
            rec.ticket_count = len(rec.origin_ticket_ids) + len(
                rec.destination_ticket_ids
            )

    @api.constrains("ip_address")
    def _check_ip_address(self):
        pattern = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
        for rec in self:
            if rec.ip_address and not pattern.match(rec.ip_address):
                raise ValidationError(
                    f'Endereço IP inválido: "{rec.ip_address}".'
                    " Use o formato XXX.XXX.XXX.XXX"
                )

    @api.constrains("mac_address")
    def _check_mac_address(self):
        pattern = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
        for rec in self:
            if rec.mac_address and not pattern.match(rec.mac_address):
                raise ValidationError(
                    f'MAC Address inválido: "{rec.mac_address}".'
                    "Use o formato AA:BB:CC:DD:EE:FF"
                )

    def action_view_tickets(self):
        self.ensure_one()
        ticket_ids = self.origin_ticket_ids.ids + self.destination_ticket_ids.ids
        return {
            "type": "ir.actions.act_window",
            "name": f"Chamados — {self.name}",
            "res_model": "helpdesk.ticket",
            "view_mode": "tree,form",
            "domain": [("id", "in", ticket_ids)],
        }

    def action_set_maintenance(self):
        self.write({"status": "maintenance"})

    def action_set_active(self):
        self.write({"status": "active"})

    reopen = fields.Integer(
        string="Incidentes",
        compute="_compute_reopen_count",
    )

    @api.depends(
        "origin_ticket_ids.reopen_count", "destination_ticket_ids.reopen_count"
    )
    def _compute_reopen_count(self):
        for rec in self:
            tickets = rec.origin_ticket_ids | rec.destination_ticket_ids
            rec.reopen = sum(tickets.mapped("reopen_count"))

    def action_view_reopen_tickets(self):
        reopen_stage = self.env["helpdesk.ticket.stage"].search(
            [("name", "ilike", "reopen")], limit=1
        )
        tickets = self.origin_ticket_ids | self.destination_ticket_ids
        reopen_tickets = tickets.filtered(lambda t: t.stage_id == reopen_stage)
        return {
            "type": "ir.actions.act_window",
            "name": "Incidentes",
            "res_model": "helpdesk.ticket",
            "view_mode": "tree,form",
            "domain": [("id", "in", reopen_tickets.ids)],
        }


class NetworkVlan(models.Model):
    _name = "network.vlan"
    _description = "VLAN"
    _order = "vlan_id asc"

    vlan_id = fields.Integer(string="ID da VLAN", required=True)
    name = fields.Char(string="Nome", required=True)
    description = fields.Char(string="Descrição")
    equipment_ids = fields.Many2many(
        comodel_name="network.equipment",
        relation="equipment_vlan_rel",
        column1="vlan_id",
        column2="equipment_id",
        string="Equipamentos",
    )

    def name_get(self):
        return [(rec.id, f"VLAN {rec.vlan_id} — {rec.name}") for rec in self]

    _sql_constraints = [
        ("vlan_id_unique", "unique(vlan_id)", "Já existe uma VLAN com este ID."),
    ]
