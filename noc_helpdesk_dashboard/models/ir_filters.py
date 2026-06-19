from odoo import api, models


class IrFilters(models.Model):
    _inherit = "ir.filters"

    @api.model
    def get_filters(self, model, action_id=None):
        # When navigating from the helpdesk dashboard with explicit domain,
        # suppress all default ir.filters to avoid overriding the given domain.
        if self.env.context.get("dashboard_no_default_filters"):
            return []
        return super().get_filters(model, action_id=action_id)
