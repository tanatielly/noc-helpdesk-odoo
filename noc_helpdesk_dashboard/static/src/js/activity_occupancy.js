/** @odoo-module **/

import {Component, onMounted, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class NOCActivityOccupancyReport extends Component {
    static template = "noc_helpdesk_dashboard.OcupacaoReport";

    setup() {
        this.rpc = useService("rpc");

        const now = new Date();
        this.state = useState({
            loading: true,
            mode: "mensal",
            mes: now.getMonth() + 1,
            ano: now.getFullYear(),
            rows: [],
            anualRows: [],
            error: null,
        });

        this.years = [];
        for (let y = now.getFullYear() + 1; y >= now.getFullYear() - 2; y--) {
            this.years.push(y);
        }

        this.months = [
            {value: 1, label: "Janeiro", short: "JAN"},
            {value: 2, label: "Fevereiro", short: "FEV"},
            {value: 3, label: "Março", short: "MAR"},
            {value: 4, label: "Abril", short: "ABR"},
            {value: 5, label: "Maio", short: "MAI"},
            {value: 6, label: "Junho", short: "JUN"},
            {value: 7, label: "Julho", short: "JUL"},
            {value: 8, label: "Agosto", short: "AGO"},
            {value: 9, label: "Setembro", short: "SET"},
            {value: 10, label: "Outubro", short: "OUT"},
            {value: 11, label: "Novembro", short: "NOV"},
            {value: 12, label: "Dezembro", short: "DEZ"},
        ];

        onMounted(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const result = await this.rpc(
                "/network_helpdesk_dashboard/ocupacao_report",
                {mes: this.state.mes, ano: this.state.ano}
            );
            if (result && result.error) {
                this.state.error = result.error;
                this.state.rows = [];
            } else {
                this.state.rows = (result && result.rows) || [];
            }
        } catch (e) {
            this.state.error = e.message || "Erro desconhecido.";
            this.state.rows = [];
        }
        this.state.loading = false;
    }

    async loadAnualData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const result = await this.rpc(
                "/network_helpdesk_dashboard/ocupacao_annual",
                {ano: this.state.ano}
            );
            if (result && result.error) {
                this.state.error = result.error;
                this.state.anualRows = [];
            } else {
                this.state.anualRows = (result && result.rows) || [];
            }
        } catch (e) {
            this.state.error = e.message || "Erro desconhecido.";
            this.state.anualRows = [];
        }
        this.state.loading = false;
    }

    setMode(mode) {
        this.state.mode = mode;
        if (mode === "anual") this.loadAnualData();
        else this.loadData();
    }

    setMes(mes) {
        this.state.mes = Number(mes);
        this.loadData();
    }

    setAno(ano) {
        this.state.ano = Number(ano);
        if (this.state.mode === "anual") this.loadAnualData();
        else this.loadData();
    }

    get mesAnoLabel() {
        return new Date(this.state.ano, this.state.mes - 1, 1).toLocaleDateString(
            "pt-BR",
            {weekday: "long", year: "numeric", month: "long", day: "numeric"}
        );
    }

    get mesAtual() {
        return new Date().getMonth();
    }
}

registry.category("actions").add("noc_activity_occupancy_report", NOCActivityOccupancyReport);
