{
    "name": "NOC Network Topology",
    "version": "16.0.1.1.0",
    "summary": "Graphical visualization of network equipment and circuits",
    "category": "Helpdesk",
    "author": "Tanatielly Serafim",
    "license": "LGPL-3",
    "depends": ["noc_helpdesk_inventory"],
    "data": [
        "views/network_equipment_views.xml",
        "views/network_site_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Apenas os componentes OWL entram no bundle global.
            # Leaflet e Cytoscape são carregados sob demanda (lazy) diretamente
            # pelos componentes via loadJS/loadCSS, para não inflar o bundle
            # de todas as páginas do backend.
            "noc_network_topology/static/src/xml/network_topology.xml",
            "noc_network_topology/static/src/xml/site_map.xml",
            "noc_network_topology/static/src/components/network_topology.js",
            "noc_network_topology/static/src/components/site_map.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
