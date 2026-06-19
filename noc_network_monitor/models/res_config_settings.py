import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    network_monitor_url = fields.Char(
        string="URL do Servidor de Monitoramento",
        config_parameter="noc_network_monitor.url",
        help="Endpoint GET que retorna o JSON com os resultados dos testes de rede.",
    )
    network_monitor_token = fields.Char(
        string="Token de Autenticação",
        config_parameter="noc_network_monitor.token",
        help="Token enviado no header Authorization: Bearer <token> (opcional).",
    )
    network_monitor_team_id = fields.Many2one(
        comodel_name="helpdesk.ticket.team",
        string="Equipe do Helpdesk",
        help="Equipe que receberá os chamados gerados pelo monitoramento.",
    )
    network_monitor_close_delay = fields.Integer(
        string="Delay para Fechar após Normalização (min)",
        default=30,
        config_parameter="noc_network_monitor.close_delay",
        help=(
            "Minutos com alarme resolvido antes de fechar o chamado automaticamente."
        ),
    )
    network_monitor_reopen_window = fields.Integer(
        string="Janela de Reabertura (horas)",
        default=6,
        config_parameter="noc_network_monitor.reopen_window",
        help=(
            "Se o circuito falhar novamente dentro deste período após o"
            " fechamento, o chamado será reaberto em vez de criar um novo."
        ),
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env["ir.config_parameter"].sudo()
        team_id_raw = ICP.get_param("noc_network_monitor.team_id", False)

        # FIX: o valor salvo pode ser uma string vazia, "False", ou um int válido.
        # Qualquer coisa que não converta para int positivo é tratada como False,
        # evitando que um ID inválido chegue ao Many2one e gere _unknown.
        team_id = False
        if team_id_raw:
            try:
                parsed = int(team_id_raw)
                if parsed > 0:
                    # Confirma que o registro ainda existe no banco
                    if self.env["helpdesk.ticket.team"].browse(parsed).exists():
                        team_id = parsed
            except (ValueError, TypeError):
                _logger.warning("Descrição do erro", exc_info=True)

        res["network_monitor_team_id"] = team_id
        return res

    def set_values(self):
        res = super().set_values()
        ICP = self.env["ir.config_parameter"].sudo()

        # FIX: era `(self.network_monitor_team_id.id ...,)` — vírgula ao final
        # criava uma tupla "(123,)" que era salva como string no ir.config_parameter,
        # impossibilitando a conversão para int no get_values e gerando _unknown.
        ICP.set_param(
            "noc_network_monitor.team_id",
            self.network_monitor_team_id.id if self.network_monitor_team_id else "",
        )
        return res
