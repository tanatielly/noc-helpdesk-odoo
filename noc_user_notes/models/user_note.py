from odoo import fields, models


class UserNote(models.Model):
    _name = "user.note"
    _description = "Anotação Privada"
    _order = "write_date desc"
    _rec_name = "name"

    name = fields.Char(
        string="Título",
        required=True,
        default="Nova Anotação",
    )
    content = fields.Html(string="Conteúdo")
    status = fields.Selection(
        selection=[("draft", "Rascunho"), ("note", "Anotação")],
        default="draft",
        required=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Usuário",
        default=lambda self: self.env.user,
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
    )
    color = fields.Integer(string="Cor", default=0)
