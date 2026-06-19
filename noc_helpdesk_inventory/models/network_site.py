from odoo import fields, models


class NetworkSite(models.Model):
    _name = "network.site"
    _description = "Site de Rede"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name asc"

    name = fields.Char(string="Nome", required=True, tracking=True)
    address = fields.Char(string="Endereço Completo", tracking=True)
    latitude = fields.Float(digits=(10, 7), tracking=True)
    longitude = fields.Float(digits=(10, 7), tracking=True)
    equipment_ids = fields.Many2many(
        comodel_name="network.equipment",
        relation="network_site_equipment_rel",
        column1="site_id",
        column2="equipment_id",
        string="Equipamentos",
    )
    equipment_count = fields.Integer(
        string="Qtd. Equipamentos", compute="_compute_equipment_count"
    )

    def _compute_equipment_count(self):
        for rec in self:
            rec.equipment_count = len(rec.equipment_ids)

    def action_view_equipment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Equipamentos — {self.name}",
            "res_model": "network.equipment",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.equipment_ids.ids)],
            "context": {"default_site_ids": [(4, self.id)]},
        }
