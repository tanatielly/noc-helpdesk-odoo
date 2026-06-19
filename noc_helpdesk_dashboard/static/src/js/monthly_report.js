/** @odoo-module **/
/* global Chart */

import {Component, onMounted, onWillUnmount, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {session} from "@web/session";

const TEAL = {border: "#0d9488", bg: "#0d9488cc"};

const CHART_IDS = {
    falha_massiva: "rm-chart-falha-massiva",
    eventos_amarelos: "rm-chart-eventos-amarelos",
    disponibilidade: "rm-chart-disponibilidade",
    descartes_pacotes: "rm-chart-descartes-pacotes",
    latencia: "rm-chart-latencia",
};

function buildAvailableMonths() {
    const now = new Date();
    const months = [];
    const PT = [
        "",
        "Janeiro",
        "Fevereiro",
        "Março",
        "Abril",
        "Maio",
        "Junho",
        "Julho",
        "Agosto",
        "Setembro",
        "Outubro",
        "Novembro",
        "Dezembro",
    ];
    for (let i = 12; i >= 0; i--) {
        const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const m = d.getMonth() + 1;
        const y = d.getFullYear();
        months.push({value: `${y}-${m}`, label: `${PT[m]}/${y}`});
    }
    return months;
}

export class RelatórioMensal extends Component {
    static template = "noc_helpdesk_dashboard.RelatórioMensal";

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        const now = new Date();
        const defaultMonth = `${now.getFullYear()}-${now.getMonth() + 1}`;

        this.state = useState({
            loading: false,
            error: null,
            data: null,
            cfg: {},
            sugestoes: {},
            selectedMonth: defaultMonth,
            availableMonths: buildAvailableMonths(),
            canEdit: Boolean(session.is_admin),
            isDirty: false,
            saving: false,
        });

        this._charts = {};

        onMounted(() => {
            const el = document.querySelector(".rm-wrapper");
            if (el) {
                let parent = el.parentElement;
                while (parent) {
                    const style = window.getComputedStyle(parent);
                    if (style.overflow === "hidden" || style.overflowY === "hidden") {
                        parent.style.overflowY = "auto";
                    }
                    parent = parent.parentElement;
                    if (parent === document.body) break;
                }
            }
            this.loadData();
        });
        onWillUnmount(() => this._destroyCharts());
    }

    async loadData() {
        this._destroyCharts();
        this.state.loading = true;
        this.state.error = null;
        const [y, m] = this.state.selectedMonth.split("-").map(Number);
        try {
            const data = await this.rpc(
                "/network_helpdesk_dashboard/relatorio_mensal",
                {
                    month: m,
                    year: y,
                }
            );
            if (data.error) throw new Error(data.error);
            this.state.data = data;
            this.state.isDirty = false;
            this.state.sugestoes = data.sugestoes || {};
            const cfg = Object.assign({}, data.config);
            const sug = data.sugestoes || {};
            const autoFields = [
                "analise_falha_massiva",
                "acao_falha_massiva",
                "analise_eventos_amarelos",
                "acao_eventos_amarelos",
                "analise_disponibilidade",
                "acao_disponibilidade",
                "analise_descartes",
                "acao_descartes",
                "analise_latencia",
                "acao_latencia",
            ];
            for (const f of autoFields) {
                if (!cfg[f] && sug[f]) cfg[f] = sug[f];
            }
            this.state.cfg = cfg;
            setTimeout(() => this._updateCharts(), 150);
        } catch (e) {
            this.state.error = `Erro ao carregar dados: ${e.message}`;
        } finally {
            this.state.loading = false;
        }
    }

    printReport() {
        const [y, m] = this.state.selectedMonth.split("-").map(Number);
        window.open(
            `/network_helpdesk_dashboard/relatorio_mensal/print?month=${m}&year=${y}`,
            "_blank"
        );
    }

    exportPpt() {
        const [y, m] = this.state.selectedMonth.split("-").map(Number);
        window.open(
            `/network_helpdesk_dashboard/relatorio_mensal/export_pptx?month=${m}&year=${y}`,
            "_blank"
        );
    }

    setMonth(value) {
        this.state.selectedMonth = value;
        this.loadData();
    }

    updateText(field, value) {
        this.state.cfg[field] = value;
        this.state.isDirty = true;
    }

    async saveConfig() {
        if (!this.state.data) return;
        const [y, m] = this.state.selectedMonth.split("-").map(Number);
        this.state.saving = true;
        try {
            const res = await this.rpc(
                "/network_helpdesk_dashboard/relatorio_mensal/config",
                {month: m, year: y, ...this.state.cfg}
            );
            if (res.error) throw new Error(res.error);
            this.state.isDirty = false;
            this.notification.add("Análise salva com sucesso.", {type: "success"});
        } catch (e) {
            this.notification.add(`Erro ao salvar: ${e.message}`, {type: "danger"});
        } finally {
            this.state.saving = false;
        }
    }

    sugerir(campo) {
        const sug = this.state.sugestoes[campo];
        if (sug) this.state.cfg[campo] = sug;
    }

    semaforo(kpi) {
        const d = this.state.data;
        if (!d) return "gray";
        const val = d.kpis[kpi];
        const cfg = d.config;
        if (val === null || val === undefined) return "gray";

        if (kpi === "falha_massiva") {
            return val === 0 ? "green" : "red";
        }
        if (kpi === "eventos_amarelos" || kpi === "latencia") {
            if (val < cfg[`meta_${kpi}`]) return "green";
            if (val === cfg[`meta_${kpi}`]) return "yellow";
            return "red";
        }
        if (kpi === "disponibilidade") {
            return val >= cfg.meta_disponibilidade_backbone ? "green" : "red";
        }
        if (kpi === "descartes_pacotes") {
            return val <= cfg.meta_descartes_pacotes ? "green" : "red";
        }
        return "gray";
    }

    _destroyCharts() {
        for (const chart of Object.values(this._charts)) {
            if (chart) chart.destroy();
        }
        this._charts = {};
    }

    _updateCharts() {
        if (!this.state.data) return;
        const {historico_labels: labels, historico} = this.state.data;

        const configs = [
            {
                key: "falha_massiva",
                data: historico.falha_massiva,
                title: "FALHA MASSIVA BACKBONE — HISTÓRICO",
            },
            {
                key: "eventos_amarelos",
                data: historico.eventos_amarelos,
                title: "EVENTOS AMARELOS — HISTÓRICO",
            },
            {
                key: "disponibilidade",
                data: historico.disponibilidade,
                title: "DISPONIBILIDADE BACKBONE — HISTÓRICO",
                nullToZero: true,
            },
            {
                key: "descartes_pacotes",
                data: historico.descartes_pacotes,
                title: "DESCARTES DE PACOTES — HISTÓRICO",
            },
            {key: "latencia", data: historico.latencia, title: "LATÊNCIA — HISTÓRICO"},
        ];

        Chart.defaults.color = "#94a3b8";
        Chart.defaults.font.family =
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
        Chart.defaults.font.size = 11;

        for (const {key, data, title, nullToZero} of configs) {
            const el = document.getElementById(CHART_IDS[key]);
            if (!el) continue;
            if (this._charts[key]) {
                this._charts[key].destroy();
            }
            const chartData = nullToZero ? data.map((v) => (v === null ? 0 : v)) : data;
            this._charts[key] = new Chart(el, {
                type: "bar",
                data: {
                    labels,
                    datasets: [
                        {
                            label: title,
                            data: chartData,
                            backgroundColor: TEAL.bg,
                            borderColor: TEAL.border,
                            borderWidth: 1,
                            borderRadius: 3,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: "top",
                            labels: {font: {size: 10}},
                        },
                    },
                    scales: {
                        x: {ticks: {font: {size: 9}}, grid: {display: false}},
                        y: {ticks: {font: {size: 9}}, beginAtZero: true},
                    },
                },
            });
        }
    }
}

registry.category("actions").add("noc_monthly_report", RelatórioMensal);
