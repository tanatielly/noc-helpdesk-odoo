COLOR_HEX = {
    "red": "#dc2626",
    "yellow": "#d97706",
    "green": "#16a34a",
    "gray": "#64748b",
}

# Metadados dos 5 KPIs do Relatório Mensal — única fonte de verdade
# reaproveitada tanto pelo template QWeb (PDF) quanto pelo builder do
# PowerPoint, para que nunca divirjam.
KPI_SPECS = [
    {
        "key": "falha_massiva",
        "title": "Falha Massiva Backbone",
        "meta_field": "meta_falha_massiva",
        "analise_field": "analise_falha_massiva",
        "acao_field": "acao_falha_massiva",
        "percent": False,
        "top_table": False,
    },
    {
        "key": "eventos_amarelos",
        "title": "Eventos Amarelos — Indisponibilidade de Links",
        "meta_field": "meta_eventos_amarelos",
        "analise_field": "analise_eventos_amarelos",
        "acao_field": "acao_eventos_amarelos",
        "percent": False,
        "top_table": True,
        "top_title": "Top 5 — Links Indisponíveis",
    },
    {
        "key": "disponibilidade",
        "title": "Disponibilidade da Rede Backbone",
        "meta_field": "meta_disponibilidade_backbone",
        "analise_field": "analise_disponibilidade",
        "acao_field": "acao_disponibilidade",
        "percent": True,
        "top_table": False,
    },
    {
        "key": "descartes_pacotes",
        "title": "Descartes de Pacotes",
        "meta_field": "meta_descartes_pacotes",
        "analise_field": "analise_descartes",
        "acao_field": "acao_descartes",
        "percent": False,
        "top_table": True,
        "top_title": "Top 5 — Links com Descartes",
    },
    {
        "key": "latencia",
        "title": "Latência",
        "meta_field": "meta_latencia",
        "analise_field": "analise_latencia",
        "acao_field": "acao_latencia",
        "percent": False,
        "top_table": True,
        "top_title": "Top 5 — Links com Latência",
    },
]


def compute_semaforo_map(report_data):
    """Espelha a lógica de semaforo() em relatorio_mensal.js."""
    kpis = report_data.get("kpis", {})
    cfg = report_data.get("config", {})
    result = {}
    for kpi, val in kpis.items():
        if val is None:
            result[kpi] = "gray"
        elif kpi == "falha_massiva":
            result[kpi] = "green" if val == 0 else "red"
        elif kpi in ("eventos_amarelos", "latencia"):
            meta = cfg.get(f"meta_{kpi}")
            if val < meta:
                result[kpi] = "green"
            elif val == meta:
                result[kpi] = "yellow"
            else:
                result[kpi] = "red"
        elif kpi == "disponibilidade":
            result[kpi] = (
                "green" if val >= cfg.get("meta_disponibilidade_backbone") else "red"
            )
        elif kpi == "descartes_pacotes":
            result[kpi] = "green" if val <= cfg.get("meta_descartes_pacotes") else "red"
        else:
            result[kpi] = "gray"
    return result
