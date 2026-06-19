import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    noc_helpdesk_shift_day_start_hour = fields.Integer(
        string="Hora Início Turno Diurno",
        default=7,
        config_parameter="noc_helpdesk.shift_day_start_hour",
        help="Hora (0–23) em que o turno diurno começa. Padrão: 7.",
    )
    noc_helpdesk_shift_night_start_hour = fields.Integer(
        string="Hora Início Turno Noturno",
        default=19,
        config_parameter="noc_helpdesk.shift_night_start_hour",
        help="Hora (0–23) em que o turno noturno começa. Padrão: 19.",
    )
    noc_helpdesk_shift_change_window_minutes = fields.Integer(
        string="Janela de Troca de Turno (min)",
        default=30,
        config_parameter="noc_helpdesk.shift_change_window_minutes",
        help=(
            "Minutos após o início do turno em que o sistema considera que a troca "
            "ainda está em andamento. Padrão: 30."
        ),
    )
    noc_helpdesk_new_ticket_interval_minutes = fields.Integer(
        string="Intervalo de Verificação de Novos Chamados (min)",
        default=30,
        config_parameter="noc_helpdesk.new_ticket_check_interval_minutes",
        help=(
            "Minutos entre verificações de novos chamados não atribuídos. Padrão: 30."
        ),
    )
    noc_helpdesk_teams_webhook_url = fields.Char(
        string="Webhook MS Teams (Chamados Críticos)",
        config_parameter="noc_helpdesk.teams_critical_webhook_url",
        help=(
            "URL do webhook do canal Teams que recebe alertas de chamados críticos. "
            "Deixe em branco para desativar."
        ),
    )
    noc_helpdesk_noc_team_id = fields.Many2one(
        comodel_name="helpdesk.ticket.team",
        string="Equipe NOC",
        help="Equipe usada como referência para aprovação de férias e escala.",
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        team_id_raw = ICP.get_param("noc_helpdesk.noc_team_id", False)

        team_id = False
        if team_id_raw:
            try:
                parsed = int(team_id_raw)
                if (
                    parsed > 0
                    and self.env["helpdesk.ticket.team"].browse(parsed).exists()
                ):
                    team_id = parsed
            except (ValueError, TypeError):
                _logger.warning(
                    "Valor inválido em noc_helpdesk.noc_team_id: %r", team_id_raw
                )

        res["noc_helpdesk_noc_team_id"] = team_id
        return res

    def set_values(self):
        res = super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param(
            "noc_helpdesk.noc_team_id",
            self.noc_helpdesk_noc_team_id.id
            if self.noc_helpdesk_noc_team_id
            else "",
        )
        return res
