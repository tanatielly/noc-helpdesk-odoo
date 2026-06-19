/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {ClientErrorDialog} from "@web/core/errors/error_dialogs";

patch(ClientErrorDialog.prototype, "noc_base.ClipboardHttpFallback", {
    async onClickClipboard() {
        const text = this.props.traceback;
        if (navigator.clipboard) {
            await navigator.clipboard.writeText(text);
        } else {
            // Fallback para contextos HTTP (sem navigator.clipboard)
            const textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            document.execCommand("copy");
            document.body.removeChild(textarea);
        }
    },
});
