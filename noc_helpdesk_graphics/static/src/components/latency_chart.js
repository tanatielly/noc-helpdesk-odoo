/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillUnmount,
    onWillUpdateProps,
    useRef,
    useState,
} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {loadJS} from "@web/core/assets";
import {useService} from "@web/core/utils/hooks";

const CHARTJS_URL = "/web/static/lib/Chart/Chart.js";

export class LatencyChart extends Component {
    static template = "noc_helpdesk_graphics.LatencyChart";

    static props = {
        // Props padrão de field widget do Odoo
        value: {type: String, optional: true},
        update: {type: Function, optional: true},
        record: {type: Object, optional: true},
        name: {type: String, optional: true},
        readonly: {type: Boolean, optional: true},
        id: {type: String, optional: true},
        decorations: {type: Object, optional: true},
        type: {type: String, optional: true},
        setDirty: {type: Function, optional: true},

        // Props customizadas
        threshold_warn: {type: Number, optional: true},
        threshold_crit: {type: Number, optional: true},
    };

    static defaultProps = {
        latencyDataJson: "{}",
        thresholdWarn: 100,
        thresholdCrit: 200,
    };

    windows = [
        {key: "all", label: "Tudo"},
        {key: 60, label: "1h"},
        {key: 360, label: "6h"},
        {key: 720, label: "12h"},
    ];

    setup() {
        this.orm = useService("orm");
        this.chartRef = useRef("chartCanvas");
        this.chartInst = null;
        this.allData = [];

        this.thresholdWarn = this.props.thresholdWarn;
        this.thresholdCrit = this.props.thresholdCrit;

        this.state = useState({
            hasData: false,
            window: "all",
            rangeLabel: "",
            kpis: {
                last: 0,
                avg: 0,
                max: 0,
                min: 0,
                samples: 0,
                lastTime: "",
                maxTime: "",
                minTime: "",
            },
        });

        onMounted(async () => {
            if (!window.Chart) {
                await loadJS(CHARTJS_URL);
            }

            await this._ingestWithFallback(this.props, this.props.value);
        });

        onWillUpdateProps(async (nextProps) => {
            const currentPayload = this.props.value;
            const nextPayload = nextProps.value;

            if (nextPayload !== currentPayload) {
                if (!window.Chart) {
                    await loadJS(CHARTJS_URL);
                }

                // Em alguns saves, o campo computado chega vazio por um ciclo.
                // Se ainda há arquivo anexado, preserva o gráfico atual.
                const hasAttachedFile =
                    Boolean(nextProps?.record?.data?.latency_file) ||
                    Boolean(nextProps?.record?.data?.latency_filename);
                const hasMonitorLogs =
                    nextProps?.record?.data?.latency_source === "monitor" ||
                    Boolean(nextProps?.record?.data?.monitor_log_count);
                const isTransientEmptyPayload =
                    (!nextPayload || nextPayload === "{}") &&
                    (hasAttachedFile || hasMonitorLogs);

                if (isTransientEmptyPayload && this.allData.length) {
                    this._renderChart(this.thresholdWarn, this.thresholdCrit);
                    return;
                }

                await this._ingestWithFallback(nextProps, nextPayload);
            } else if (
                nextProps.thresholdWarn !== this.props.thresholdWarn ||
                nextProps.thresholdCrit !== this.props.thresholdCrit
            ) {
                this.thresholdWarn = nextProps.thresholdWarn;
                this.thresholdCrit = nextProps.thresholdCrit;

                this._renderChart(this.thresholdWarn, this.thresholdCrit);
            }
        });
        onWillUnmount(() => {
            if (this.chartInst) {
                this.chartInst.destroy();
                this.chartInst = null;
            }
        });
    }

    // ─────────────────────────────────────────────
    // Ingestão de dados
    // ─────────────────────────────────────────────

    async _ingestWithFallback(props, payloadCandidate) {
        const payloadFromRecord = props?.record?.data?.[props?.name];

        if (this._isUsablePayload(payloadCandidate)) {
            this._ingest(payloadCandidate);
            return;
        }
        if (this._isUsablePayload(payloadFromRecord)) {
            this._ingest(payloadFromRecord);
            return;
        }

        // Busca no servidor se há arquivo manual OU se o monitor de rede está ativo
        const hasAttachedFile =
            Boolean(props?.record?.data?.latency_file) ||
            Boolean(props?.record?.data?.latency_filename);
        const hasMonitorLogs =
            props?.record?.data?.latency_source === "monitor" ||
            Boolean(props?.record?.data?.monitor_log_count);

        if (hasAttachedFile || hasMonitorLogs) {
            const payloadFromServer = await this._readPayloadFromServer(props);
            if (this._isUsablePayload(payloadFromServer)) {
                this._ingest(payloadFromServer);
                return;
            }
        }

        this._ingest(payloadCandidate || payloadFromRecord || "{}");
    }

