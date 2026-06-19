from odoo import fields, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # Marca que o chamado foi criado pelo monitor automático
    monitor_origin = fields.Selection(
        selection=[("network_monitor", "Monitor de Rede")],
        string="Origem do Monitor",
        readonly=True,
        index=True,
        help=(
            "Preenchido automaticamente quando o chamado"
            " é criado pelo monitor de rede."
        ),
    )

    # Momento em que o circuito foi detectado como normalizado
    # (usado para calcular o delay de fechamento)
    monitor_normalized_since = fields.Datetime(
        string="Normalizado desde",
        readonly=True,
        help="Data/hora em que o monitor detectou a normalização do circuito. "
        "O chamado será fechado após o delay configurado.",
    )

    # Momento em que o chamado foi fechado pelo monitor
    # (usado para calcular a janela de reabertura)
    monitor_closed_at = fields.Datetime(
        string="Fechado pelo Monitor em",
        readonly=True,
        help="Data/hora em que o monitor fechou este chamado automaticamente. "
        "Usado para controle da janela de reabertura.",
    )

    # Log de monitoramento relacionados
    monitor_log_ids = fields.One2many(
        comodel_name="network.monitor.log",
        inverse_name="ticket_id",
        string="Logs de Monitoramento",
        readonly=True,
    )
    monitor_log_count = fields.Integer(
        string="Logs",
        compute="_compute_monitor_log_count",
    )

    def _compute_monitor_log_count(self):
        for rec in self:
            rec.monitor_log_count = len(rec.monitor_log_ids)

    def action_view_monitor_logs(self):
        self.ensure_one()
        return {
            "name": "Logs de Monitoramento",
            "type": "ir.actions.act_window",
            "res_model": "network.monitor.log",
            "view_mode": "tree,form",
            "domain": [("ticket_id", "=", self.id)],
        }
