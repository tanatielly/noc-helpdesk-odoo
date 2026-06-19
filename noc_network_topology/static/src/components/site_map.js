/** @odoo-module **/

import {
    Component,
    onMounted,
    onPatched,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
import {loadCSS, loadJS} from "@web/core/assets";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

// ---------------------------------------------------------------------------
// Geocodificação estática: fallback para sites sem coordenadas cadastradas
// ---------------------------------------------------------------------------
const BRAZIL_COORDS = {
    "rio branco": [-9.9754, -67.8249],
    macapa: [0.0349, -51.0694],
    manaus: [-3.119, -60.0217],
    belem: [-1.4558, -48.5039],
    "porto velho": [-8.7612, -63.9004],
    "boa vista": [2.8235, -60.6758],
    palmas: [-10.2491, -48.3243],
    maceio: [-9.6658, -35.735],
    salvador: [-12.9714, -38.5014],
    fortaleza: [-3.7319, -38.5267],
    "sao luis": [-2.5297, -44.3028],
    teresina: [-5.092, -42.8038],
    natal: [-5.7945, -35.211],
    "joao pessoa": [-7.1195, -34.845],
    recife: [-8.0476, -34.877],
    aracaju: [-10.9167, -37.05],
    brasilia: [-15.7797, -47.9297],
    goiania: [-16.6864, -49.2643],
    cuiaba: [-15.6014, -56.0979],
    "campo grande": [-20.4697, -54.6201],
    "sao paulo": [-23.5505, -46.6333],
    "rio de janeiro": [-22.9068, -43.1729],
    "belo horizonte": [-19.9167, -43.9345],
    vitoria: [-20.3222, -40.3381],
    campinas: [-22.9056, -47.0608],
    curitiba: [-25.4284, -49.2733],
    "porto alegre": [-30.0346, -51.2177],
    florianopolis: [-27.5954, -48.548],
    joinville: [-26.3044, -48.8455],
    londrina: [-23.3045, -51.1696],
    "foz do iguacu": [-25.5163, -54.5854],
};

function normalize(str) {
    if (!str) return "";
    return str.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
}

const _sortedKeys = Object.keys(BRAZIL_COORDS).sort((a, b) => b.length - a.length);

function resolveCoords(addressStr) {
    if (!addressStr) return null;
    const norm = normalize(addressStr);
    if (BRAZIL_COORDS[norm]) return BRAZIL_COORDS[norm];
    const parts = norm
        .split(/[,;]/)
        .map((p) => p.trim())
        .filter(Boolean)
        .reverse();
    for (const part of parts) {
        const subs = part
            .split(/\s*[-–]\s*/)
            .map((p) => p.trim())
            .filter(Boolean);
        for (const sub of subs) {
            if (BRAZIL_COORDS[sub]) return BRAZIL_COORDS[sub];
        }
        for (const key of _sortedKeys) {
            for (const sub of subs) {
                if (key.length <= 2 && sub.length > 4) continue;
                if (sub.includes(key)) return BRAZIL_COORDS[key];
            }
        }
    }
    for (const key of _sortedKeys) {
        if (norm.includes(key)) return BRAZIL_COORDS[key];
    }
    return null;
}

// ---------------------------------------------------------------------------

const EQUIPMENT_TYPE_LABELS = {
    switch: "Switch",
    router: "Roteador",
    firewall: "Firewall",
    access_point: "AP",
    server: "Servidor",
    other: "Outro",
};

// ---------------------------------------------------------------------------

class NetworkSiteMap extends Component {
    static template = "noc_network_topology.NetworkSiteMap";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.mapRef = useRef("map");
        this.cyRef = useRef("cy");

        this.leafletMap = null;
        this.clusterGroup = null;
        this.siteMarkers = new Map();
        this._pendingTopologyRender = false;
        this._resizeObserver = null;
        this._circuitLines = [];
        this._allCircuits = [];
        this._equipmentSiteMap = new Map();
        this._sitesWithOpenTickets = new Set();
        this._sitesWithCriticalTickets = new Set();
        this._criticalEquipmentIds = new Set();
        this._unavailableCircuitIds = new Set();
        this._sitesWithLinkAlert = new Set();

        this.state = useState({
            loading: true,
            sites: [],
            unmappedSites: [],
            selectedSite: null,
            siteEquipment: [],
            siteCircuits: [],
            loadingTopology: false,
        });

        onMounted(() => this._init());

        onPatched(() => {
            if (this._pendingTopologyRender && this.cyRef.el) {
                this._pendingTopologyRender = false;
                this._doRenderTopology();
            }
        });

        onWillUnmount(() => {
            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
                this._resizeObserver = null;
            }
            if (this.leafletMap) {
                this._circuitLines.forEach((l) => this.leafletMap.removeLayer(l));
                this._circuitLines = [];
                if (this.clusterGroup) {
                    this.leafletMap.removeLayer(this.clusterGroup);
                    this.clusterGroup = null;
                }
                this.leafletMap.remove();
                this.leafletMap = null;
            }
        });
    }

    async _ensureLibsLoaded() {
        await Promise.all([
            loadCSS("/noc_network_topology/static/lib/leaflet/leaflet.min.css"),
            loadCSS(
                "/noc_network_topology/static/lib/leaflet.markercluster/MarkerCluster.css"
            ),
            loadCSS(
                "/noc_network_topology/static/lib/leaflet.markercluster/MarkerCluster.Default.css"
            ),
            loadJS("/noc_network_topology/static/lib/leaflet/leaflet.min.js"),
        ]);
        await loadJS(
            "/noc_network_topology/static/lib/leaflet.markercluster/leaflet.markercluster.js"
        );
    }

    async _loadData() {
        const [sites, circuits, equipment, openTickets, unavailableTickets] =
            await Promise.all([
                this.orm.searchRead(
                    "network.site",
                    [],
                    [
                        "id",
                        "name",
                        "address",
                        "latitude",
                        "longitude",
                        "equipment_count",
                    ],
                    {limit: 0, order: "name asc"}
                ),
                this.orm.searchRead(
                    "network.circuit",
                    [["active", "=", true]],
                    ["id", "origin_id", "destination_id"],
                    {limit: 0}
                ),
                this.orm.searchRead("network.equipment", [], ["id", "site_ids"], {
                    limit: 0,
                }),
                this.orm.searchRead(
                    "helpdesk.ticket",
                    [
                        ["stage_id.closed", "!=", true],
                        "|",
                        ["net_origin_id", "!=", false],
                        ["net_destination_id", "!=", false],
                    ],
                    [
                        "net_origin_id",
                        "net_destination_id",
                        "is_equipamento_isolado",
                        "is_falha_massiva",
                    ],
                    {limit: 0}
                ),
                this.orm.searchRead(
                    "helpdesk.ticket",
                    [
                        ["stage_id.closed", "!=", true],
                        ["is_unavailable", "=", true],
                        ["circuit_id", "!=", false],
                    ],
                    ["circuit_id"],
                    {limit: 0}
                ),
            ]);
        this.state.sites = sites;
        this._allCircuits = circuits;
        this._equipmentSiteMap = new Map(equipment.map((e) => [e.id, e.site_ids]));

        // Constrói os conjuntos de sites/equipamentos com chamados abertos e críticos
        this._sitesWithOpenTickets = new Set();
        this._sitesWithCriticalTickets = new Set();
        this._criticalEquipmentIds = new Set();
        for (const ticket of openTickets) {
            const eqIds = [
                ticket.net_origin_id && ticket.net_origin_id[0],
                ticket.net_destination_id && ticket.net_destination_id[0],
            ].filter(Boolean);
            const isCritical = ticket.is_equipamento_isolado || ticket.is_falha_massiva;
            for (const eqId of eqIds) {
                for (const siteId of this._equipmentSiteMap.get(eqId) || []) {
                    this._sitesWithOpenTickets.add(siteId);
                    if (isCritical) this._sitesWithCriticalTickets.add(siteId);
                }
                if (isCritical) this._criticalEquipmentIds.add(eqId);
            }
        }

        // Constrói o conjunto de sites com alerta de link em risco
        this._unavailableCircuitIds = new Set(
            unavailableTickets.map((t) => t.circuit_id[0])
        );
        const eqTotal = new Map();
        const eqUnavail = new Map();
        for (const circuit of circuits) {
            const isUnavail = this._unavailableCircuitIds.has(circuit.id);
            for (const eqId of [circuit.origin_id[0], circuit.destination_id[0]]) {
                eqTotal.set(eqId, (eqTotal.get(eqId) || 0) + 1);
                if (isUnavail) eqUnavail.set(eqId, (eqUnavail.get(eqId) || 0) + 1);
            }
        }
        this._sitesWithLinkAlert = new Set();
        for (const [eqId, total] of eqTotal) {
            const unavail = eqUnavail.get(eqId) || 0;
            if (unavail > 0 && total - unavail <= 2) {
                for (const siteId of this._equipmentSiteMap.get(eqId) || []) {
                    this._sitesWithLinkAlert.add(siteId);
                }
            }
        }

        this.state.loading = false;
    }

    async _init() {
        await this._ensureLibsLoaded();
        await this._loadData();
        // Aguarda animações de transição de página do Odoo (~300ms) terminarem
        await new Promise((resolve) => setTimeout(resolve, 400));
        this._renderMap();
        if (this.props.onActionReady) {
            this.props.onActionReady();
        }
    }

    _getSiteCoords(site) {
        if (site.latitude && site.longitude) return [site.latitude, site.longitude];
        return resolveCoords(site.address);
    }

    _injectPulseStyle() {
        if (document.getElementById("site-pulse-style")) return;
        const style = document.createElement("style");
        style.id = "site-pulse-style";
        style.textContent = `
            @keyframes site-ring-expand {
                0%   { opacity: 0.85; transform: translate(-50%, -50%) scale(1); }
                100% { opacity: 0;    transform: translate(-50%, -50%) scale(2); }
            }
            .site-ring-pulse {
                position: absolute;
                top: 50%;
                left: 50%;
                border-radius: 50%;
                animation: site-ring-expand 1.1s ease-out infinite;
                pointer-events: none;
            }
        `;
        document.head.appendChild(style);
    }

    _markerColor(isSelected, hasCriticalTickets, hasOpenTickets, hasLinkAlert) {
        if (isSelected) return "#dc3545";
        if (hasCriticalTickets) return "#dc3545";
        if (hasLinkAlert) return "#fd7e14";
        if (hasOpenTickets) return "#ffc107";
        return "#0056b3";
    }

    _makeIcon(color, size, pulse = false) {
        if (pulse) {
            const PAD = 24;
            const container = size + PAD * 2;
            const half = container / 2;
            return window.L.divIcon({
                html: `<div style="position:relative;width:${container}px;height:${container}px;"><div class="site-ring-pulse" style="width:${size}px;height:${size}px;background:${color};"></div><div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:${size}px;height:${size}px;background:${color};border:3px solid #ffffff;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.5);cursor:pointer;"></div></div>`,
                className: "",
                iconSize: [container, container],
                iconAnchor: [half, half],
            });
        }
        const half = size / 2;
        return window.L.divIcon({
            html: `<div style="width:${size}px;height:${size}px;background:${color};border:3px solid #ffffff;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.5);cursor:pointer;"></div>`,
            className: "",
            iconSize: [size, size],
            iconAnchor: [half, half],
        });
    }

    _createMarker(
        coords,
        isSelected,
        site,
        hasCriticalTickets,
        hasOpenTickets,
        hasLinkAlert
    ) {
        const color = this._markerColor(
            isSelected,
            hasCriticalTickets,
            hasOpenTickets,
            hasLinkAlert
        );
        const size = isSelected ? 26 : 20;
        const pulse = !isSelected && hasLinkAlert && !hasCriticalTickets;
        const marker = window.L.marker(coords, {
            icon: this._makeIcon(color, size, pulse),
            title: site.name,
        });

        marker._hasCritical = hasCriticalTickets;
        marker._hasOpen = hasOpenTickets;
        marker._hasLinkAlert = hasLinkAlert;

        marker.bindTooltip(
            `<strong>${site.name}</strong><br/>${
                site.address || ""
            }<br/>Equipamentos: ${site.equipment_count || 0}`,
            {sticky: true}
        );

        marker.on("click", () => this._selectSite(site));

        marker.setSelected = (sel) => {
            const c = this._markerColor(
                sel,
                hasCriticalTickets,
                hasOpenTickets,
                hasLinkAlert
            );
            const s = sel ? 26 : 20;
            const p = !sel && hasLinkAlert && !hasCriticalTickets;
            marker.setIcon(this._makeIcon(c, s, p));
        };

        return marker;
    }

    _renderMap() {
        if (!window.L || !this.mapRef.el) return;

        this._injectPulseStyle();

        if (!this.leafletMap) {
            this.leafletMap = window.L.map(this.mapRef.el, {
                center: [-15.7797, -47.9297],
                zoom: 4,
                zoomControl: true,
                fadeAnimation: false,
                zoomAnimation: false,
                markerZoomAnimation: false,
            });
            window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution: "© OpenStreetMap contributors",
                maxZoom: 18,
            }).addTo(this.leafletMap);

            if (window.ResizeObserver && this.mapRef.el) {
                this._resizeObserver = new ResizeObserver(() => {
                    if (this.leafletMap && this.mapRef.el.offsetWidth > 0) {
                        this.leafletMap.invalidateSize({animate: false});
                    }
                });
                this._resizeObserver.observe(this.mapRef.el);
            }
        }

        // Remove cluster group anterior
        if (this.clusterGroup) {
            this.leafletMap.removeLayer(this.clusterGroup);
        }
        this.siteMarkers.clear();

        this.clusterGroup = window.L.markerClusterGroup({
            maxClusterRadius: 50,
            disableClusteringAtZoom: 12,
            animate: false,
            iconCreateFunction: (cluster) => {
                const children = cluster.getAllChildMarkers();
                const hasCritical = children.some((m) => m._hasCritical);
                const hasOpen = children.some((m) => m._hasOpen);
                const hasAlert = children.some((m) => m._hasLinkAlert);
                const color = hasCritical
                    ? "#dc3545"
                    : hasAlert
                    ? "#fd7e14"
                    : hasOpen
                    ? "#ffc107"
                    : "#0056b3";
                const count = cluster.getChildCount();
                const size = count < 10 ? 32 : count < 100 ? 38 : 46;
                const fs = count < 10 ? 13 : 11;
                const pulse = hasAlert;
                const PAD = pulse ? 24 : 0;
                const container = size + PAD * 2;
                const chalf = container / 2;
                const ringHtml = pulse
                    ? `<div class="site-ring-pulse" style="width:${size}px;height:${size}px;background:${color};"></div>`
                    : "";
                return window.L.divIcon({
                    html: `<div style="position:relative;width:${container}px;height:${container}px;">${ringHtml}<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:${size}px;height:${size}px;background:${color};border:3px solid #ffffff;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:${fs}px;">${count}</div></div>`,
                    className: "",
                    iconSize: [container, container],
                    iconAnchor: [chalf, chalf],
                });
            },
        });

        const unmapped = [];

        for (const site of this.state.sites) {
            const coords = this._getSiteCoords(site);
            if (!coords) {
                unmapped.push(site.name);
                continue;
            }

            const isSelected = this.state.selectedSite?.id === site.id;
            const hasCriticalTickets = this._sitesWithCriticalTickets.has(site.id);
            const hasOpenTickets = this._sitesWithOpenTickets.has(site.id);
            const hasLinkAlert = this._sitesWithLinkAlert.has(site.id);
            const marker = this._createMarker(
                coords,
                isSelected,
                site,
                hasCriticalTickets,
                hasOpenTickets,
                hasLinkAlert
            );
            this.siteMarkers.set(site.id, marker);
            this.clusterGroup.addLayer(marker);
        }

        this.leafletMap.addLayer(this.clusterGroup);
        this.state.unmappedSites = unmapped;
        this._renderCircuitLines();
    }

    _computeCircuitSitePairs() {
        const siteById = new Map(this.state.sites.map((s) => [s.id, s]));
        // Key → [siteA, siteB, isCritical]
        const pairs = new Map();
        for (const circuit of this._allCircuits) {
            const originSites = this._equipmentSiteMap.get(circuit.origin_id[0]) || [];
            const destSites =
                this._equipmentSiteMap.get(circuit.destination_id[0]) || [];
            const isCritical = this._isCircuitCritical(circuit);
            for (const aId of originSites) {
                for (const bId of destSites) {
                    if (aId === bId) continue;
                    const key = `${Math.min(aId, bId)}-${Math.max(aId, bId)}`;
                    const existing = pairs.get(key);
                    // Um par já crítico não pode ser rebaixado por outro circuito normal
                    if (!existing || (!existing[2] && isCritical)) {
                        pairs.set(key, [
                            siteById.get(aId),
                            siteById.get(bId),
                            isCritical,
                        ]);
                    }
                }
            }
        }
        return [...pairs.values()].filter(([a, b]) => a && b);
    }

    _isCircuitCritical(circuit) {
        return (
            this._criticalEquipmentIds.has(circuit.origin_id[0]) ||
            this._criticalEquipmentIds.has(circuit.destination_id[0])
        );
    }

    _renderCircuitLines() {
        this._circuitLines.forEach((l) => this.leafletMap.removeLayer(l));
        this._circuitLines = [];

        // Renderiza linhas normais primeiro, depois as críticas (ficam por cima)
        const pairs = this._computeCircuitSitePairs();
        for (const critical of [false, true]) {
            for (const [siteA, siteB, isCritical] of pairs) {
                if (isCritical !== critical) continue;
                const coordsA = this._getSiteCoords(siteA);
                const coordsB = this._getSiteCoords(siteB);
                if (!coordsA || !coordsB) continue;
                const line = window.L.polyline([coordsA, coordsB], {
                    color: isCritical ? "#dc3545" : "#adb5bd",
                    weight: isCritical ? 2.5 : 2,
                    dashArray: "6 5",
                    opacity: isCritical ? 1 : 0.8,
                });
                line.addTo(this.leafletMap);
                this._circuitLines.push(line);
            }
        }
    }

    async _selectSite(site) {
        if (this.state.selectedSite?.id === site.id) {
            this.closeSitePanel();
            return;
        }

        if (this.cyRef.el) this.cyRef.el.innerHTML = "";

        this.siteMarkers.forEach((marker, siteId) => {
            marker.setSelected(siteId === site.id);
        });

        this.state.selectedSite = site;
        this.state.siteEquipment = [];
        this.state.siteCircuits = [];
        this.state.loadingTopology = true;

        setTimeout(() => {
            if (this.leafletMap) this.leafletMap.invalidateSize();
        }, 320);

        if (!site.equipment_count) {
            this.state.loadingTopology = false;
            return;
        }

        const equipment = await this.orm.searchRead(
            "network.equipment",
            [["site_ids", "in", [site.id]]],
            ["id", "name", "status", "ticket_count", "equipment_type"],
            {limit: 0, order: "name asc"}
        );
        const eqIds = equipment.map((e) => e.id);
        const circuits = await this.orm.searchRead(
            "network.circuit",
            [
                ["active", "=", true],
                "|",
                ["origin_id", "in", eqIds],
                ["destination_id", "in", eqIds],
            ],
            ["id", "link_designation", "name", "origin_id", "destination_id"],
            {limit: 0}
        );

        this.state.siteEquipment = equipment;
        this.state.siteCircuits = circuits;
        this.state.loadingTopology = false;
        this._pendingTopologyRender = true;
    }

    _nodeColor(eq) {
        if (eq.ticket_count > 0) return "#dc3545";
        if (eq.status === "maintenance") return "#ffc107";
        if (eq.status === "active") return "#28a745";
        return "#6c757d";
    }

    _doRenderTopology() {
        if (!this.cyRef.el) return;

        const NS = "http://www.w3.org/2000/svg";
        const equipment = this.state.siteEquipment;
        const circuits = this.state.siteCircuits;
        const eqIds = new Set(equipment.map((e) => e.id));

        const W = this.cyRef.el.clientWidth || 420;
        const H = this.cyRef.el.clientHeight || 420;
        const cx = W / 2;
        const cy = H / 2;
        const R = Math.min(W, H) * 0.36;
        const NODE_R = 30;

        const pos = new Map();
        equipment.forEach((eq, i) => {
            const angle = (2 * Math.PI * i) / equipment.length - Math.PI / 2;
            pos.set(eq.id, {
                x: equipment.length === 1 ? cx : cx + R * Math.cos(angle),
                y: equipment.length === 1 ? cy : cy + R * Math.sin(angle),
                eq,
            });
        });

        const mk = (tag, attrs) => {
            const el = document.createElementNS(NS, tag);
            Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
            return el;
        };

        const svg = mk("svg", {
            width: "100%",
            height: "100%",
            viewBox: `0 0 ${W} ${H}`,
        });

        circuits
            .filter((c) => eqIds.has(c.origin_id[0]) && eqIds.has(c.destination_id[0]))
            .forEach((c) => {
                const a = pos.get(c.origin_id[0]);
                const b = pos.get(c.destination_id[0]);
                svg.appendChild(
                    mk("line", {
                        x1: a.x,
                        y1: a.y,
                        x2: b.x,
                        y2: b.y,
                        stroke: "#adb5bd",
                        "stroke-width": 1.5,
                        "stroke-dasharray": "5 4",
                    })
                );
                const label = c.link_designation || c.name;
                if (label) {
                    const t = mk("text", {
                        x: (a.x + b.x) / 2,
                        y: (a.y + b.y) / 2 - 4,
                        "text-anchor": "middle",
                        "font-size": 8,
                        fill: "#6c757d",
                    });
                    t.textContent = label;
                    svg.appendChild(t);
                }
            });

        pos.forEach(({x, y, eq}) => {
            const g = document.createElementNS(NS, "g");
            g.style.cursor = "pointer";
            g.addEventListener("click", () => {
                this.actionService.doAction({
                    type: "ir.actions.act_window",
                    res_model: "network.equipment",
                    res_id: eq.id,
                    views: [[false, "form"]],
                    target: "current",
                });
            });
            g.appendChild(
                mk("circle", {
                    cx: x,
                    cy: y,
                    r: NODE_R,
                    fill: this._nodeColor(eq),
                    stroke: "#fff",
                    "stroke-width": 2,
                })
            );
            const nm = mk("text", {
                x,
                y: y + 3,
                "text-anchor": "middle",
                "dominant-baseline": "middle",
                "font-size": 9,
                "font-weight": "bold",
                fill: "#fff",
            });
            nm.textContent = eq.name.length > 10 ? eq.name.slice(0, 9) + "…" : eq.name;
            g.appendChild(nm);
            const tp = mk("text", {
                x,
                y: y + NODE_R + 12,
                "text-anchor": "middle",
                "font-size": 8,
                fill: "#495057",
            });
            tp.textContent = EQUIPMENT_TYPE_LABELS[eq.equipment_type] || "";
            g.appendChild(tp);
            svg.appendChild(g);
        });

        this.cyRef.el.innerHTML = "";
        this.cyRef.el.appendChild(svg);
    }

    closeSitePanel() {
        if (this.cyRef.el) this.cyRef.el.innerHTML = "";
        this.siteMarkers.forEach((marker) => marker.setSelected(false));
        this.state.selectedSite = null;
        this.state.siteEquipment = [];
        this.state.siteCircuits = [];
    }

    openSiteForm(site) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "network.site",
            res_id: site.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("network_site_map", NetworkSiteMap);
