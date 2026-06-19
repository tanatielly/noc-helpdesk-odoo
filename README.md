# NOC Helpdesk Suite — Odoo 16 Modules

A suite of **11 custom Odoo 16 modules** designed for **Network Operations Centers (NOC)** of any company. Built on top of the [helpdesk_mgmt](https://github.com/OCA/helpdesk) OCA module, it adds network-specific workflows, inventory management, real-time monitoring, and analytics dashboards.

---

## Modules

| Module | Description |
|---|---|
| `noc_base` | Meta-module: installs the full suite with a single click |
| `noc_contacts` | ISP providers and client registry for the helpdesk |
| `noc_helpdesk` | Core NOC helpdesk: ticket workflows, on-call scheduling, shift management |
| `noc_helpdesk_dashboard` | Analytics dashboard, occupancy tracking, and monthly network reports (PPTX/PDF) |
| `noc_helpdesk_graphics` | Link latency chart embedded in the ticket form |
| `noc_helpdesk_inventory` | Network equipment, sites, VLANs, and circuit inventory |
| `noc_network_monitor` | Automatic ticket creation from network monitoring alerts via external API |
| `noc_network_topology` | Interactive topology map and geographic site map (Leaflet/Cytoscape) |
| `noc_user_activity` | Auto-logout on inactivity + user session activity reports |
| `noc_user_notes` | Private per-user notes/drafts within the helpdesk |
| `theme_noc` | Custom brand color theme (replaces Odoo's default purple) |

---

## Module Dependency Graph

```
noc_base  ──────────────────────────────────────────────────────────┐
  │                                                                  │
  ├── noc_helpdesk ──────────────────────────────────┐              │
  │     ├── noc_helpdesk_inventory                   │              │
  │     ├── noc_helpdesk_dashboard ◄── noc_helpdesk  │              │
  │     ├── noc_helpdesk_graphics  ◄── noc_helpdesk  │              │
  │     └── noc_contacts                             │              │
  │                                                  │              │
  ├── noc_network_monitor ◄── noc_helpdesk_inventory─┘              │
  ├── noc_network_topology ◄── noc_helpdesk_inventory               │
  ├── noc_user_activity ◄── noc_contacts                            │
  ├── noc_user_notes ◄── noc_contacts                               │
  └── theme_noc                                                     │
```

**External dependencies (OCA):**
- `helpdesk_mgmt` — base helpdesk (tickets, teams, stages)
- `contacts` — Odoo contacts
- `document_page`, `document_page_access_group` — wiki/knowledge base
- `web_company_color` — company branding support

---

## Key Features

### Helpdesk (noc_helpdesk)
- NOC-specific ticket fields: link designation, latency, packet loss, upstream ISP
- On-call shift schedule (`helpdesk.plantao`) with full/light week rotation
- Vacation management with automatic shift coverage
- Ticket escalation and severity tracking
- Brazilian Portuguese translations included (`i18n/pt_BR.po`)

### Network Inventory (noc_helpdesk_inventory)
- Models: `network.equipment`, `network.site`, `network.circuit`, `network.circuit.type`, `network.vlan`
- Linked directly to helpdesk tickets
- Portal view for clients to check their circuits

### Network Monitoring (noc_network_monitor)
- REST API endpoint that accepts alerts from external monitoring tools (Zabbix, Nagios, etc.)
- Automatically opens/updates helpdesk tickets from alerts
- Scheduled polling with configurable intervals

### Network Topology (noc_network_topology)
- Interactive topology graph (Cytoscape.js) showing equipment and circuit connections
- Geographic site map (Leaflet.js) with marker clustering
- Automatic geocoding via Nominatim (OpenStreetMap) — configurable via Settings

### Dashboard (noc_helpdesk_dashboard)
- Real-time ticket and network event charts (Chart.js)
- Activity occupancy tracker: compare planned vs. actual NOC team activity by category
- Monthly Network Report: generate PDF and PPTX reports with SLA metrics and trend analysis

### User Activity (noc_user_activity)
- Automatic session logout after configurable inactivity timeout
- Warning dialog before logout
- Admin view of active sessions and session history

---

## Installation

### Requirements
- Odoo 16.0 Community or Enterprise
- OCA `helpdesk` module: `helpdesk_mgmt`
- OCA `server-tools` for migration helpers (optional)

### Steps

1. Clone this repository into your Odoo addons path:
   ```bash
   git clone https://github.com/your-username/noc-helpdesk-odoo.git /odoo/custom/src/noc
   ```

2. Add the path to your `odoo.conf`:
   ```ini
   addons_path = /odoo/addons,/odoo/custom/src/noc
   ```

3. Restart Odoo and install `noc_base` from the Apps menu (it will install all modules).

---

## Configuration

After installation, go to **Settings → NOC** to configure:

| Setting | Description |
|---|---|
| Geocoding Service URL | Nominatim endpoint (default: OpenStreetMap) |
| Contact E-mail (User-Agent) | Required by Nominatim ToS |
| Country Codes | ISO 3166-1 codes to restrict geocoding (leave blank for global) |
| Inactivity Timeout | Minutes before auto-logout |
| Network Monitor API Token | Authentication token for the monitoring webhook |

---

## License

LGPL-3 — See individual module manifests.

## Author

Tanatielly Serafim
