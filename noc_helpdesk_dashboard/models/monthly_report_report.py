from odoo import models

from .relatorio_mensal_common import KPI_SPECS, compute_semaforo_map


class ReportRelatorioMensal(models.AbstractModel):
    _name = "report.noc_helpdesk_dashboard.relatorio_mensal_pdf"
    _description = "Relatório Mensal — Rede Backbone (PDF)"

    def _get_report_values(self, docids, data=None):
        report_data = (data or {}).get("report_data", {})
        return {
            "report_data": report_data,
            "semaforo": compute_semaforo_map(report_data),
            "kpi_specs": KPI_SPECS,
        }