    async _readPayloadFromServer(props) {
        const resId = props?.record?.resId || props?.record?.data?.id;
        if (!resId) {
            return null;
        }

        try {
            const [row] = await this.orm.read(
                "helpdesk.ticket",
                [resId],
                [
                    "latency_data_json",
                    "latency_threshold_warn",
                    "latency_threshold_crit",
                ]
            );

            if (row?.latency_threshold_warn !== undefined) {
                this.thresholdWarn = row.latency_threshold_warn;
            }
            if (row?.latency_threshold_crit !== undefined) {
                this.thresholdCrit = row.latency_threshold_crit;
            }

            return row?.latency_data_json || null;
        } catch {
            return null;
        }
    }

    _isUsablePayload(value) {
        if (!value || typeof value !== "string" || value === "{}") {
            return false;
        }
        try {
            const parsed = JSON.parse(value);
            return Array.isArray(parsed?.labels) && parsed.labels.length > 0;
        } catch {
            return false;
        }
    }

    _ingest(jsonStr) {
        try {
            const payload = JSON.parse(jsonStr || "{}");

            const labels = payload.labels || [];
            const values = payload.values || [];

            this.thresholdWarn = payload.threshold_warn ?? this.props.thresholdWarn;
            this.thresholdCrit = payload.threshold_crit ?? this.props.thresholdCrit;

            this.allData = labels
                .map((label, i) => ({
                    ts: this._parseTimestamp(label),
                    ms: parseFloat(values[i]),
                }))
                .filter(
                    (r) =>
                        !isNaN(r.ms) && r.ts instanceof Date && !isNaN(r.ts.getTime())
                )
                .sort((a, b) => a.ts - b.ts);
        } catch {
            this.allData = [];
        }

        this.state.hasData = this.allData.length > 0;

        if (this.state.hasData) {
            this._renderChart(this.thresholdWarn, this.thresholdCrit);
        } else if (this.chartInst) {
            this.chartInst.destroy();
            this.chartInst = null;
        }
    }

    // ─────────────────────────────────────────────
    // Filtro de janela de tempo
    // ─────────────────────────────────────────────

    _getVisible() {
        if (this.state.window === "all" || !this.allData.length) {
            return this.allData;
        }

        const last = this.allData[this.allData.length - 1].ts;
        const cutoff = new Date(last.getTime() - this.state.window * 60000);
        if (isNaN(cutoff.getTime())) {
            return this.allData;
        }

        const filtered = this.allData.filter((d) => d.ts >= cutoff);
        return filtered.length ? filtered : this.allData;
    }

    setWindow(key) {
        this.state.window = key;
        if (this.chartInst) {
            this.chartInst.destroy();
            this.chartInst = null;
        }

        this._renderChart(this.thresholdWarn, this.thresholdCrit);
    }

    // ─────────────────────────────────────────────
    // KPIs
    // ─────────────────────────────────────────────

    _updateKPIs(data) {
        if (!data.length) return;

        const vals = data.map((d) => d.ms);

        const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
        const max = Math.max(...vals);
        const min = Math.min(...vals);

        const last = data[data.length - 1];

        const maxD = data.find((d) => d.ms === max);
        const minD = data.find((d) => d.ms === min);

        const fmtT = (t) =>
            t
                ? t.toLocaleTimeString("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                  })
                : "—";

        const fmtDT = (t) =>
            t
                ? t.toLocaleString("pt-BR", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                  })
                : "—";

        Object.assign(this.state.kpis, {
            last: last.ms,
            avg,
            max,
            min,
            samples: data.length,
            lastTime: fmtT(last.ts),
            maxTime: fmtT(maxD?.ts),
            minTime: fmtT(minD?.ts),
        });

        this.state.rangeLabel = `${fmtDT(data[0].ts)} → ${fmtDT(
            data[data.length - 1].ts
        )}`;
    }

    // ─────────────────────────────────────────────
    // Render do gráfico
    // ─────────────────────────────────────────────

    _renderChart(thW, thC) {
        if (!window.Chart) return;

        let visible = this._getVisible();

        if (!visible.length) {
            // Destruir gráfico anterior quando não há dados
            if (this.chartInst) {
                this.chartInst.destroy();
                this.chartInst = null;
            }
            // Limpar KPIs
            Object.assign(this.state.kpis, {
                last: 0,
                avg: 0,
                max: 0,
                min: 0,
                samples: 0,
                lastTime: "",
                maxTime: "",
                minTime: "",
            });
            this.state.rangeLabel = "";
            return;
        }

        // Downsampling para evitar travar o browser
        const MAX_POINTS = 1500;

        if (visible.length > MAX_POINTS) {
            const step = Math.ceil(visible.length / MAX_POINTS);

            visible = visible.filter((_, i) => i % step === 0);
        }

        this._updateKPIs(visible);

        const labels = visible.map((d) =>
            d.ts.toLocaleTimeString("pt-BR", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            })
        );

