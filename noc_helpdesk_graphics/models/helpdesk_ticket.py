import base64
import csv
import io
import json

from odoo import api, fields, models


class HelpdeskTicketGraphics(models.Model):
    _inherit = "helpdesk.ticket"

    # ── Arquivo de dados ─────────────────────────────────────
    latency_file = fields.Binary(
        string="Arquivo de Latência (CSV/JSON)",
        attachment=True,
    )

    latency_filename = fields.Char(string="Nome do arquivo")

    # JSON enviado para o gráfico
    latency_data_json = fields.Text(
        string="Dados de Latência (JSON)",
        compute="_compute_latency_data_json",
    )

    # ── Thresholds ───────────────────────────────────────────
    latency_threshold_warn = fields.Integer(string="Threshold Alerta (ms)", default=100)

    latency_threshold_crit = fields.Integer(
        string="Threshold Crítico (ms)", default=200
    )

    # ── KPIs ─────────────────────────────────────────────────
    # store=False é intencional: estes campos dependem dos logs do
    # noc_network_monitor (módulo opcional), que não pode ser listado
    # no @api.depends deste módulo. A invalidação é feita explicitamente
    # por NetworkMonitorLog._invalidate_ticket_latency_graph().
    latency_avg = fields.Float(
        string="Latência Média (ms)", compute="_compute_latency_kpis", store=False
    )

    latency_max = fields.Float(
        string="Latência Máxima (ms)", compute="_compute_latency_kpis", store=False
    )

    latency_min = fields.Float(
        string="Latência Mínima (ms)", compute="_compute_latency_kpis", store=False
    )

    latency_last = fields.Float(
        string="Latência Atual (ms)", compute="_compute_latency_kpis", store=False
    )

    latency_samples = fields.Integer(
        string="Amostras", compute="_compute_latency_kpis", store=False
    )

    # ── Parser principal ─────────────────────────────────────
    def _parse_latency_file(self):
        """Retorna lista [{'timestamp': str, 'latency_ms': float}]"""
        self.ensure_one()

        if not self.latency_file:
            return []

        # Proteção contra base64 inválido
        try:
            raw = base64.b64decode(self.latency_file)
        except Exception:
            return []

        filename = (self.latency_filename or "").lower()

        try:
            if filename.endswith(".json"):
                return self._parse_json(raw)
            return self._parse_csv(raw)
        except Exception:
            return []

    # ── CSV ──────────────────────────────────────────────────
    def _parse_csv(self, raw):
        text = raw.decode("utf-8-sig", errors="replace")

        reader = csv.DictReader(io.StringIO(text), skipinitialspace=True)

        fieldnames = reader.fieldnames or []

        ts_col = next(
            (
                f
                for f in fieldnames
                if any(k in f.lower() for k in ["time", "date", "hora", "stamp"])
            ),
            None,
        )

        ms_col = next(
            (
                f
                for f in fieldnames
                if any(k in f.lower() for k in ["lat", "ms", "ping", "delay", "rtt"])
            ),
            None,
        )

        if not ts_col or not ms_col:
            return []

        result = []

        for row in reader:
            try:
                result.append(
                    {"timestamp": row[ts_col].strip(), "latency_ms": float(row[ms_col])}
                )
            except Exception:
                continue

        return result

    # ── JSON ─────────────────────────────────────────────────
    def _parse_json(self, raw):
        try:
            obj = json.loads(raw.decode("utf-8"))
        except Exception:
            return []

        arr = obj if isinstance(obj, list) else obj.get("data", obj.get("records", []))

        result = []

        for r in arr:
            ts_key = next(
                (
                    k
                    for k in r
                    if any(x in k.lower() for x in ["time", "date", "hora", "stamp"])
                ),
                None,
            )

            ms_key = next(
                (
                    k
                    for k in r
                    if any(
                        x in k.lower() for x in ["lat", "ms", "ping", "delay", "rtt"]
                    )
                ),
                None,
            )

            if ts_key and ms_key:
                try:
                    result.append(
                        {"timestamp": str(r[ts_key]), "latency_ms": float(r[ms_key])}
                    )
                except Exception:
                    continue

        return result

    # ── Fonte de dados ────────────────────────────────────────
    latency_source = fields.Selection(
        selection=[
            ("file", "Arquivo (CSV/JSON)"),
            ("monitor", "Monitor de Rede"),
        ],
        string="Fonte dos Dados de Latência",
        compute="_compute_latency_source",
        store=False,
    )

    @api.depends("latency_file")
    def _compute_latency_source(self):
        for rec in self:
            if rec.latency_file:
                rec.latency_source = "file"
            elif rec.monitor_log_ids:
                rec.latency_source = "monitor"
            else:
                rec.latency_source = "file"

    # ── Dados dos logs do monitor ─────────────────────────────
    def _get_monitor_data(self):
        """Retorna lista [{'timestamp': str, 'latency_ms': float}]
        a partir dos network.monitor.log vinculados ao chamado,
        ordenados por collected_at crescente.
        Retorna lista vazia quando noc_network_monitor nao esta instalado."""
        self.ensure_one()
        if "network.monitor.log" not in self.env:
            return []
        logs = self.env["network.monitor.log"].search(
            [("ticket_id", "=", self.id)],
            order="collected_at asc",
        )
        result = []
        for log in logs:
            if not log.collected_at:
                continue
            result.append(
                {
                    "timestamp": fields.Datetime.to_string(log.collected_at),
                    "latency_ms": log.round_trip_avg_ms,
                }
            )
        return result

    # ── Dados combinados ─────────────────────────────────────
    def _get_latency_data(self):
        """Retorna os dados de latência priorizando arquivo manual;
        cai para os logs do monitor quando nao ha arquivo."""
        self.ensure_one()
        data = self._parse_latency_file()
        if data:
            return data
        return self._get_monitor_data()

    # ── JSON para o frontend ─────────────────────────────────────
    @api.depends(
        "latency_file",
        "latency_filename",
        "latency_threshold_warn",
        "latency_threshold_crit",
    )
    def _compute_latency_data_json(self):
        for rec in self:
            data = rec._get_latency_data()

            if not data:
                rec.latency_data_json = "{}"
                continue

            labels = []
            values = []

            for d in data:
                labels.append(d["timestamp"])
                values.append(d["latency_ms"])

            payload = {
                "labels": labels,
                "values": values,
                "threshold_warn": rec.latency_threshold_warn,
                "threshold_crit": rec.latency_threshold_crit,
            }

            rec.latency_data_json = json.dumps(payload)

    # ── KPIs ─────────────────────────────────────────────────
    @api.depends(
        "latency_file",
        "latency_filename",
    )
    def _compute_latency_kpis(self):
        for rec in self:
            data = rec._get_latency_data()

            if not data:
                rec.latency_avg = 0
                rec.latency_max = 0
                rec.latency_min = 0
                rec.latency_last = 0
                rec.latency_samples = 0
                continue

            vals = [d["latency_ms"] for d in data]

            rec.latency_avg = sum(vals) / len(vals)
            rec.latency_max = max(vals)
            rec.latency_min = min(vals)
            rec.latency_last = vals[-1]
            rec.latency_samples = len(vals)
