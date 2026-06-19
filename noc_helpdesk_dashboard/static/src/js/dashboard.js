/** @odoo-module **/
/* global Chart */

import {Component, onMounted, onWillUnmount, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

const COLORS = {
    blue: {border: "#2563eb", bg: "#dbeafe"},
    red: {border: "#dc2626", bg: "#fee2e2"},
    green: {border: "#16a34a", bg: "#dcfce7"},
    yellow: {border: "#b45309", bg: "#fef3c7"},
    purple: {border: "#7c3aed", bg: "#ede9fe"},
    teal: {border: "#0891b2", bg: "#cffafe"},
    orange: {border: "#d97706", bg: "#fed7aa"},
    gray: {border: "#64748b", bg: "#e2e8f0"},
};

export class NetworkHelpdeskDashboard extends Component {
    static template = "network_helpdesk_dashboard.Dashboard";

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.busService = useService("bus_service");

        this.openTicket = (id) => {
            if (!id) return;
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "helpdesk.ticket",
                res_id: id,
                views: [[false, "form"]],
                target: "current",
            });
        };

        this.openCircuit = (id) => {
            if (!id) return;
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "network.circuit",
                res_id: id,
                views: [[false, "form"]],
                target: "current",
            });
        };

        this.openTicketList = async (filter) => {
            const action = await this.rpc(
                "/network_helpdesk_dashboard/ticket_list_action",
                {filter_type: filter, period: this.state.period}
            );
            this.actionService.doAction(action, {clearBreadcrumbs: true});
        };

        this.state = useState({
            loading: true,
            filterLoading: false,
            period: "30d",
            data: null,
            errorMsg: null,
            activeFilters: {tags: [], provider_id: null, health: [], stage_ids: []},
            drilldown: {
                circuit_id: null,
                circuit_name: null,
                tickets: [],
                loading: false,
            },
            tableSearch: "",
            plantao: null,
        });

        this.charts = {};
        this.refreshInterval = null;
        this._busReloadPending = false;

        this._onBusNotification = ({detail: notifications}) => {
            for (const {type} of notifications) {
                if (type === "noc_helpdesk/ticket_update") {
                    if (!this._busReloadPending) {
                        this._busReloadPending = true;
                        setTimeout(async () => {
                            this._busReloadPending = false;
                            await this.loadData();
                        }, 800);
                    }
                    break;
                }
            }
        };

        onMounted(async () => {
            const el = document.querySelector(".nd-wrapper");
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
            this.busService.addEventListener("notification", this._onBusNotification);
            this.busService.start();
            await Promise.all([this.loadData(), this.loadPlantao()]);
            this.refreshInterval = setInterval(async () => {
                await Promise.all([this.loadData(), this.loadPlantao()]);
            }, 5 * 60 * 1000);
        });

        onWillUnmount(() => {
            this.busService.removeEventListener(
                "notification",
                this._onBusNotification
            );
            if (this.refreshInterval) clearInterval(this.refreshInterval);
            Object.values(this.charts).forEach((c) => c.destroy());
        });
    }

    // ── Data loading ──────────────────────────────────────────────────

    async loadData() {
        this.state.errorMsg = null;
        try {
            const data = await this.rpc("/network_helpdesk_dashboard/data", {
                period: this.state.period,
                tags: this.state.activeFilters.tags,
                provider_id: this.state.activeFilters.provider_id,
                health: this.state.activeFilters.health,
                stage_ids: this.state.activeFilters.stage_ids,
            });

            if (!data || data.error) {
                const msg =
                    data && data.error ? data.error : "Resposta inválida do servidor.";
                this.state.errorMsg = msg;
                this.state.loading = false;
                this.state.filterLoading = false;
                return;
            }

            this.state.data = data;
            this.state.loading = false;
            this.state.filterLoading = false;
            setTimeout(() => this.renderCharts(data), 150);
        } catch (e) {
            this.state.loading = false;
            this.state.filterLoading = false;
            this.state.errorMsg = e.message || "Erro desconhecido.";
        }
    }

    async loadPlantao() {
        try {
            const data = await this.rpc(
                "/network_helpdesk_dashboard/plantao_status",
                {}
            );
            if (data && !data.error) {
                this.state.plantao = data;
            }
        } catch (_e) {
            // Plantão indisponível — não bloqueia o dashboard
        }
    }

    async setPeriod(period) {
        this.state.period = period;
        this.state.loading = true;
        await this.loadData();
    }

    // ── Filter methods ────────────────────────────────────────────────

    get hasActiveFilters() {
        const f = this.state.activeFilters;
        return (
            f.tags.length > 0 ||
            f.provider_id !== null ||
            f.health.length > 0 ||
            f.stage_ids.length > 0
        );
    }

    toggleTagFilter(tag) {
        const tags = this.state.activeFilters.tags;
        const idx = tags.indexOf(tag);
        if (idx >= 0) {
            tags.splice(idx, 1);
        } else {
            tags.push(tag);
        }
        this.state.filterLoading = true;
        this.loadData();
    }

    setProviderFilter(providerId) {
        this.state.activeFilters.provider_id = providerId ? Number(providerId) : null;
        this.state.filterLoading = true;
        this.loadData();
    }

    toggleHealthFilter(level) {
        const health = this.state.activeFilters.health;
        const idx = health.indexOf(level);
        if (idx >= 0) {
            health.splice(idx, 1);
        } else {
            health.push(level);
        }
        this.state.filterLoading = true;
        this.loadData();
    }

    toggleStageFilter(stageId) {
        const ids = this.state.activeFilters.stage_ids;
        const id = Number(stageId);
        const idx = ids.indexOf(id);
        if (idx >= 0) {
            ids.splice(idx, 1);
        } else {
            ids.push(id);
        }
        this.state.filterLoading = true;
        this.loadData();
    }

    clearFilters() {
        this.state.activeFilters.tags = [];
        this.state.activeFilters.provider_id = null;
        this.state.activeFilters.health = [];
        this.state.activeFilters.stage_ids = [];
        this.state.filterLoading = true;
        this.loadData();
    }

    // ── Drill-down ────────────────────────────────────────────────────

    async drillCircuit(circuitId, circuitName) {
        if (this.state.drilldown.circuit_id === circuitId) {
            this.state.drilldown.circuit_id = null;
            this.state.drilldown.circuit_name = null;
            this.state.drilldown.tickets = [];
            return;
        }
        this.state.drilldown.circuit_id = circuitId;
        this.state.drilldown.circuit_name = circuitName;
        this.state.drilldown.loading = true;
        this.state.drilldown.tickets = [];
        try {
            const result = await this.rpc(
                "/network_helpdesk_dashboard/circuit_tickets",
                {circuit_id: circuitId, period: this.state.period}
            );
            this.state.drilldown.tickets = (result && result.tickets) || [];
        } catch (e) {
            this.state.drilldown.tickets = [];
        }
        this.state.drilldown.loading = false;
    }

    // ── Table search & getters ────────────────────────────────────────

    setTableSearch(value) {
        this.state.tableSearch = value;
    }

    getStageName(stageId) {
        const stages = this.state.data && this.state.data.available_stages;
        if (!stages) return `#${stageId}`;
        const found = stages.find((s) => s.id === stageId);
        return found ? found.name : `#${stageId}`;
    }

    get filteredCircuitStats() {
        const stats = this.state.data && this.state.data.circuit_stats;
        if (!stats) return [];
        const q = this.state.tableSearch.toLowerCase().trim();
        if (!q) return stats;
        return stats.filter(
            (c) =>
                c.name.toLowerCase().includes(q) ||
                c.provider.toLowerCase().includes(q) ||
                c.main_tag.toLowerCase().includes(q)
        );
    }

    get filteredRecentTickets() {
        const tickets = this.state.data && this.state.data.recent_tickets;
        if (!tickets) return [];
        const q = this.state.tableSearch.toLowerCase().trim();
        if (!q) return tickets;
        return tickets.filter(
            (t) =>
                t.name.toLowerCase().includes(q) ||
                t.tag.toLowerCase().includes(q) ||
                t.stage.toLowerCase().includes(q) ||
                t.user.toLowerCase().includes(q) ||
                (t.circuit && t.circuit.toLowerCase().includes(q))
        );
    }

    // ── Charts ────────────────────────────────────────────────────────

    renderCharts(data) {
        this.destroyCharts();
        if (!data) return;

        this._applyChartDefaults();
        if (data.mensal) this._renderMensal(data.mensal);
        if (data.tags) this._renderTags(data.tags);
        this._renderIncidentesPorSite(
            data.incidentes_por_site || {labels: [], values: []}
        );
        if (data.tag_by_month) this._renderTagMes(data.tag_by_month);
        if (data.tma_by_tag) this._renderTma(data.tma_by_tag);
        if (data.trend) this._renderTrend(data.trend);
    }

    _applyChartDefaults() {
        const tickColor = "#94a3b8";
        Chart.defaults.color = tickColor;
        Chart.defaults.font.family =
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
        Chart.defaults.font.size = 11;
    }

    _renderMensal(mensal) {
        const grid = "rgba(0,0,0,0.05)";
        this._chart(
            "chartMensal",
            "bar",
            {
                labels: mensal.labels || [],
                datasets: [
                    {
                        label: "Abertos",
                        data: mensal.abertos || [],
                        backgroundColor: COLORS.red.bg,
                        borderColor: COLORS.red.border,
                        borderWidth: 1.5,
                        borderRadius: 5,
                    },
                    {
                        label: "Resolvidos",
                        data: mensal.resolvidos || [],
                        backgroundColor: COLORS.green.bg,
                        borderColor: COLORS.green.border,
                        borderWidth: 1.5,
                        borderRadius: 5,
                    },
                ],
            },
            {scales: {x: {grid: {color: grid}}, y: {grid: {color: grid}}}}
        );
    }

    _renderTags(tags) {
        const tagLabels = tags.labels || [];
        const tagValues = tags.values || [];
        if (!tagLabels.length) return;

        const tagBgColors = tagLabels.map((l) => this._tagColor(l).bg);
        const tagBorderColors = tagLabels.map((l) => this._tagColor(l).border);

        this._chart(
            "chartTags",
            "doughnut",
            {
                labels: tagLabels,
                datasets: [
                    {
                        data: tagValues,
                        backgroundColor: tagBgColors,
                        borderColor: tagBorderColors,
                        borderWidth: 1.5,
                    },
                ],
            },
            {
                cutout: "62%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {color: "#475569", boxWidth: 10},
                    },
                },
                onClick: (event, elements) => {
                    if (!elements.length) return;
                    const label = tagLabels[elements[0].index];
                    this.toggleTagFilter(label);
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length
                        ? "pointer"
                        : "default";
                },
            }
        );
    }

    _renderIncidentesPorSite(siteData) {
        const labels = siteData.labels || [];
        const values = siteData.values || [];
        if (!labels.length) return;

        const grid = "rgba(0,0,0,0.05)";
        this._chart(
            "chartSite",
            "bar",
            {
                labels,
                datasets: [
                    {
                        label: "Incidentes",
                        data: values,
                        backgroundColor: COLORS.blue.bg,
                        borderColor: COLORS.blue.border,
                        borderWidth: 1.5,
                        borderRadius: 4,
                    },
                ],
            },
            {
                indexAxis: "y",
                plugins: {legend: {display: false}},
                scales: {
                    x: {grid: {color: grid}, ticks: {stepSize: 1}},
                    y: {grid: {display: false}, ticks: {font: {size: 11}}},
                },
            }
        );
    }

    _renderTagMes(tagByMonth) {
        const grid = "rgba(0,0,0,0.05)";
        const tagSeries = Object.entries(tagByMonth.series || {});
        if (!tagSeries.length) return;

        this._chart(
            "chartTagMes",
            "bar",
            {
                labels: tagByMonth.labels || [],
                datasets: tagSeries.map(([label, values]) => ({
                    label,
                    data: values || [],
                    backgroundColor: this._tagColor(label).bg,
                    borderColor: this._tagColor(label).border,
                    borderWidth: 1,
                    borderRadius: 3,
                })),
            },
            {
                scales: {
                    x: {stacked: true, grid: {color: grid}},
                    y: {stacked: true, grid: {color: grid}},
                },
            }
        );
    }

    _renderTma(tmaByTag) {
        const grid = "rgba(0,0,0,0.05)";
        const tmaEntries = Object.entries(tmaByTag || {});
        if (!tmaEntries.length) return;

        this._chart(
            "chartTma",
            "bar",
            {
                labels: tmaEntries.map(([k]) => k),
                datasets: [
                    {
                        label: "TMA (horas)",
                        data: tmaEntries.map(([, v]) => v),
                        backgroundColor: tmaEntries.map(([k]) => this._tagColor(k).bg),
                        borderColor: tmaEntries.map(([k]) => this._tagColor(k).border),
                        borderWidth: 1.5,
                        borderRadius: 5,
                    },
                ],
            },
            {
                indexAxis: "y",
                plugins: {legend: {display: false}},
                scales: {
                    x: {grid: {color: grid}},
                    y: {grid: {color: "transparent"}},
                },
            }
        );
    }

    _renderTrend(trend) {
        const grid = "rgba(0,0,0,0.05)";
        const tagSeries = Object.entries(trend.series || {});
        if (!tagSeries.length) return;

        this._chart(
            "chartTrend",
            "line",
            {
                labels: trend.labels || [],
                datasets: tagSeries.map(([label, values]) => ({
                    label,
                    data: values || [],
                    borderColor: this._tagColor(label).border,
                    backgroundColor: this._tagColor(label).bg + "28",
                    tension: 0.4,
                    fill: true,
                    pointRadius: 3,
                })),
            },
            {scales: {x: {grid: {color: grid}}, y: {grid: {color: grid}}}}
        );
    }

    // ── Helpers ───────────────────────────────────────────────────────

    _tagColor(tag = "") {
        const t = tag.toLowerCase();
        if (t.includes("equipamento isolado")) return COLORS.gray;
        if (t.includes("falha massiva")) return COLORS.orange;
        if (t.includes("porta agrega")) return COLORS.red;
        if (t.includes("sinergia")) return COLORS.green;
        if (t.includes("manutenção programada") || t.includes("manutencao programada"))
            return COLORS.green;
        if (t.includes("intermitente")) return COLORS.teal;
        if (t.includes("sistemas")) return COLORS.blue;
        if (t.includes("indispon")) return COLORS.red;
        if (t.includes("lat")) return COLORS.purple;
        if (t.includes("descarte")) return COLORS.yellow;
        if (t.includes("oscil")) return COLORS.teal;
        return COLORS.blue;
    }

    _chart(id, type, data, extraOptions = {}) {
        const el = document.getElementById(id);
        if (!el) return;
        if (this.charts[id]) {
            this.charts[id].destroy();
        }
        this.charts[id] = new Chart(el, {
            type,
            data,
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {legend: {labels: {color: "#475569"}}},
                ...extraOptions,
            },
        });
    }

    destroyCharts() {
        Object.values(this.charts).forEach((c) => c.destroy());
        this.charts = {};
    }

    tagClass(tag = "") {
        const t = tag.toLowerCase();
        if (t.includes("equipamento isolado")) return "nd-tag-equip-isolado";
        if (t.includes("falha massiva")) return "nd-tag-falha-massiva";
        if (t.includes("porta agrega")) return "nd-tag-indisp";
        if (t.includes("sinergia")) return "nd-tag-sinergia";
        if (t.includes("manutenção programada") || t.includes("manutencao programada"))
            return "nd-tag-sinergia";
        if (t.includes("intermitente")) return "nd-tag-oscilacao";
        if (t.includes("sistemas")) return "nd-tag-sistemas-ti";
        if (t.includes("indispon")) return "nd-tag-indisp";
        if (t.includes("lat")) return "nd-tag-latencia";
        if (t.includes("descarte")) return "nd-tag-descarte";
        if (t.includes("oscil")) return "nd-tag-oscilacao";
        return "nd-tag-outros";
    }

    formatNum(n) {
        if (n !== null && n !== undefined) {
            return n.toLocaleString("pt-BR");
        }
        return "—";
    }
}

registry
    .category("actions")
    .add("network_helpdesk_dashboard", NetworkHelpdeskDashboard);