        const values = visible.map((d) => d.ms);

        const n = visible.length;

        const pointColors = values.map((v) =>
            v >= thC ? "#ef4444" : v >= thW ? "#f59e0b" : "#6366f1"
        );

        const datasets = [
            {
                label: "Latência (ms)",
                data: values,
                borderColor: "#6366f1",
                borderWidth: 2,
                backgroundColor: "rgba(99,102,241,0.08)",
                fill: true,
                tension: 0.35,
                pointRadius: n > 200 ? 0 : 3,
                pointHoverRadius: 5,
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                order: 1,
            },

            {
                label: `Alerta (${thW}ms)`,
                data: Array(n).fill(thW),
                borderColor: "#f59e0b",
                borderWidth: 1.5,
                borderDash: [5, 4],
                pointRadius: 0,
                fill: false,
                tension: 0,
                order: 0,
            },

            {
                label: `Crítico (${thC}ms)`,
                data: Array(n).fill(thC),
                borderColor: "#ef4444",
                borderWidth: 1.5,
                borderDash: [5, 4],
                pointRadius: 0,
                fill: false,
                tension: 0,
                order: 0,
            },
        ];

        const canvas = this.chartRef.el;

        if (!canvas) return;

        if (this.chartInst) {
            this.chartInst.data.labels = labels;
            this.chartInst.data.datasets = datasets;
            this.chartInst.update("active");
            return;
        }

        const ctx = canvas.getContext("2d");

        this.chartInst = new window.Chart(ctx, {
            type: "line",

            data: {labels, datasets},

            options: {
                responsive: true,
                maintainAspectRatio: false,

                animation: {duration: 400},

                interaction: {
                    mode: "index",
                    intersect: false,
                },

                plugins: {
                    legend: {display: false},

                    tooltip: {
                        backgroundColor: "#1a1a2e",
                        titleColor: "#fff",
                        bodyColor: "rgba(255,255,255,0.75)",

                        callbacks: {
                            label: (ctx) => {
                                if (ctx.datasetIndex !== 0) return null;

                                const v = ctx.parsed.y;

                                const status =
                                    v >= thC
                                        ? "🔴 CRÍTICO"
                                        : v >= thW
                                        ? "🟡 ALERTA"
                                        : "🟢 OK";

                                return ` ${v.toFixed(1)} ms ${status}`;
                            },
                        },
                    },
                },

                scales: {
                    x: {
                        grid: {color: "rgba(0,0,0,0.05)"},
                        ticks: {color: "#8892a4", maxTicksLimit: 10},
                    },

                    y: {
                        beginAtZero: true,
                        grid: {color: "rgba(0,0,0,0.05)"},
                        ticks: {
                            color: "#8892a4",
                            callback: (v) => v + " ms",
                        },
                    },
                },
            },
        });
    }

    // ─────────────────────────────────────────────
    // Helpers
    // ─────────────────────────────────────────────

    _parseTimestamp(value) {
        if (value === null || value === undefined) {
            return new Date(NaN);
        }

        if (typeof value === "number") {
            // Aceita timestamps em segundos ou milissegundos.
            return new Date(value < 1e12 ? value * 1000 : value);
        }

        const raw = String(value).trim();
        if (!raw) return new Date(NaN);

        // Formato comum de CSV: "YYYY-MM-DD HH:mm:ss"
        const normalizedIso = raw.includes("T") ? raw : raw.replace(" ", "T");
        const isoDate = new Date(normalizedIso);
        if (!isNaN(isoDate.getTime())) {
            return isoDate;
        }

        // Fallback para formato brasileiro "DD/MM/YYYY HH:mm:ss"
        const brMatch = raw.match(
            /^(\d{2})\/(\d{2})\/(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/
        );
        if (!brMatch) {
            return new Date(NaN);
        }

        const [, dd, mm, yyyy, hh = "00", min = "00", ss = "00"] = brMatch;
        return new Date(
            Number(yyyy),
            Number(mm) - 1,
            Number(dd),
            Number(hh),
            Number(min),
            Number(ss)
        );
    }

    fmt(v) {
        return Math.round(v);
    }

    kpiStatus(v) {
        const thW = this.thresholdWarn;
        const thC = this.thresholdCrit;

        if (v >= thC) return "bad";
        if (v >= thW) return "warn";

        return "good";
    }
}

// Registrar widget para <field widget="latency_chart"/>

registry.category("fields").add("latency_chart", LatencyChart);
