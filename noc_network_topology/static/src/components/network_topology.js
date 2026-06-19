/** @odoo-module **/

import {Component, onMounted, onWillUnmount, useRef, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {useService} from "@web/core/utils/hooks";
import {loadCSS, loadJS} from "@web/core/assets";

// ---------------------------------------------------------------------------
// Geocodificação estática: cidades/estados brasileiros → [lat, lng]
// A chave é o texto normalizado (sem acento, minúsculo).
// ---------------------------------------------------------------------------
const BRAZIL_COORDS = {
    // Região Norte
    "rio branco": [-9.9754, -67.8249],
    ac: [-9.9754, -67.8249],
    macapa: [0.0349, -51.0694],
    ap: [0.0349, -51.0694],
    manaus: [-3.119, -60.0217],
    am: [-3.119, -60.0217],
    belem: [-1.4558, -48.5039],
    pa: [-1.4558, -48.5039],
    "porto velho": [-8.7612, -63.9004],
    ro: [-8.7612, -63.9004],
    "boa vista": [2.8235, -60.6758],
    rr: [2.8235, -60.6758],
    palmas: [-10.2491, -48.3243],
    to: [-10.2491, -48.3243],
    // Região Nordeste
    maceio: [-9.6658, -35.735],
    al: [-9.6658, -35.735],
    salvador: [-12.9714, -38.5014],
    ba: [-12.9714, -38.5014],
    fortaleza: [-3.7319, -38.5267],
    ce: [-3.7319, -38.5267],
    "sao luis": [-2.5297, -44.3028],
    ma: [-2.5297, -44.3028],
    teresina: [-5.092, -42.8038],
    pi: [-5.092, -42.8038],
    natal: [-5.7945, -35.211],
    rn: [-5.7945, -35.211],
    "joao pessoa": [-7.1195, -34.845],
    pb: [-7.1195, -34.845],
    recife: [-8.0476, -34.877],
    pe: [-8.0476, -34.877],
    aracaju: [-10.9167, -37.05],
    se: [-10.9167, -37.05],
    "feira de santana": [-12.2664, -38.9663],
    caruaru: [-8.276, -35.9763],
    "campina grande": [-7.2306, -35.8811],
    mossoró: [-5.1878, -37.3445],
    mossoro: [-5.1878, -37.3445],
    ilheus: [-14.789, -39.0461],
    petrolina: [-9.3989, -40.5008],
    "juazeiro do norte": [-7.2133, -39.3153],
    // Região Centro-Oeste
    brasilia: [-15.7797, -47.9297],
    df: [-15.7797, -47.9297],
    goiania: [-16.6864, -49.2643],
    go: [-16.6864, -49.2643],
    cuiaba: [-15.6014, -56.0979],
    mt: [-15.6014, -56.0979],
    "campo grande": [-20.4697, -54.6201],
    ms: [-20.4697, -54.6201],
    anapolis: [-16.3281, -48.9527],
    rondonopolis: [-16.4727, -54.6358],
    dourados: [-22.2228, -54.8056],
    // Região Sudeste
    "sao paulo": [-23.5505, -46.6333],
    sp: [-23.5505, -46.6333],
    "rio de janeiro": [-22.9068, -43.1729],
    rj: [-22.9068, -43.1729],
    "belo horizonte": [-19.9167, -43.9345],
    mg: [-19.9167, -43.9345],
    vitoria: [-20.3222, -40.3381],
    es: [-20.3222, -40.3381],
    campinas: [-22.9056, -47.0608],
    guarulhos: [-23.4543, -46.5338],
    santos: [-23.9618, -46.3322],
    "sao bernardo do campo": [-23.6939, -46.565],
    "sao jose dos campos": [-23.1794, -45.8869],
    "ribeirao preto": [-21.1775, -47.8103],
    sorocaba: [-23.5015, -47.4526],
    osasco: [-23.5329, -46.7919],
    contagem: [-19.9317, -44.0536],
    uberlandia: [-18.9188, -48.2769],
    "juiz de fora": [-21.7642, -43.3503],
    betim: [-19.9682, -44.1982],
    niteroi: [-22.8833, -43.1036],
    "duque de caxias": [-22.7858, -43.3117],
    "nova iguacu": [-22.7558, -43.4506],
    "mogi das cruzes": [-23.5225, -46.1875],
    "sao jose do rio preto": [-20.8113, -49.3758],
    carapicuiba: [-23.5228, -46.8389],
    piracicaba: [-22.7253, -47.6492],
    bauru: [-22.3246, -49.071],
    limeira: [-22.568, -47.4011],
    jundiai: [-23.1864, -46.884],
    marilia: [-22.2144, -49.9459],
    franca: [-20.5386, -47.4007],
    "vila velha": [-20.3297, -40.2922],
    serra: [-20.1286, -40.3078],
    cariacica: [-20.2642, -40.4169],
    divinopolis: [-20.1386, -44.885],
    macae: [-22.3711, -41.7869],
    "campos dos goytacazes": [-21.7545, -41.3244],
    petropolis: [-22.5046, -43.1786],
    "volta redonda": [-22.5231, -44.1043],
    // Região Sul
    curitiba: [-25.4284, -49.2733],
    pr: [-25.4284, -49.2733],
    "porto alegre": [-30.0346, -51.2177],
    rs: [-30.0346, -51.2177],
    florianopolis: [-27.5954, -48.548],
    sc: [-27.5954, -48.548],
    joinville: [-26.3044, -48.8455],
    londrina: [-23.3045, -51.1696],
    "caxias do sul": [-29.1681, -51.1794],
    maringa: [-23.4205, -51.9333],
    "ponta grossa": [-25.0945, -50.1618],
    cascavel: [-24.9578, -53.4558],
    blumenau: [-26.9195, -49.0661],
    "sao jose": [-27.5969, -48.6388],
    pelotas: [-31.7654, -52.3376],
    canoas: [-29.9191, -51.1837],
    "santa maria": [-29.6869, -53.8019],
    "foz do iguacu": [-25.5163, -54.5854],
    chapeco: [-27.1006, -52.6152],
    criciuma: [-28.678, -49.3697],
};

// Normaliza string: remove acentos, minúscula, strip
function normalize(str) {
    if (!str) return "";
    return str.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
}

// Chaves ordenadas por comprimento decrescente (evita "pa" casar antes de "palmas")
const _sortedKeys = Object.keys(BRAZIL_COORDS).sort((a, b) => b.length - a.length);

function resolveCoords(locationStr) {
    if (!locationStr) return null;

    // Detecta string de coordenadas brutas, ex: "-23.5505, -46.6333" (Google Maps)
    const coordMatch = String(locationStr)
        .trim()
        .match(/^(-?\d{1,3}(?:[.,]\d+)?)[,\s]+(-?\d{1,3}(?:[.,]\d+)?)$/);
    if (coordMatch) {
        const lat = parseFloat(coordMatch[1].replace(",", "."));
        const lng = parseFloat(coordMatch[2].replace(",", "."));
        if (!isNaN(lat) && !isNaN(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180) {
            return [lat, lng];
        }
    }

    const norm = normalize(locationStr);

    if (BRAZIL_COORDS[norm]) return BRAZIL_COORDS[norm];

    const parts = norm
        .split(/[,;]/)
        .map((p) => p.trim())
        .filter(Boolean)
        .reverse();

    for (const part of parts) {
        const subParts = part
            .split(/\s*[-–]\s*/)
            .map((p) => p.trim())
            .filter(Boolean);

        for (const sub of subParts) {
            if (BRAZIL_COORDS[sub]) return BRAZIL_COORDS[sub];
        }

        for (const key of _sortedKeys) {
            for (const sub of subParts) {
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

// Jitter para equipamentos na mesma coordenada exata
const _jitterMap = new Map();
function jitteredCoords(lat, lng, locationKey) {
    const count = _jitterMap.get(locationKey) || 0;
    _jitterMap.set(locationKey, count + 1);
    if (count === 0) return [lat, lng];
    // Espiral de Fibonacci para distribuir sem sobreposição
    const angle = (count * 137.5 * Math.PI) / 180;
    const r = 0.015 * Math.ceil(count / 6);
    return [lat + r * Math.sin(angle), lng + r * Math.cos(angle)];
}

const STATUS_LABELS = {
    active: "Ativo",
    maintenance: "Manutenção",
    inactive: "Inativo",
    obsolete: "Obsoleto",
};

// ---------------------------------------------------------------------------

class NetworkTopology extends Component {
    static template = "noc_network_topology.NetworkTopology";
    static props = {...standardFieldProps};

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.mapRef = useRef("map");
        this.leafletMap = null;
        this.markers = [];
        this.polylines = [];
        this.siteMarkers = [];
        this.state = useState({
            loading: true,
            locations: [],
            vlans: [],
            filterLocation: "",
            filterVlan: 0,
            unmapped: [],
            allEquipment: [],
            allCircuits: [],
            allSites: [],
            showSites: true,
        });
        this._resizeObserver = null;
        onMounted(() => this._init());
        onWillUnmount(() => {
            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
                this._resizeObserver = null;
            }
            if (this.leafletMap) {
                this.leafletMap.remove();
                this.leafletMap = null;
            }
        });
    }

    async _ensureLibsLoaded() {
        await loadCSS("/noc_network_topology/static/lib/leaflet/leaflet.min.css");
        await loadJS("/noc_network_topology/static/lib/leaflet/leaflet.min.js");
    }

    async _init() {
        await this._ensureLibsLoaded();
        await this._loadData();
        this._renderMap();
    }

    async _loadData() {
        const [equipment, circuits, vlans, sites] = await Promise.all([
            this.orm.searchRead(
                "network.equipment",
                [],
                [
                    "id",
                    "name",
                    "status",
                    "location",
                    "latitude",
                    "longitude",
                    "ticket_count",
                    "vlan_ids",
                ],
                {limit: 0}
            ),
            this.orm.searchRead(
                "network.circuit",
                [["active", "=", true]],
                ["id", "origin_id", "destination_id"],
                {limit: 0}
            ),
            this.orm.searchRead("network.vlan", [], ["id", "vlan_id", "name"], {
                order: "vlan_id asc",
                limit: 0,
            }),
            this.orm.searchRead(
                "network.site",
                [],
                ["id", "name", "address", "latitude", "longitude"],
                {limit: 0, order: "name asc"}
            ),
        ]);
        this.state.allEquipment = equipment;
        this.state.allCircuits = circuits;
        this.state.vlans = vlans;
        this.state.allSites = sites;
        this.state.locations = [
            ...new Set(equipment.map((e) => e.location).filter(Boolean)),
        ].sort();
        this.state.loading = false;
    }

    _getFilteredData() {
        let equipment = this.state.allEquipment;
        if (this.state.filterLocation) {
            equipment = equipment.filter(
                (e) => e.location === this.state.filterLocation
            );
        }
        if (this.state.filterVlan) {
            equipment = equipment.filter((e) =>
                e.vlan_ids.includes(this.state.filterVlan)
            );
        }
        const ids = new Set(equipment.map((e) => e.id));
        const circuits = this.state.allCircuits.filter(
            (c) => ids.has(c.origin_id[0]) && ids.has(c.destination_id[0])
        );
        return {equipment, circuits};
    }

    _nodeColor(eq) {
        if (eq.ticket_count > 0) return "#dc3545";
        if (eq.status === "maintenance") return "#ffc107";
        if (eq.status === "active") return "#28a745";
        return "#6c757d";
    }

    // ---- Helpers de renderização (extraídos para reduzir complexidade) ----

    _initLeafletMap() {
        if (this.leafletMap) return;
        this.leafletMap = window.L.map(this.mapRef.el, {
            center: [-15.7797, -47.9297],
            zoom: 4,
            zoomControl: true,
        });
        window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenStreetMap contributors",
            maxZoom: 18,
        }).addTo(this.leafletMap);
    }

    _createMarker(eq, lat, lng, currentId) {
        const isCurrent = eq.id === currentId;
        const marker = window.L.circleMarker([lat, lng], {
            radius: isCurrent ? 14 : 10,
            fillColor: this._nodeColor(eq),
            color: isCurrent ? "#0056b3" : "#ffffff",
            weight: isCurrent ? 3 : 2,
            opacity: 1,
            fillOpacity: 0.9,
        }).addTo(this.leafletMap);

        const statusLabel = STATUS_LABELS[eq.status] || eq.status;
        marker.bindTooltip(
            `<strong>${eq.name}</strong><br/>` +
                `Status: ${statusLabel}<br/>` +
                `Tickets abertos: ${eq.ticket_count}<br/>` +
                `Localização: ${eq.location || "—"}`,
            {sticky: true}
        );
        marker.on("click", () => {
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "network.equipment",
                res_id: eq.id,
                views: [[false, "form"]],
                target: "current",
            });
        });
        return marker;
    }

    _buildEquipmentMarkers(equipment, currentId) {
        const eqCoords = new Map();
        const unmapped = [];
        for (const eq of equipment) {
            const base =
                eq.latitude || eq.longitude
                    ? [eq.latitude || 0, eq.longitude || 0]
                    : resolveCoords(eq.location);
            if (!base) {
                unmapped.push(eq.name);
                continue;
            }
            const locationKey =
                eq.latitude || eq.longitude
                    ? `${eq.latitude || 0},${eq.longitude || 0}`
                    : normalize(eq.location || "");
            const [lat, lng] = jitteredCoords(base[0], base[1], locationKey);
            eqCoords.set(eq.id, [lat, lng]);
            this.markers.push(this._createMarker(eq, lat, lng, currentId));
        }
        return {eqCoords, unmapped};
    }

    _buildCircuitLines(circuits, eqCoords) {
        for (const c of circuits) {
            const orig = eqCoords.get(c.origin_id[0]);
            const dest = eqCoords.get(c.destination_id[0]);
            if (orig && dest) {
                const line = window.L.polyline([orig, dest], {
                    color: "#6c757d",
                    weight: 1.5,
                    opacity: 0.6,
                    dashArray: "4 4",
                }).addTo(this.leafletMap);
                this.polylines.push(line);
            }
        }
    }

    _setupResizeObserver() {
        if (this._resizeObserver || !window.ResizeObserver) return;
        this._resizeObserver = new ResizeObserver(() => {
            if (this.leafletMap && this.mapRef.el && this.mapRef.el.offsetWidth > 0) {
                this.leafletMap.invalidateSize();
                if (this.markers.length > 0) {
                    const group = window.L.featureGroup(this.markers);
                    this.leafletMap.fitBounds(group.getBounds().pad(0.2));
                }
            }
        });
        this._resizeObserver.observe(this.mapRef.el);
    }

    _buildSiteMarkers(sites) {
        this.siteMarkers.forEach((m) => m.remove());
        this.siteMarkers = [];
        if (!this.state.showSites) return;
        for (const site of sites) {
            const coords =
                site.latitude || site.longitude
                    ? [site.latitude || 0, site.longitude || 0]
                    : resolveCoords(site.address);
            if (!coords) continue;
            const marker = window.L.circleMarker(coords, {
                radius: 9,
                fillColor: "#6f42c1",
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9,
            }).addTo(this.leafletMap);
            marker.bindTooltip(
                `<strong>Site: ${site.name}</strong><br/>${site.address || ""}`,
                {sticky: true}
            );
            this.siteMarkers.push(marker);
        }
    }

    _renderMap() {
        if (!window.L || !this.mapRef.el) return;

        _jitterMap.clear();
        const currentId = this.props.record.data.id;
        const {equipment, circuits} = this._getFilteredData();

        this._initLeafletMap();

        this.markers.forEach((m) => m.remove());
        this.polylines.forEach((p) => p.remove());
        this.markers = [];
        this.polylines = [];

        const {eqCoords, unmapped} = this._buildEquipmentMarkers(equipment, currentId);
        this._buildCircuitLines(circuits, eqCoords);
        this._buildSiteMarkers(this.state.allSites);
        this.state.unmapped = unmapped;

        if (this.markers.length > 0) {
            const group = window.L.featureGroup(this.markers);
            this.leafletMap.fitBounds(group.getBounds().pad(0.2));
        }

        this._setupResizeObserver();
    }

    onFilterLocation(ev) {
        this.state.filterLocation = ev.target.value;
        this._renderMap();
    }

    onFilterVlan(ev) {
        this.state.filterVlan = ev.target.value ? parseInt(ev.target.value, 10) : 0;
        this._renderMap();
    }

    onToggleSites() {
        this.state.showSites = !this.state.showSites;
        this._buildSiteMarkers(this.state.allSites);
    }
}

registry.category("fields").add("network_topology", NetworkTopology);
