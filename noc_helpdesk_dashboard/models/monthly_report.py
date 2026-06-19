from odoo import api, fields, models


class NOCMonthlyReport(models.Model):
    _name = "noc.monthly.report"
    _description = "Monthly Network Report"
    _order = "year desc, month desc"
    _rec_name = "name"

    name = fields.Char(string="Period", compute="_compute_name", store=True)
    month = fields.Integer(string="Month", required=True)
    year = fields.Integer(string="Year", required=True)

    # Goals
    meta_falha_massiva = fields.Integer(string="Massive Failures Goal", default=0)
    meta_eventos_amarelos = fields.Integer(string="Yellow Events Goal (Links)", default=0)
    meta_disponibilidade_backbone = fields.Float(
        string="Backbone Availability Goal (%)", default=0.0, digits=(5, 2)
    )
    meta_descartes_pacotes = fields.Integer(string="Packet Loss Goal", default=0)
    meta_latencia = fields.Integer(string="Latency Goal (ms)", default=0)

    # Backbone config
    backbone_circuit_type_ids = fields.Many2many(
        comodel_name="network.circuit.type",
        relation="noc_monthly_report_backbone_type_rel",
        column1="relatorio_id",
        column2="circuit_type_id",
        string="Backbone Circuit Types",
    )
    total_backbone_circuits = fields.Integer(string="Total Backbone Circuits", default=0)

    # Analysis — Massive Failure
    analise_falha_massiva = fields.Text(string="Deviations — Massive Failure")
    acao_falha_massiva = fields.Text(string="Systemic Action — Massive Failure")

    # Analysis — Yellow Events
    analise_eventos_amarelos = fields.Text(string="Deviations — Yellow Events")
    acao_eventos_amarelos = fields.Text(string="Systemic Action — Yellow Events")

    # Analysis — Backbone Availability
    analise_disponibilidade = fields.Text(string="Deviations — Availability")
    acao_disponibilidade = fields.Text(string="Systemic Action — Availability")

    # Analysis — Packet Loss
    analise_descartes = fields.Text(string="Deviations — Packet Loss")
    acao_descartes = fields.Text(string="Systemic Action — Packet Loss")

    # Analysis — Latency
    analise_latencia = fields.Text(string="Deviations — Latency")
    acao_latencia = fields.Text(string="Systemic Action — Latency")

    _sql_constraints = [
        (
            "unique_month_year",
            "UNIQUE(month, year)",
            "A report configuration for this month/year already exists.",
        )
    ]

    @api.depends("month", "year")
    def _compute_name(self):
        _MONTHS = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December",
        }
        for rec in self:
            rec.name = (
                f"{_MONTHS.get(rec.month, rec.month)}/{rec.year}"
                if rec.month and rec.year
                else ""
            )