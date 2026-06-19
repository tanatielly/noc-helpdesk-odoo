/* @odoo-module */

import {ListRenderer} from "@web/views/list/list_renderer";
import {listView} from "@web/views/list/list_view";
import {registry} from "@web/core/registry";

// View genérica que adiciona suporte a Ctrl+Click (ou Cmd+Click no Mac)
// para abrir registros em nova aba a partir de qualquer lista.
// Uso: adicione js_class="ctrl_click_list" na tag <tree> desejada.

class CtrlClickListRenderer extends ListRenderer {
    async onCellClicked(record, column, ev) {
        if (
            (ev.ctrlKey || ev.metaKey) &&
            !this.props.archInfo.noOpen &&
            !this.isInlineEditable(record)
        ) {
            const hash = Object.fromEntries(
                new URLSearchParams(window.location.hash.slice(1))
            );
            hash.view_type = "form";
            hash.id = record.resId;
            window.open("/web#" + new URLSearchParams(hash).toString(), "_blank");
            return;
        }
        return super.onCellClicked(record, column, ev);
    }
}

registry.category("views").add("ctrl_click_list", {
    ...listView,
    Renderer: CtrlClickListRenderer,
});
