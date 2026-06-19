from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Seg(0), Qua(2), Sex(4), Sáb(5), Dom(6)
CHEIA_WEEKDAYS = frozenset({0, 2, 4, 5, 6})
# Ter(1), Qui(3)
VAZIA_WEEKDAYS = frozenset({1, 3})


class HelpdeskEscalaConfig(models.Model):
    _name = "helpdesk.escala.config"
    _description = "Configuração da Escala de Plantão"

    reference_monday = fields.Date(
        string="Segunda-feira de referência (início de Semana Cheia)",
        required=True,
        help=(
            "Informe qualquer segunda-feira que seja início de 'Semana Cheia'. "
            "O sistema alternará automaticamente Semana Cheia/Vazia a cada semana."
        ),
    )

    @api.constrains("reference_monday")
    def _check_reference_monday(self):
        for rec in self:
            if rec.reference_monday and rec.reference_monday.weekday() != 0:
                raise ValidationError(
                    _("A data de referência deve ser uma segunda-feira.")
                )

    @api.model
    def get_config(self):
        return self.search([], limit=1)


class HelpdeskEscala(models.Model):
    _name = "helpdesk.escala"
    _description = "Escala de Plantão"
    _order = "week_type, shift"

    week_type = fields.Selection(
        selection=[("cheia", "Semana Cheia"), ("vazia", "Semana Vazia")],
        string="Tipo de Semana",
        required=True,
        help="Semana Cheia: Seg/Qua/Sex/Sáb/Dom — Semana Vazia: Ter/Qui",
    )
    shift = fields.Selection(
        selection=[
            ("day", "Diurno (07h–19h)"),
            ("night", "Noturno (19h–07h)"),
        ],
        string="Turno",
        required=True,
    )
    user1_id = fields.Many2one(
        comodel_name="res.users",
        string="1º Responsável",
        required=True,
        domain=[("share", "=", False)],
    )
    user2_id = fields.Many2one(
        comodel_name="res.users",
        string="2º Responsável",
        required=True,
        domain=[("share", "=", False)],
    )

    _sql_constraints = [
        (
            "unique_slot",
            "UNIQUE(week_type, shift)",
            "Já existe uma entrada para essa combinação semana/turno.",
        )
    ]

    def get_effective_users(self, date=None):
        """Retorna (user1, user2)
        substituindo titulares com férias aprovadas vigentes."""
        self.ensure_one()
        if date is None:
            date = fields.Date.context_today(self)
        active_ferias = (
            self.env["helpdesk.ferias"]
            .sudo()
            .search(
                [
                    ("state", "=", "approved"),
                    ("substitute_id", "!=", False),
                    ("date_from", "<=", date),
                    ("date_to", ">=", date),
                ]
            )
        )
        sub_map = {f.user_id.id: f.substitute_id for f in active_ferias}
        return (
            sub_map.get(self.user1_id.id, self.user1_id),
            sub_map.get(self.user2_id.id, self.user2_id),
        )
