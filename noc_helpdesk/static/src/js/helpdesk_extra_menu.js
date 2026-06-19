/* @odoo-module */

import {onMounted} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {ListController} from "@web/views/list/list_controller";

// Captura o setup original ANTES de aplicar o patch para evitar
// problemas com super em object literals (sem [[HomeObject]] correto).
const _originalListControllerSetup = ListController.prototype.setup;

patch(ListController.prototype, "noc_helpdesk.filters", {
    setup() {
        _originalListControllerSetup.call(this);
        if (this.props.resModel === "helpdesk.ticket") {
            onMounted(async () => {
                const anyActive =
                    this.env.searchModel.getDomainPart("noc_helpdesk_open") ||
                    this.env.searchModel.getDomainPart("noc_helpdesk_closed") ||
                    this.env.searchModel.getDomainPart("noc_helpdesk_high_latency") ||
                    this.env.searchModel.getDomainPart("noc_helpdesk_unavailable") ||
                    this.env.searchModel.getDomainPart(
                        "noc_helpdesk_discarded_packet"
                    ) ||
                    this.env.searchModel.getDomainPart("noc_helpdesk_mine");
                if (!anyActive) {
                    const activeFilter = this.props.context?.helpdesk_active_filter;
                    if (activeFilter === "open") {
                        await this.filterOpen();
                    } else if (activeFilter === "closed") {
                        await this.filterClosed();
                    } else if (activeFilter === "high_latency") {
                        await this.filterHighLatency();
                    } else if (activeFilter === "unavailable") {
                        await this.filterUnavailable();
                    } else if (activeFilter === "discarded_packet") {
                        await this.filterDiscardedPacket();
                    } else if (activeFilter === "mine") {
                        await this.filterMine();
                    }
                }
            });
        }
    },
    isFilterActive(key) {
        const open = this.env.searchModel.getDomainPart("noc_helpdesk_open");
        const closed = this.env.searchModel.getDomainPart("noc_helpdesk_closed");
        const highLatency = this.env.searchModel.getDomainPart(
            "noc_helpdesk_high_latency"
        );
        const unavailable = this.env.searchModel.getDomainPart(
            "noc_helpdesk_unavailable"
        );
        const discardedPacket = this.env.searchModel.getDomainPart(
            "noc_helpdesk_discarded_packet"
        );
        const mine = this.env.searchModel.getDomainPart("noc_helpdesk_mine");
        if (key === "all") {
            return (
                !open &&
                !closed &&
                !highLatency &&
                !unavailable &&
                !discardedPacket &&
                !mine
            );
        }
        if (key === "open") {
            return Boolean(open);
        }
        if (key === "closed") {
            return Boolean(closed);
        }
        if (key === "high_latency") {
            return Boolean(highLatency);
        }
        if (key === "unavailable") {
            return Boolean(unavailable);
        }
        if (key === "discarded_packet") {
            return Boolean(discardedPacket);
        }
        if (key === "mine") {
            return Boolean(mine);
        }
        return false;
    },
    _clearFilters() {
        this.env.searchModel.setDomainParts({
            noc_helpdesk_open: null,
            noc_helpdesk_closed: null,
            noc_helpdesk_high_latency: null,
            noc_helpdesk_unavailable: null,
            noc_helpdesk_discarded_packet: null,
            noc_helpdesk_mine: null,
        });
    },
    async _getModelDataResId(xmlid, modelName) {
        const orm =
            this.orm || (this.env && this.env.services && this.env.services.orm);
        if (!orm) {
            return null;
        }
        if (!this._listTabsModelDataCache) {
            this._listTabsModelDataCache = {};
        }
        const cacheKey = `${modelName}:${xmlid}`;
        if (!(cacheKey in this._listTabsModelDataCache)) {
            const [module, name] = xmlid.split(".");
            if (!module || !name) {
                this._listTabsModelDataCache[cacheKey] = null;
            } else {
                const records = await orm.searchRead(
                    "ir.model.data",
                    [
                        ["module", "=", module],
                        ["name", "=", name],
                        ["model", "=", modelName],
                    ],
                    ["res_id"],
                    {limit: 1}
                );
                this._listTabsModelDataCache[cacheKey] = records.length
                    ? records[0].res_id
                    : null;
            }
        }
        return this._listTabsModelDataCache[cacheKey];
    },
    async _getTagId(xmlid, name) {
        const orm =
            this.orm || (this.env && this.env.services && this.env.services.orm);
        if (!orm) {
            return null;
        }
        const tagId = await this._getModelDataResId(xmlid, "helpdesk.ticket.tag");
        if (tagId) {
            return tagId;
        }
        const records = await orm.searchRead(
            "helpdesk.ticket.tag",
            [["name", "=", name]],
            ["id"],
            {limit: 1}
        );
        return records.length ? records[0].id : null;
    },
    _toggleFilter(key, domain, exclusiveKeys = []) {
        const current = this.env.searchModel.getDomainPart(key);
        const parts = {
            [key]: current ? null : {domain},
        };
        if (!current && exclusiveKeys.length) {
            for (const otherKey of exclusiveKeys) {
                parts[otherKey] = null;
            }
        }
        this.env.searchModel.setDomainParts(parts);
    },
    async filterAll() {
        if (this.model.root.editedRecord) {
            const saved = await this.model.root.editedRecord.save();
            if (!saved) {
                return;
            }
        }
        this._clearFilters();
    },
    async filterOpen() {
        if (this.model.root.editedRecord) {
            const saved = await this.model.root.editedRecord.save();
            if (!saved) {
                return;
            }
        }

        const domain = [["stage_id.closed", "=", false]];
        this._toggleFilter("noc_helpdesk_open", domain, ["noc_helpdesk_closed"]);
    },
    async filterHighLatency() {
        if (this.model.root.editedRecord) {
            const saved = await this.model.root.editedRecord.save();
            if (!saved) {
                return;
            }
        }
        const tagId = await this._getTagId(
            "noc_helpdesk.helpdesk_ticket_tag_high_latency",
            "Alta Latência"
        );
        if (!tagId) {
            return;
        }
        const domain = [["tag_id", "in", [tagId]]];
        this._toggleFilter("noc_helpdesk_high_latency", domain, [
            "noc_helpdesk_unavailable",
            "noc_helpdesk_discarded_packet",
        ]);
    },
    async filterUnavailable() {
        if (this.model.root.editedRecord) {
            const saved = await this.model.root.editedRecord.save();
            if (!saved) {
                return;
            }
        }
        const tagId = await this._getTagId(
            "noc_helpdesk.helpdesk_ticket_tag_unavailable",
            "Indisponível"
        );
        if (!tagId) {
            return;
        }
        const domain = [["tag_id", "in", [tagId]]];
        this._toggleFilter("noc_helpdesk_unavailable", domain, [
            "noc_helpdesk_high_latency",
            "noc_helpdesk_discarded_packet",
        ]);
    },
    async filterDiscardedPacket() {
        if (this.model.root.editedRecord) {
            const saved = await this.model.root.editedRecord.save();
            if (!saved) {
                return;
            }
        }
        const tagId = await this._getTagId(
            "noc_helpdesk.helpdesk_ticket_tag_discarded_packet",
            "Descarte de Pacote"
        );
        if (!tagId) {
            return;
        }
        const domain = [["tag_id", "in", [tagId]]];
        this._toggleFilter("noc_helpdesk_discarded_packet", domain, [
            "noc_helpdesk_high_latency",
            "noc_helpdesk_unavailable",
        ]);
    },
    async filterClosed() {
        if (this.model.root.editedRecord) {
            const saved = await this.model.root.editedRecord.save();
            if (!saved) {
                return;
            }
        }

        const domain = [["stage_id.closed", "=", true]];
        this._toggleFilter("noc_helpdesk_closed", domain, ["noc_helpdesk_open"]);
    },
    async filterMine() {
        if (this.model.root.editedRecord) {
            const saved = await this.model.root.editedRecord.save();
            if (!saved) {
                return;
            }
        }

        const userId = this.userService.userId;
        if (!userId) {
            return;
        }

        const domain = [["create_uid", "=", userId]];
        this._toggleFilter("noc_helpdesk_mine", domain);
    },
});
