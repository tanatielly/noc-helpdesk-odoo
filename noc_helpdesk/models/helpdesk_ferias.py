import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class HelpdeskFerias(models.Model):
    _name = "helpdesk.ferias"
    _description = "Solicitação de Férias"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc"

    name = fields.Char(
        string="Descrição",
        compute="_compute_name",
        store=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Colaborador",
        required=True,
        default=lambda self: self.env.user,
        domain=[("share", "=", False)],
        tracking=True,
    )
    date_from = fields.Date(string="Data de Início", required=True, tracking=True)
    date_to = fields.Date(string="Data de Fim", required=True, tracking=True)
    duration = fields.Integer(
        string="Dias",
        compute="_compute_duration",
        store=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Rascunho"),
            ("submitted", "Aguardando Aprovação"),
            ("approved", "Aprovado"),
            ("refused", "Recusado"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    approver_id = fields.Many2one(
        comodel_name="res.users",
        string="Aprovado/Recusado por",
        tracking=True,
        domain=[("share", "=", False)],
        readonly=True,
    )
    notes = fields.Text(string="Observações")
    substitute_id = fields.Many2one(
        comodel_name="res.users",
        string="Substituto no Plantão",
        domain=[("share", "=", False)],
        tracking=True,
    )
    is_plantao_member = fields.Boolean(
        string="Membro do Time de Plantão",
        compute="_compute_is_plantao_member",
    )
    can_approve = fields.Boolean(
        string="Pode Aprovar",
        compute="_compute_can_approve",
    )
    is_own_record = fields.Boolean(
        string="Registro Próprio",
        compute="_compute_is_own_record",
    )

    # ── Computed ────────────────────────────────────────────────────────────

    @api.depends("user_id")
    def _compute_is_plantao_member(self):
        escala_records = self.env["helpdesk.escala"].sudo().search([])
        plantao_user_ids = {
            uid for e in escala_records for uid in (e.user1_id.id, e.user2_id.id) if uid
        }
        for rec in self:
            rec.is_plantao_member = bool(
                rec.user_id and rec.user_id.id in plantao_user_ids
            )

    # ── Helpers de autorização ──────────────────────────────────────────────

    def _get_noc_team(self):
        ICP = self.env["ir.config_parameter"].sudo()
        team_id_raw = ICP.get_param("noc_helpdesk.noc_team_id", False)
        if team_id_raw:
            try:
                team_id = int(team_id_raw)
                if team_id > 0:
                    team = self.env["helpdesk.ticket.team"].browse(team_id)
                    if team.exists():
                        return team
            except (ValueError, TypeError):
                pass
        return self.env["helpdesk.ticket.team"]

    def _is_noc_leader(self):
        team = self._get_noc_team()
        return bool(team.user_id and self.env.user == team.user_id)

    @api.depends("user_id")
    @api.depends_context("uid")
    def _compute_is_own_record(self):
        for rec in self:
            rec.is_own_record = rec.user_id == self.env.user

    @api.depends_context("uid")
    def _compute_can_approve(self):
        is_leader = self._is_noc_leader()
        for rec in self:
            rec.can_approve = is_leader

    def _check_can_approve(self):
        if not self._is_noc_leader():
            team = self._get_noc_team()
            raise UserError(
                _(
                    "Apenas o líder da equipe %s"
                    "pode aprovar ou recusar solicitações de férias.",
                    team.name,
                )
            )

    # ── Controle de acesso ─────────────────────────────────────────────────

    @api.model
    def _search(
        self,
        domain,
        offset=0,
        limit=None,
        order=None,
        count=False,
        access_rights_uid=None,
    ):
        """Líder do NOC enxerga todos os registros; demais usuários só os próprios."""
        if self._is_noc_leader():
            return super(HelpdeskFerias, self.sudo())._search(
                domain,
                offset=offset,
                limit=limit,
                order=order,
                count=count,
                access_rights_uid=access_rights_uid,
            )
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            count=count,
            access_rights_uid=access_rights_uid,
        )

    def check_access_rule(self, operation):
        """Líder do NOC tem acesso de leitura e escrita a todos os registros.
        Quais campos o líder pode escrever em registros alheios é
        controlado pelo write()."""
        if self._is_noc_leader() and operation in ("read", "write"):
            return
        return super().check_access_rule(operation)

    _LEADER_WRITABLE_FIELDS = frozenset({"substitute_id"})

    def write(self, vals):
        """Usuários só podem escrever nos próprios registros.
        Exceção: líder NOC pode escrever substitute_id em registros alheios.
        Transições de estado (aprovar/recusar/redefinir) usam _state_write()
        que contorna este guard via super() com sudo."""
        if self.env.su:
            return super().write(vals)

        foreign_records = self.filtered(lambda r: r.user_id != self.env.user)
        if foreign_records:
            if (
                self._is_noc_leader()
                and set(vals.keys()) <= self._LEADER_WRITABLE_FIELDS
            ):
                return super().write(vals)
            raise UserError(
                _("Você só pode editar suas próprias solicitações de férias.")
            )
        return super().write(vals)

    def _state_write(self, vals):
        """Escrita privilegiada para transições de estado autorizadas.
        Bypassa write() e record rules via super()+sudo, preservando tracking."""
        return super(HelpdeskFerias, self.sudo()).write(vals)

    @api.depends("user_id", "date_from")
    def _compute_name(self):
        for rec in self:
            if rec.user_id and rec.date_from:
                month = rec.date_from.strftime("%b/%Y")
                rec.name = f"Férias – {rec.user_id.name} ({month})"
            else:
                rec.name = "Nova Solicitação"

    @api.depends("date_from", "date_to")
    def _compute_duration(self):
        for rec in self:
            if rec.date_from and rec.date_to:
                rec.duration = (rec.date_to - rec.date_from).days + 1
            else:
                rec.duration = 0

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(
                    _("A data de fim deve ser igual ou posterior à data de início.")
                )

    # ── Ações de estado ─────────────────────────────────────────────────────

    def _notify_noc_leader_on_submit(self):
        noc_team = self._get_noc_team()
        leader = noc_team.user_id if noc_team else None
        if not leader or not leader.partner_id:
            _logger.warning(
                "helpdesk.ferias: líder da equipe NOC não configurado; "
                "notificação de aprovação não enviada (record %s).",
                self.id,
            )
            return
        self.message_subscribe(partner_ids=[leader.partner_id.id])
        self.env["bus.bus"].sudo()._sendone(
            leader.partner_id,
            "noc_helpdesk/ferias_alert",
            {
                "ferias_id": self.id,
                "employee_name": self.user_id.name,
                "date_from": self.date_from.strftime("%d/%m/%Y"),
                "date_to": self.date_to.strftime("%d/%m/%Y"),
                "duration": self.duration,
            },
        )

    def action_submit(self):
        self.write({"state": "submitted"})
        self._notify_noc_leader_on_submit()

    def action_approve(self):
        self._check_can_approve()
        for rec in self:
            if rec.is_plantao_member and not rec.substitute_id:
                raise UserError(
                    _(
                        "O colaborador %s faz parte do time de plantão. "
                        "É obrigatório designar um substituto antes de aprovar.",
                        rec.user_id.name,
                    )
                )
        self._state_write({"state": "approved", "approver_id": self.env.user.id})

    def action_refuse(self):
        self._check_can_approve()
        self._state_write({"state": "refused", "approver_id": self.env.user.id})

    def action_reset(self):
        self._state_write({"state": "draft", "approver_id": False})
