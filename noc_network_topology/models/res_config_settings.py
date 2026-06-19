from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    noc_network_topology_nominatim_url = fields.Char(
        string="Geocoding Service URL",
        default="https://nominatim.openstreetmap.org/search",
        config_parameter="noc_network_topology.nominatim_url",
        help="Nominatim-compatible endpoint for address-to-coordinates conversion.",
    )
    noc_network_topology_contact_email = fields.Char(
        string="Contact E-mail (User-Agent)",
        config_parameter="noc_network_topology.contact_email",
        help=(
            "E-mail included in the User-Agent header of geocoding requests, "
            "as required by Nominatim terms of use."
        ),
    )
    noc_network_topology_country_codes = fields.Char(
        string="Country Codes (geocoding)",
        default="",
        config_parameter="noc_network_topology.country_codes",
        help=(
            "Comma-separated ISO 3166-1 alpha-2 codes to restrict geocoding search. "
            "Leave blank for global search."
        ),
    )
    noc_network_topology_geocoding_timeout = fields.Integer(
        string="Geocoding Timeout (s)",
        default=8,
        config_parameter="noc_network_topology.geocoding_timeout",
        help="Maximum seconds to wait for a geocoding service response. Default: 8.",
    )
    noc_network_topology_geocoding_rate_delay = fields.Float(
        string="Batch Request Interval (s)",
        default=1.1,
        config_parameter="noc_network_topology.geocoding_rate_delay",
        help=(
            "Seconds to wait between requests during batch geocoding, "
            "to respect the service rate limit. Default: 1.1."
        ),
    )