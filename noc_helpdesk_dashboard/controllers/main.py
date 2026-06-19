import logging
from collections import defaultdict
from datetime import datetime, timedelta

import pytz

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class NetworkHelpdeskDashboard(http.Controller):
    @http.route("/network_helpdesk_dashboard/data", type="json", auth="user")
    def get_dashboard_data(
        self,
        period="30d",
        tags=None,
        provider_id=None,
        health=None,
        stage_ids=None,
        **kwargs,
    ):
        try:
            return self._compute_data(
                period,
                tags=tags or [],
                provider_id=provider_id,
                health=health or [],
                stage_ids=stage_ids or [],
            )
        except Exception as e:
            _logger.exception("Erro no dashboard: %s", e)
            return {"error": str(e)}

    @http.route(
        "/network_helpdesk_dashboard/ticket_list_action", type="json", auth="user"
    )
    def ticket_list_action(self, filter_type="all", period="30d", **kwargs):
        date_from = self._date_from(period).strftime("%Y-%m-%d 00:00:00")
        domain = [["create_date", ">=", date_from]]
        name = "Todos os Chamados"
        if filter_type == "open":
            domain.append(["stage_id.fold", "=", False])
            name = "Chamados em Aberto"
        elif filter_type == "closed":
            domain.append(["stage_id.fold", "=", True])
            name = "Chamados Resolvidos"
        context = {
            "group_by": ["tag_id"],
            "search_disable_custom_filters": True,
            "dashboard_no_default_filters": True,
        }
        if filter_type in ("open", "closed"):
            context["helpdesk_active_filter"] = filter_type
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "helpdesk.ticket",
            "views": [[False, "list"], [False, "form"]],
            "domain": domain,
            "context": context,
            "target": "current",
        }

    @http.route("/network_helpdesk_dashboard/plantao_status", type="json", auth="user")
    def get_plantao_status(self, **kwargs):
        try:
            return self._compute_plantao_status()
        except Exception as e:
            _logger.exception("Erro plantao_status: %s", e)
            return {"error": str(e)}

    @http.route("/network_helpdesk_dashboard/circuit_tickets", type="json", auth="user")
    def get_circuit_tickets(self, circuit_id, period="30d", **kwargs):
        try:
            date_from_str = self._date_from(period).strftime("%Y-%m-%d 00:00:00")
            Ticket = request.env["helpdesk.ticket"]
            tickets = Ticket.search(
                [
                    ("create_date", ">=", date_from_str),
                    ("circuit_id", "=", int(circuit_id)),
                ]
            ).sorted("create_date", reverse=True)

            now_utc = datetime.utcnow()
            result = []
            for t in tickets:
                create_local = self._to_local(t.create_date)
                delta = now_utc - t.create_date.replace(tzinfo=None)
                total_secs = max(0, int(delta.total_seconds()))
                hrs = total_secs // 3600
                mins = (total_secs - hrs * 3600) // 60
                result.append(
                    {
                        "id": t.id,
                        "name": t.name or "(sem título)",
                        "tag": t.tag_id.name if t.tag_id else "—",
                        "stage": t.stage_id.name if t.stage_id else "—",
                        "create_date": (
                            create_local.strftime("%d/%m/%Y %H:%M")
                            if create_local
                            else "—"
                        ),
                        "tempo_aberto": f"{hrs}h {mins:02d}m",
                        "user": t.user_id.name if t.user_id else "—",
                        "external_ticket_number": t.external_ticket_number or "—",
                        "is_open": not t.stage_id.fold,
                    }
                )
            return {"tickets": result}
        except Exception as e:
            _logger.exception("Erro circuit_tickets: %s", e)
            return {"error": str(e)}

    # ── Relatório Mensal ──────────────────────────────────────────────

    @http.route(
        "/network_helpdesk_dashboard/relatorio_mensal", type="json", auth="user"
    )
    def get_relatorio_mensal(self, month=None, year=None, **kwargs):
        try:
            return self._compute_relatorio_mensal(month, year)
        except Exception as e:
            _logger.exception("Erro relatorio_mensal: %s", e)
            return {"error": str(e)}

    @http.route(
        "/network_helpdesk_dashboard/relatorio_mensal/print",
        type="http",
        auth="user",
    )
    def print_relatorio_mensal(self, month=None, year=None, **kwargs):
        report_data = self._compute_relatorio_mensal(month, year)
        report = request.env.ref(
            "noc_helpdesk_dashboard.action_report_relatorio_mensal"
        )
        pdf_content, _ = report._render_qweb_pdf(
            report.report_name, [], data={"report_data": report_data}
        )
        headers = [
            ("Content-Type", "application/pdf"),
            ("Content-Length", len(pdf_content)),
        ]
        return request.make_response(pdf_content, headers=headers)

    @http.route(
        "/network_helpdesk_dashboard/relatorio_mensal/export_pptx",
        type="http",
        auth="user",
    )
    def export_relatorio_mensal_pptx(self, month=None, year=None, **kwargs):
        from .relatorio_mensal_pptx import build_pptx

        report_data = self._compute_relatorio_mensal(month, year)
        buf = build_pptx(report_data)
        content = buf.getvalue()
        headers = [
            (
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ),
            ("Content-Disposition", "attachment; filename=relatorio_mensal.pptx"),
            ("Content-Length", len(content)),
        ]
        return request.make_response(content, headers=headers)

    @http.route(
        "/network_helpdesk_dashboard/relatorio_mensal/config",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def save_relatorio_mensal_config(self, month, year, **kwargs):
        try:
            Config = request.env["noc.monthly.report"].sudo()
            record = Config.search(
                [("month", "=", month), ("year", "=", year)], limit=1
            )
            writable_fields = [
                "meta_falha_massiva",
                "meta_eventos_amarelos",
                "meta_disponibilidade_backbone",
                "meta_descartes_pacotes",
                "meta_latencia",
                "total_backbone_circuits",
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
            ]
            vals = {f: kwargs[f] for f in writable_fields if f in kwargs}
            if record:
                record.write(vals)
            else:
                vals.update({"month": month, "year": year})
                Config.create(vals)
            return {"ok": True}
        except Exception as e:
            _logger.exception("Erro save_relatorio_mensal_config: %s", e)
            return {"error": str(e)}

    def _compute_relatorio_mensal(self, month, year):
        from calendar import monthrange

        now = datetime.utcnow()
        month, year = int(month or now.month), int(year or now.year)
        Config = request.env["noc.monthly.report"].sudo()
        config = Config.search([("month", "=", month), ("year", "=", year)], limit=1)
        _, last_day = monthrange(year, month)
        date_start = datetime(year, month, 1, 0, 0, 0)
        date_end = datetime(year, month, last_day, 23, 59, 59)
        Ticket = request.env["helpdesk.ticket"].sudo()
        Circuit = request.env["network.circuit"].sudo()
        detected = self._detect_fields(Ticket)
        kpi_flags = {
            "falha_massiva": "is_falha_massiva",
            "eventos_amarelos": "is_unavailable",
            "descartes_pacotes": "is_discarded_packet",
            "latencia": "is_high_latency",
        }

        def _month_domain(extra_domain):
            return [
                ("create_date", ">=", date_start.strftime("%Y-%m-%d %H:%M:%S")),
                ("create_date", "<=", date_end.strftime("%Y-%m-%d %H:%M:%S")),
            ] + extra_domain

        kpis = {
            key: Ticket.search_count(_month_domain([(field, "=", True)]))
            for key, field in kpi_flags.items()
        }
        bb_type_ids = config.backbone_circuit_type_ids.ids if config else []
        kpis["disponibilidade"] = self._backbone_disponibilidade(
            year,
            month,
            last_day,
            Ticket,
            Circuit,
            detected,
            bb_type_ids,
            config.total_backbone_circuits if config else 0,
        )
        historico, historico_labels = self._historico_mensal(
            month, year, kpi_flags, Ticket, Circuit, Config, detected, bb_type_ids
        )
        top_links = self._top_links_mensal(kpi_flags, Ticket, detected, _month_domain)
        cfg = self._build_config_dict(config)
        sugestoes = self._gerar_sugestoes(month, historico, top_links)
        auto_fields = [
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
        ]
        for f in auto_fields:
            if not cfg.get(f) and sugestoes.get(f):
                cfg[f] = sugestoes[f]
        return {
            "month": month,
            "year": year,
            "config": cfg,
            "kpis": kpis,
            "historico_labels": historico_labels,
            "historico": historico,
            "top_links": top_links,
            "sugestoes": sugestoes,
        }

    def _backbone_disponibilidade(
        self,
        year,
        month,
        last_day,
        Ticket,
        Circuit,
        detected,
        bb_type_ids,
        override_total=0,
    ):
        if override_total > 0:
            total = override_total
        else:
            c_domain = [("active", "=", True)]
            if bb_type_ids:
                c_domain.append(("circuit_type_id", "in", bb_type_ids))
            total = Circuit.search_count(c_domain)
        if not total:
            return None
        ds = datetime(year, month, 1)
        de = datetime(year, month, last_day, 23, 59, 59)
        ticket_domain = [
            ("create_date", ">=", ds.strftime("%Y-%m-%d %H:%M:%S")),
            ("create_date", "<=", de.strftime("%Y-%m-%d %H:%M:%S")),
            ("is_unavailable", "=", True),
        ]
        if bb_type_ids:
            ticket_domain.append(("circuit_id.circuit_type_id", "in", bb_type_ids))
        tickets = Ticket.search(ticket_domain)
        downtime = sum(
            self._hours_between(self._end_date(t, detected), t.create_date) * 60
            for t in tickets
            if t.create_date
        )
        total_min = total * last_day * 24 * 60
        return round(max(0.0, (total_min - downtime) / total_min * 100), 3)

    def _historico_mensal(
        self, month, year, kpi_flags, Ticket, Circuit, Config, detected, bb_type_ids
    ):
        from calendar import monthrange

        _PT_MONTHS = [
            "",
            "JAN",
            "FEV",
            "MAR",
            "ABR",
            "MAI",
            "JUN",
            "JUL",
            "AGO",
            "SET",
            "OUT",
            "NOV",
            "DEZ",
        ]

        # Build ordered list of (year, month) for the 13 slots
        months_seq = []
        for i in range(12, -1, -1):
            m, y = month - i, year
            while m <= 0:
                m += 12
                y -= 1
            months_seq.append((y, m))

        labels = [f"{_PT_MONTHS[m]}/{str(y)[2:]}" for y, m in months_seq]
        historico = {k: [0] * 13 for k in kpi_flags.keys()}
        historico["disponibilidade"] = [None] * 13
        ym_index = {ym: idx for idx, ym in enumerate(months_seq)}

        # Date range covering all 13 months
        y_start, m_start = months_seq[0]
        y_end, m_end = months_seq[-1]
        _, ld_end = monthrange(y_end, m_end)
        from_str = datetime(y_start, m_start, 1).strftime("%Y-%m-%d %H:%M:%S")
        to_str = datetime(y_end, m_end, ld_end, 23, 59, 59).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # 1 query covering all KPI flags instead of 52 search_count calls
        tickets = Ticket.search_read(
            domain=[
                ("create_date", ">=", from_str),
                ("create_date", "<=", to_str),
            ],
            fields=["create_date"] + list(kpi_flags.values()),
        )
        for t in tickets:
            cd = t["create_date"]
            if not cd:
                continue
            y, m = (
                (int(cd[:4]), int(cd[5:7]))
                if isinstance(cd, str)
                else (cd.year, cd.month)
            )
            idx = ym_index.get((y, m))
            if idx is None:
                continue
            for key, field in kpi_flags.items():
                if t.get(field):
                    historico[key][idx] += 1

        # Disponibilidade requires per-month downtime calculation
        for idx, (y, m) in enumerate(months_seq):
            _, ld = monthrange(y, m)
            h_cfg = Config.search([("month", "=", m), ("year", "=", y)], limit=1)
            h_types = h_cfg.backbone_circuit_type_ids.ids if h_cfg else bb_type_ids
            h_override = h_cfg.total_backbone_circuits if h_cfg else 0
            historico["disponibilidade"][idx] = self._backbone_disponibilidade(
                y, m, ld, Ticket, Circuit, detected, h_types, h_override
            )

        return historico, labels

    def _top_links_mensal(self, kpi_flags, Ticket, detected, month_domain_fn, limit=5):
        def _one(field):
            tickets = Ticket.search(month_domain_fn([(field, "=", True)]))
            counts = {}
            for t in tickets:
                key = t.circuit_id.id if t.circuit_id else 0
                if key not in counts:
                    name = (
                        t.circuit_id.link_designation or t.circuit_id.name
                        if t.circuit_id
                        else t.name or "—"
                    )
                    provider = (
                        t.circuit_id.provider_id.name
                        if t.circuit_id and t.circuit_id.provider_id
                        else (t.provider_id.name if t.provider_id else "NOSSO")
                    )
                    counts[key] = {
                        "designacao": name,
                        "operadora": provider,
                        "qtde": 0,
                        "duracao_min": 0.0,
                    }
                counts[key]["qtde"] += 1
                counts[key]["duracao_min"] += (
                    self._hours_between(self._end_date(t, detected), t.create_date) * 60
                )
            total = sum(v["qtde"] for v in counts.values()) or 1
            result = sorted(counts.values(), key=lambda x: x["qtde"], reverse=True)[
                :limit
            ]
            for r in result:
                r["pct_total"] = round(r["qtde"] / total * 100, 2)
                mins = int(r["duracao_min"])
                h, m_rem = divmod(mins, 60)
                r["duracao_fmt"] = f"{h:02d}:{m_rem:02d}:00 hs"
                del r["duracao_min"]
            return result

        return {key: _one(field) for key, field in kpi_flags.items()}

    def _build_config_dict(self, config):
        def _field(name, default):
            return getattr(config, name) if config else default

        def _text(name):
            return getattr(config, name) or "" if config else ""

        return {
            "meta_falha_massiva": _field("meta_falha_massiva", 0),
            "meta_eventos_amarelos": _field("meta_eventos_amarelos", 23),
            "meta_disponibilidade_backbone": _field(
                "meta_disponibilidade_backbone", 99.90
            ),
            "meta_descartes_pacotes": _field("meta_descartes_pacotes", 1),
            "meta_latencia": _field("meta_latencia", 4),
            "analise_falha_massiva": _text("analise_falha_massiva"),
            "acao_falha_massiva": _text("acao_falha_massiva"),
            "analise_eventos_amarelos": _text("analise_eventos_amarelos"),
            "acao_eventos_amarelos": _text("acao_eventos_amarelos"),
            "analise_disponibilidade": _text("analise_disponibilidade"),
            "acao_disponibilidade": _text("acao_disponibilidade"),
            "analise_descartes": _text("analise_descartes"),
            "acao_descartes": _text("acao_descartes"),
            "analise_latencia": _text("analise_latencia"),
            "acao_latencia": _text("acao_latencia"),
            "total_backbone_circuits": _field("total_backbone_circuits", 0),
        }

    def _gerar_sugestoes(self, month, historico, top_links):
        _PT_MONTHS_FULL = [
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
        ]
        mes_nome = _PT_MONTHS_FULL[month]

        def _prev(key):
            h = historico.get(key, [])
            return h[-2] if len(h) >= 2 else None

        def _curr(key):
            h = historico.get(key, [])
            return h[-1] if h else None

        n_fm = _curr("falha_massiva") or 0
        tend_fm = self._tendencia_texto(n_fm, _prev("falha_massiva"))
        analise_fm, acao_fm = self._sugestao_falha_massiva(
            mes_nome, n_fm, tend_fm, top_links.get("falha_massiva", [])
        )

        n_ea = _curr("eventos_amarelos") or 0
        tend_ea = self._tendencia_texto(n_ea, _prev("eventos_amarelos"))
        analise_ea, acao_ea = self._sugestao_eventos_amarelos(
            mes_nome, tend_ea, top_links.get("eventos_amarelos", [])
        )

        analise_disp, acao_disp = self._sugestao_disponibilidade(
            mes_nome,
            _curr("disponibilidade"),
            _prev("disponibilidade"),
            top_links.get("eventos_amarelos", []),
        )

        n_dp = _curr("descartes_pacotes") or 0
        tend_dp = self._tendencia_texto(n_dp, _prev("descartes_pacotes"))
        analise_dp, acao_dp = self._sugestao_descartes(
            tend_dp, top_links.get("descartes_pacotes", [])
        )

        n_lat = _curr("latencia") or 0
        tend_lat = self._tendencia_texto(n_lat, _prev("latencia"))
        analise_lat, acao_lat = self._sugestao_latencia(
            tend_lat, top_links.get("latencia", [])
        )

        return {
            "analise_falha_massiva": analise_fm,
            "acao_falha_massiva": acao_fm,
            "analise_eventos_amarelos": analise_ea,
            "acao_eventos_amarelos": acao_ea,
            "analise_disponibilidade": analise_disp,
            "acao_disponibilidade": acao_disp,
            "analise_descartes": analise_dp,
            "acao_descartes": acao_dp,
            "analise_latencia": analise_lat,
            "acao_latencia": acao_lat,
        }

    def _tendencia_texto(self, atual, anterior):
        if anterior is None:
            return "resultado sem dados do mês anterior para comparação"
        if atual > anterior:
            return "piora em relação ao mês anterior"
        if atual < anterior:
            return "melhora em relação ao mês anterior"
        return "resultado estável em relação ao mês anterior"

    def _por_operadora(self, links):
        by_op = {}
        for link in links:
            op = link["operadora"]
            by_op[op] = by_op.get(op, 0) + link["qtde"]
        return sorted(by_op.items(), key=lambda x: x[1], reverse=True)

    def _sugestao_falha_massiva(self, mes_nome, n_fm, tend_fm, top_fm):
        analise = f"Tivemos {tend_fm}."
        if n_fm > 0:
            analise += f"\n\nNo mês de {mes_nome}, tivemos {n_fm} falha(s) massiva(s)."
        if n_fm == 0:
            acao = "Sem falhas massivas no período."
        elif top_fm:
            maior = top_fm[0]
            acao = (
                f"No mês de {mes_nome}, tivemos {n_fm} falha(s) massiva(s). "
                f"O circuito {maior['designacao']} ({maior['operadora']})"
                " foi o mais afetado."
            )
        else:
            acao = f"No mês de {mes_nome}, tivemos {n_fm} falha(s) massiva(s)."
        return analise, acao

    def _sugestao_eventos_amarelos(self, mes_nome, tend_ea, top_ea):
        analise = f"Tivemos {tend_ea} referente ao número de eventos."
        if top_ea:
            por_op = self._por_operadora(top_ea)
            nosso_qtd = next((qtd for op, qtd in por_op if op == "NOSSO"), None)
            outros = [(op, qtd) for op, qtd in por_op if op != "NOSSO"]
            if nosso_qtd:
                outros_str = ", ".join(f"{op} {qtd}" for op, qtd in outros[:3])
                analise += (
                    f"\n\nNossos Links foram os maiores ofensores"
                    f" do mês com {nosso_qtd} eventos"
                    + (f", seguidos de {outros_str}." if outros_str else ".")
                )
            elif por_op:
                op1, qtd1 = por_op[0]
                analise += f"\n\n{op1} foi o maior ofensor do mês com {qtd1} eventos."
        if top_ea:
            maior = top_ea[0]
            acao = (
                f"{maior['designacao']} ({maior['operadora']})"
                " foi o maior ofensor este mês "
                f"com {maior['qtde']} evento(s)."
            )
        else:
            acao = "Planos de ação em andamento."
        return analise, acao

    def _sugestao_disponibilidade(self, mes_nome, disp_atual, disp_prev, top_indisp):
        if disp_atual is not None and disp_prev is not None:
            if disp_atual >= disp_prev:
                analise = "Houve melhora em relação ao mês anterior."
            else:
                analise = "Houve piora em relação ao mês anterior."
            diff = round(abs(disp_atual - disp_prev), 3)
            analise += f" Variação de {diff}%."
        elif disp_atual is not None:
            analise = f"Disponibilidade de {disp_atual}% no mês de {mes_nome}."
        else:
            analise = "Configure os circuitos backbone para calcular a disponibilidade."
        if top_indisp:
            por_op_disp = self._por_operadora(top_indisp)
            ops_str = ", ".join(op for op, _ in por_op_disp[:3])
            if ops_str:
                analise += f"\n\nMaiores ofensores do mês: {ops_str}."
        return analise, "Planos de ação em andamento."

    def _sugestao_descartes(self, tend_dp, top_dp):
        analise = f"Tivemos {tend_dp}."
        if top_dp:
            por_op_dp = self._por_operadora(top_dp)
            partes = []
            for op, qtd in por_op_dp[:4]:
                if op == "NOSSO":
                    partes.append(f"{qtd} evento(s) nossos")
                else:
                    partes.append(f"{qtd} da {op}")
            if partes:
                analise += f"\n\nPrincipais alterações: Tivemos {', '.join(partes)}."
        return analise, "Planos de ação em andamento."

    def _sugestao_latencia(self, tend_lat, top_lat):
        analise = f"Houve {tend_lat}."
        if top_lat:
            por_op_lat = self._por_operadora(top_lat)
            nosso_lat = next((qtd for op, qtd in por_op_lat if op == "NOSSO"), None)
            if nosso_lat:
                analise += (
                    f"\n\nPrincipais alterações: Tivemos"
                    f" {nosso_lat} evento(s) dos nossos links."
                )
            elif por_op_lat:
                op1, qtd1 = por_op_lat[0]
                analise += (
                    f"\n\nPrincipais alterações: Tivemos {qtd1} evento(s) da {op1}."
                )
        return analise, "Planos de ação em andamento."

    # ── helpers ───────────────────────────────────────────────────────

    def _user_tz(self):
        tz_name = request.env.user.tz or "UTC"
        return pytz.timezone(tz_name)

    def _to_local(self, dt_utc):
        """Converte datetime naive UTC para o fuso do usuário."""
        if not dt_utc:
            return None
        return pytz.utc.localize(dt_utc.replace(tzinfo=None)).astimezone(
            self._user_tz()
        )

    def _date_from(self, period):
        days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(period, 30)
        return datetime.utcnow() - timedelta(days=days)

    def _detect_fields(self, model):
        fields = model.fields_get()
        return {
            "close_date": "close_date" in fields,
            "last_stage_update": "last_stage_update" in fields,
            "ticket_ref": "ticket_ref" in fields,
        }

    def _end_date(self, ticket, detected_fields):
        """Retorna a melhor data de encerramento disponível para o ticket."""
        if detected_fields["close_date"] and ticket.close_date:
            return ticket.close_date
        if detected_fields["last_stage_update"] and ticket.last_stage_update:
            return ticket.last_stage_update
        return ticket.write_date

    def _hours_between(self, dt_end, dt_start):
        """Diferença em horas entre dois datetimes, sem dependência de fuso."""
        end = dt_end.replace(tzinfo=None) if dt_end else None
        start = dt_start.replace(tzinfo=None) if dt_start else None
        if not end or not start or end <= start:
            return 0.0
        return (end - start).total_seconds() / 3600

    def _split_tickets(self, tickets):
        open_t = tickets.filtered(lambda t: not t.stage_id.fold)
        closed_t = tickets.filtered(lambda t: t.stage_id.fold)
        return open_t, closed_t

    def _calc_tma(self, closed_tickets, detected_fields):
        if not closed_tickets:
            return 0.0
        hours = [
            self._hours_between(self._end_date(t, detected_fields), t.create_date)
            for t in closed_tickets
            if t.create_date and self._end_date(t, detected_fields)
        ]
        valid = [h for h in hours if h > 0]
        return round(sum(valid) / len(valid), 1) if valid else 0.0

    def _monthly_series(self, tickets, today, detected_fields):
        monthly_open = defaultdict(int)
        monthly_closed = defaultdict(int)
        for t in tickets:
            key = t.create_date.strftime("%b/%y")
            monthly_open[key] += 1
            if t.stage_id.fold:
                end = self._end_date(t, detected_fields)
                close_key = end.strftime("%b/%y") if end else key
                monthly_closed[close_key] += 1

        labels = [
            (today - timedelta(days=30 * i)).strftime("%b/%y")
            for i in range(11, -1, -1)
        ]
        return (
            labels,
            [monthly_open.get(m, 0) for m in labels],
            [monthly_closed.get(m, 0) for m in labels],
        )

    def _tag_counts(self, tickets):
        counts = defaultdict(int)
        for t in tickets:
            for tag in t.tag_id:
                counts[tag.name] += 1
        return counts

    def _site_counts(self, tickets, top_n=10):
        counts = defaultdict(int)
        for t in tickets:
            location = None
            if t.net_origin_id and t.net_origin_id.location:
                location = t.net_origin_id.location.strip()
            elif (
                t.circuit_id
                and t.circuit_id.origin_id
                and t.circuit_id.origin_id.location
            ):
                location = t.circuit_id.origin_id.location.strip()
            if location:
                counts[location] += 1
        top = sorted(counts.items(), key=lambda x: -x[1])[:top_n]
        labels = [item[0] for item in top]
        values = [item[1] for item in top]
        return {"labels": labels, "values": values}

    def _tag_by_month(self, tickets, labels):
        """Conta todos os tipos de evento por mês, sem filtro de categoria."""
        series = defaultdict(lambda: defaultdict(int))
        for t in tickets:
            if not t.tag_id:
                continue
            mk = t.create_date.strftime("%b/%y")
            series[t.tag_id.name][mk] += 1
        return {k: [v.get(m, 0) for m in labels] for k, v in series.items()}

    def _tma_by_tag(self, all_tickets, closed_tickets, detected_fields):
        all_tags = {tag.name for t in all_tickets for tag in t.tag_id}
        bucket = defaultdict(list)
        for t in closed_tickets:
            if not t.create_date:
                continue
            hrs = self._hours_between(self._end_date(t, detected_fields), t.create_date)
            if hrs <= 0:
                continue
            for tag in t.tag_id:
                bucket[tag.name].append(hrs)
        return {
            tag: round(sum(bucket[tag]) / len(bucket[tag]), 1) if bucket[tag] else 0.0
            for tag in all_tags
        }

    def _weekly_trend(self, tickets, today):
        """Retorna volume semanal para todos os tipos de evento."""
        labels = []
        series = defaultdict(lambda: [0] * 8)

        for i in range(7, -1, -1):
            wstart = today - timedelta(weeks=i + 1)
            wend = today - timedelta(weeks=i)
            week_idx = 7 - i
            labels.append("Atual" if i == 0 else f"S-{i}")
            for t in tickets:
                cd = t.create_date.replace(tzinfo=None)
                if not (wstart <= cd < wend):
                    continue
                if t.tag_id:
                    series[t.tag_id.name][week_idx] += 1

        return labels, dict(series)

    def _circuit_stats(self, tickets, detected_fields, period_days=30):
        """Estatísticas por circuito usando circuit_id (Many2one → network.circuit)."""
        today = datetime.utcnow()
        this_month = today.strftime("%Y-%m")
        last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

        stats = defaultdict(
            lambda: {
                "circuit_id": None,
                "name": "",
                "provider": "—",
                "speed": "—",
                "open": 0,
                "total": 0,
                "closed": 0,
                "tags": defaultdict(int),
                "tma_hrs": [],
                "last_failure": None,
                "monthly": defaultdict(int),
            }
        )

        for t in tickets:
            if not t.circuit_id:
                continue
            c = t.circuit_id
            key = c.id
            entry = stats[key]
            entry["circuit_id"] = c.id
            entry["name"] = c.link_designation or c.name or f"#{c.id}"
            entry["provider"] = c.provider_id.name if c.provider_id else "—"
            entry["speed"] = c.link_speed or "—"
            entry["total"] += 1

            if t.tag_id:
                entry["tags"][t.tag_id.name] += 1

            if not t.stage_id.fold:
                entry["open"] += 1
            else:
                entry["closed"] += 1
                hrs = self._hours_between(
                    self._end_date(t, detected_fields), t.create_date
                )
                if hrs > 0:
                    entry["tma_hrs"].append(hrs)

            if t.create_date:
                fd = t.create_date.replace(tzinfo=None)
                if not entry["last_failure"] or fd > entry["last_failure"]:
                    entry["last_failure"] = fd
                entry["monthly"][t.create_date.strftime("%Y-%m")] += 1

        result = []
        for _key, data in sorted(stats.items(), key=lambda x: -x[1]["total"])[:15]:
            main_tag = max(data["tags"], key=data["tags"].get) if data["tags"] else "—"
            hrs_list = data["tma_hrs"]
            avg_tma = round(sum(hrs_list) / len(hrs_list), 1) if hrs_list else 0.0

            curr = data["monthly"].get(this_month, 0)
            prev = data["monthly"].get(last_month, 0)
            if curr > prev:
                trend = "up"
            elif curr < prev:
                trend = "down"
            else:
                trend = "stable"

            total = data["total"]
            if total >= 5:
                health = "critico"
            elif total >= 3:
                health = "alerta"
            else:
                health = "ok"

            # MTBF: período analisado / incidentes fechados
            closed = data["closed"]
            mtbf = round(period_days * 24 / closed, 1) if closed > 0 else None

            result.append(
                {
                    "circuit_id": data["circuit_id"],
                    "name": data["name"],
                    "provider": data["provider"],
                    "speed": data["speed"],
                    "total": total,
                    "open": data["open"],
                    "closed": total - data["open"],
                    "main_tag": main_tag,
                    "tma": avg_tma,
                    "mtbf": mtbf,
                    "last_failure": (
                        self._to_local(data["last_failure"]).strftime("%d/%m %H:%M")
                        if data["last_failure"]
                        else "—"
                    ),
                    "trend": trend,
                    "health": health,
                    "pct": 0.0,
                }
            )

        total_all = sum(r["total"] for r in result)
        for r in result:
            r["pct"] = round(r["total"] / total_all * 100, 1) if total_all else 0.0

        return result

    def _top_circuits(self, tickets, open_t, total_open, detected_fields):
        """Top 10 circuitos com mais chamados abertos no período."""
        counts = defaultdict(
            lambda: {
                "circuit_id": None,
                "name": "",
                "open": 0,
                "tags": defaultdict(int),
                "tma_hrs": [],
            }
        )

        for t in open_t:
            if not t.circuit_id:
                continue
            c = t.circuit_id
            key = c.id
            counts[key]["circuit_id"] = c.id
            counts[key]["name"] = c.link_designation or c.name or f"#{c.id}"
            counts[key]["open"] += 1
            if t.tag_id:
                counts[key]["tags"][t.tag_id.name] += 1

        # TMA de fechados para os mesmos circuitos que têm abertos
        for t in tickets.filtered(lambda t: t.stage_id.fold and t.circuit_id):
            key = t.circuit_id.id
            if key not in counts or not t.create_date:
                continue
            hrs = self._hours_between(self._end_date(t, detected_fields), t.create_date)
            if hrs > 0:
                counts[key]["tma_hrs"].append(hrs)

        total = total_open or 1
        result = []
        for _key, data in sorted(counts.items(), key=lambda x: -x[1]["open"])[:10]:
            main_tag = max(data["tags"], key=data["tags"].get) if data["tags"] else "—"
            hrs_list = data["tma_hrs"]
            avg_tma = round(sum(hrs_list) / len(hrs_list), 1) if hrs_list else 0.0
            result.append(
                {
                    "circuit_id": data["circuit_id"],
                    "name": data["name"],
                    "total": data["open"],
                    "pct": round(data["open"] / total * 100, 1),
                    "main_tag": main_tag,
                    "tma": avg_tma,
                }
            )
        return result

    def _recent_tickets(self, tickets, fields):
        result = []
        now_utc = datetime.utcnow()
        cutoff = now_utc - timedelta(hours=12)
        recent = tickets.filtered(
            lambda t: t.create_date and t.create_date.replace(tzinfo=None) >= cutoff
        ).sorted("create_date", reverse=True)
        for t in recent:
            delta = now_utc - t.create_date.replace(tzinfo=None)
            total_secs = int(delta.total_seconds())
            hrs = total_secs // 3600
            mins = (total_secs - hrs * 3600) // 60

            create_local = self._to_local(t.create_date)
            write_local = self._to_local(t.write_date)

            circ = t.circuit_id
            is_router_register = t.portal_type == "router_register"
            is_network_config = t.portal_type == "network_config"
            if is_network_config:
                circuit_display = t.portal_net_equipment_id.name or "—"
            elif is_router_register:
                circuit_display = t.portal_hostname or "—"
            else:
                circuit_display = (circ.link_designation or circ.name) if circ else "—"

            # Verifica inatividade: write_date mais antigo que o limite do tag
            is_overdue = False
            if not t.stage_id.fold and t.inactivity_limit_minutes > 0 and t.write_date:
                inactive_secs = (
                    now_utc - t.write_date.replace(tzinfo=None)
                ).total_seconds()
                is_overdue = inactive_secs / 60 >= t.inactivity_limit_minutes

            result.append(
                {
                    "id": t.id,
                    "name": t.name or "(sem título)",
                    "tag": t.tag_id.name if t.tag_id else "—",
                    "circuit_id": circ.id if circ else None,
                    "circuit": circuit_display,
                    "create_date": create_local.strftime("%d/%m %H:%M"),
                    "tempo_aberto": f"{hrs}h {mins:02d}m",
                    "last_update": (
                        write_local.strftime("%d/%m %H:%M") if write_local else "—"
                    ),
                    "stage": t.stage_id.name if t.stage_id else "—",
                    "user": t.ticket_creator_id.name if t.ticket_creator_id else "—",
                    "external_ticket_number": t.external_ticket_number or "—",
                    "is_open": not t.stage_id.fold,
                    "is_overdue": is_overdue,
                    "traffic_restriction": bool(t.traffic_restriction),
                }
            )
        return result

    def _compute_plantao_status(self):
        Ticket = request.env["helpdesk.ticket"].sudo()

        # Turno e horários
        day_h, night_h = Ticket._get_shift_hours()
        try:
            tz_name = request.env.company.timezone or "UTC"
        except AttributeError:
            tz_name = "UTC"
        tz = pytz.timezone(tz_name)
        now_utc = datetime.utcnow()
        now_local = pytz.utc.localize(now_utc).astimezone(tz)

        if day_h <= now_local.hour < night_h:
            turno = "dia"
            shift_inicio = f"{day_h:02d}:00"
            shift_fim = f"{night_h:02d}:00"
            next_shift_local = now_local.replace(
                hour=night_h, minute=0, second=0, microsecond=0
            )
        elif now_local.hour >= night_h:
            turno = "noite"
            shift_inicio = f"{night_h:02d}:00"
            shift_fim = f"{day_h:02d}:00 (+1d)"
            next_shift_local = (now_local + timedelta(days=1)).replace(
                hour=day_h, minute=0, second=0, microsecond=0
            )
        else:
            turno = "noite"
            shift_inicio = f"{night_h:02d}:00 (-1d)"
            shift_fim = f"{day_h:02d}:00"
            next_shift_local = now_local.replace(
                hour=day_h, minute=0, second=0, microsecond=0
            )

        secs_until = int((next_shift_local - now_local).total_seconds())
        hrs_until = secs_until // 3600
        mins_until = (secs_until - hrs_until * 3600) // 60
        proximo_turno_em = f"{hrs_until}h {mins_until:02d}min"

        # Escala do turno atual
        entry = Ticket._get_duty_entry_from_escala()
        user1 = request.env["res.users"]
        user2 = request.env["res.users"]
        if entry:
            user1, user2 = entry.get_effective_users()

        def _user_info(u):
            if not u:
                return None
            return {
                "id": u.id,
                "name": u.name,
                "avatar_url": f"/web/image/res.users/{u.id}/avatar_128",
            }

        # Férias aprovadas ativas hoje
        today = now_local.date()
        ferias_ativas = []
        ferias_records = (
            request.env["helpdesk.ferias"]
            .sudo()
            .search(
                [
                    ("state", "=", "approved"),
                    ("date_from", "<=", today.isoformat()),
                    ("date_to", ">=", today.isoformat()),
                ]
            )
        )
        for f in ferias_records:
            ferias_ativas.append(
                {
                    "user": f.user_id.name if f.user_id else "—",
                    "substituto": f.substitute_id.name if f.substitute_id else "—",
                }
            )

        return {
            "turno": turno,
            "inicio": shift_inicio,
            "fim": shift_fim,
            "proximo_turno_em": proximo_turno_em,
            "user1": _user_info(user1),
            "user2": _user_info(user2),
            "ferias_ativas": ferias_ativas,
        }

    def _critical_tickets(self, open_tickets):
        """Retorna tickets abertos com tag_priority <= 5 (eventos críticos)."""
        now_utc = datetime.utcnow()
        result = []
        criticals = open_tickets.filtered(
            lambda t: t.tag_id and 1 <= t.tag_id.priority <= 5
        ).sorted(lambda t: (t.tag_id.priority if t.tag_id else 9999, t.create_date))
        for t in criticals:
            delta = now_utc - t.create_date.replace(tzinfo=None)
            total_secs = int(delta.total_seconds())
            hrs = total_secs // 3600
            mins = (total_secs - hrs * 3600) // 60

            is_overdue = False
            if t.inactivity_limit_minutes > 0 and t.write_date:
                inactive_secs = (
                    now_utc - t.write_date.replace(tzinfo=None)
                ).total_seconds()
                is_overdue = inactive_secs / 60 >= t.inactivity_limit_minutes

            circ = t.circuit_id
            circuit_display = (
                (circ.link_designation or circ.name) if circ else (t.hostname or "—")
            )
            create_local = self._to_local(t.create_date)
            result.append(
                {
                    "id": t.id,
                    "name": t.name or "(sem título)",
                    "tag": t.tag_id.name if t.tag_id else "—",
                    "tag_priority": t.tag_id.priority if t.tag_id else 9999,
                    "circuit": circuit_display,
                    "circuit_id": circ.id if circ else None,
                    "stage": t.stage_id.name if t.stage_id else "—",
                    "user": (
                        t.user_id.name
                        if t.user_id
                        else (t.ticket_creator_id.name if t.ticket_creator_id else "—")
                    ),
                    "provider": t.provider_id.name if t.provider_id else "—",
                    "external_ticket_number": t.external_ticket_number or "—",
                    "create_date": create_local.strftime("%d/%m %H:%M")
                    if create_local
                    else "—",
                    "tempo_aberto": f"{hrs}h {mins:02d}m",
                    "is_overdue": is_overdue,
                    "traffic_restriction": bool(t.traffic_restriction),
                }
            )
        return result

    def _falha_massiva_ativa(self, open_tickets):
        """Retorna tickets abertos com is_falha_massiva=True."""
        now_utc = datetime.utcnow()
        result = []
        massivas = open_tickets.filtered(lambda t: t.is_falha_massiva)
        for t in massivas:
            delta = now_utc - t.create_date.replace(tzinfo=None)
            hrs = int(delta.total_seconds()) // 3600
            mins = (int(delta.total_seconds()) - hrs * 3600) // 60
            circuit_count = len(t.falha_massiva_circuit_ids)
            site_count = len(t.falha_massiva_site_ids)
            result.append(
                {
                    "id": t.id,
                    "name": t.name or "(sem título)",
                    "tag": t.tag_id.name if t.tag_id else "—",
                    "circuit_count": circuit_count,
                    "site_count": site_count,
                    "elapsed": f"{hrs}h {mins:02d}m",
                }
            )
        return result

    # ── main ───────────────────────────────────────────────────────────────

    def _compute_data(
        self, period, tags=None, provider_id=None, health=None, stage_ids=None
    ):
        tags = tags or []
        health = health or []
        stage_ids = [int(s) for s in (stage_ids or [])]
        provider_id = int(provider_id) if provider_id else None

        today = datetime.utcnow()
        date_from = self._date_from(period)
        date_from_str = date_from.strftime("%Y-%m-%d 00:00:00")
        year_ago_str = (today - timedelta(days=365)).strftime("%Y-%m-%d 00:00:00")

        Ticket = request.env["helpdesk.ticket"]
        fields = self._detect_fields(Ticket)

        tickets_all_raw = Ticket.search([("create_date", ">=", date_from_str)])
        tickets_year_raw = Ticket.search([("create_date", ">=", year_ago_str)])

        # Coleta opções de filtro a partir dos dados não filtrados
        available_tags = sorted({t.tag_id.name for t in tickets_all_raw if t.tag_id})
        stage_map = {}
        for t in tickets_all_raw:
            if t.stage_id and t.stage_id.id not in stage_map:
                stage_map[t.stage_id.id] = {
                    "id": t.stage_id.id,
                    "name": t.stage_id.name,
                    "fold": t.stage_id.fold,
                }
        available_stages = sorted(stage_map.values(), key=lambda s: s["name"])
        providers_seen = {}
        for t in tickets_all_raw:
            if t.provider_id and t.provider_id.id not in providers_seen:
                providers_seen[t.provider_id.id] = t.provider_id.name
        available_providers = sorted(
            [{"id": pid, "name": name} for pid, name in providers_seen.items()],
            key=lambda x: x["name"],
        )

        # Aplica filtros de tag, operadora e estágio
        def _apply_filters(ticket_set):
            if tags:
                ticket_set = ticket_set.filtered(
                    lambda t: t.tag_id and t.tag_id.name in tags
                )
            if provider_id:
                ticket_set = ticket_set.filtered(
                    lambda t: t.provider_id and t.provider_id.id == provider_id
                )
            if stage_ids:
                ticket_set = ticket_set.filtered(
                    lambda t: t.stage_id and t.stage_id.id in stage_ids
                )
            return ticket_set

        tickets_all = _apply_filters(tickets_all_raw)
        tickets_year = _apply_filters(tickets_year_raw)
        open_t, closed_t = self._split_tickets(tickets_all)

        total = len(tickets_all)
        tma = self._calc_tma(closed_t, fields)

        labels, abertos, resolvidos = self._monthly_series(tickets_year, today, fields)
        tag_counts = self._tag_counts(tickets_all)
        total_tag_events = sum(tag_counts.values()) or 1
        tag_summary = sorted(
            [
                {
                    "tag": tag,
                    "total": count,
                    "pct": round(count / total_tag_events * 100, 1),
                }
                for tag, count in tag_counts.items()
            ],
            key=lambda x: -x["total"],
        )
        site_counts = self._site_counts(tickets_all)
        tag_month = self._tag_by_month(tickets_all, labels)
        tma_tags = self._tma_by_tag(tickets_all, closed_t, fields)
        wlabels, trend_series = self._weekly_trend(tickets_year, today)
        top = self._top_circuits(tickets_all, open_t, len(open_t), fields)
        recent = self._recent_tickets(tickets_all, fields)
        period_days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(period, 30)
        circuit_stats = self._circuit_stats(
            tickets_all, fields, period_days=period_days
        )
        critical_tickets = self._critical_tickets(open_t)
        falha_massiva_ativa = self._falha_massiva_ativa(open_t)

        # Aplica filtro de saúde (pós-cálculo)
        if health:
            circuit_stats = [c for c in circuit_stats if c["health"] in health]

        critical_count = sum(1 for c in circuit_stats if c["health"] == "critico")
        top_circuit = circuit_stats[0] if circuit_stats else None

        return {
            "kpis": {
                "total": total,
                "em_aberto": len(open_t),
                "resolvidos": len(closed_t),
                "tma": tma,
            },
            "mensal": {
                "labels": labels,
                "abertos": abertos,
                "resolvidos": resolvidos,
            },
            "tags": {
                "labels": list(tag_counts.keys()),
                "values": list(tag_counts.values()),
            },
            "equipamentos": {"labels": [], "values": []},
            "incidentes_por_site": site_counts,
            "tag_by_month": {"labels": labels, "series": tag_month},
            "tma_by_tag": tma_tags,
            "trend": {
                "labels": wlabels,
                "series": trend_series,
            },
            "top_redes": top,
            "recent_tickets": recent,
            "circuit_stats": circuit_stats,
            "circuit_kpis": {
                "total_circuits": len(circuit_stats),
                "critical_count": critical_count,
                "top_circuit_name": top_circuit["name"] if top_circuit else "—",
                "top_circuit_total": top_circuit["total"] if top_circuit else 0,
            },
            "available_tags": available_tags,
            "available_providers": available_providers,
            "available_stages": available_stages,
            "tag_summary": tag_summary,
            "critical_tickets": critical_tickets,
            "falha_massiva_ativa": falha_massiva_ativa,
        }
