/* @odoo-module */

import {attr} from "@mail/model/model_field";
import {clear} from "@mail/model/model_field_command";
import {registerPatch} from "@mail/model/model_core";
import {session} from "@web/session";

registerPatch({
    name: "Message",
    fields: {
        canBeEdited: attr({
            compute() {
                if (!session.is_admin && !this.isCurrentUserOrGuestAuthor) {
                    return false;
                }
                if (!this.originThread) {
                    return false;
                }
                if (this.trackingValues.length > 0) {
                    return false;
                }
                if (this.message_type !== "comment") {
                    return false;
                }
                return true;
            },
        }),
    },
});

registerPatch({
    name: "MessageView",
    fields: {
        dateFromNow: {
            compute() {
                if (!this.message) {
                    return clear();
                }
                if (!this.message.date) {
                    return clear();
                }
                return this.message.date.format("DD/MM/YYYY HH:mm");
            },
        },
    },
});

registerPatch({
    name: "MessageActionList",
    fields: {
        actionEdit: {
            compute() {
                if (this.message && this.message.canBeEdited) {
                    return {};
                }
                return clear();
            },
        },
    },
});
