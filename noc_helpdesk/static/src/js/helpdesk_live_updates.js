/* @odoo-module */

import {KanbanController} from "@web/views/kanban/kanban_controller";
import {ListController} from "@web/views/list/list_controller";
import {ListRenderer} from "@web/views/list/list_renderer";
import {kanbanView} from "@web/views/kanban/kanban_view";
import {listView} from "@web/views/list/list_view";
import {registry} from "@web/core/registry";
import {useBus} from "@web/core/utils/hooks";

const RELOAD_DEBOUNCE_MS = 500;
const NOTIF_TYPE = "noc_helpdesk/ticket_update";

/**
 * Evento interno OWL disparado pelo serviço quando chega notificação do WebSocket.
 * Os controllers escutam este evento via useBus(env.bus, ...).
 * Usar um evento interno desacopla o WebSocket dos controllers.
 */
const OWL_BUS_EVENT = "noc_helpdesk:ticket_changed";

// ─── Serviço de escuta do WebSocket ──────────────────────────────────────────
//
// ARQUITETURA:
//   helpdesk_alerts.js usa o mesmo padrão — um serviço registrado UMA VEZ
//   que fica vivo para sempre. Isso é o correto para escutar o bus_service.
//
//   Colocar o addEventListener no controller (como antes) era problemático
//   porque o controller só existe enquanto a view está montada, e o OWL
//   pode não ter completado a subscrição ao canal do parceiro ainda.
//
//   O serviço:
//     1. Inicia junto com o Odoo, nunca desmonta
//     2. Escuta o WebSocket bus (bus_service)
//     3. Quando recebe noc_helpdesk/ticket_update, dispara OWL_BUS_EVENT
//        no env.bus (barramento global OWL — diferente do WebSocket bus)
//
//   Os controllers:
//     1. Escutam OWL_BUS_EVENT via useBus(env.bus, ...)
//     2. Fazem reload do modelo e forçam re-render

export const helpdeskLiveUpdateService = {
    dependencies: ["bus_service"],
    start(env, {bus_service}) {
        const onNotification = ({detail: notifications}) => {
            if (!Array.isArray(notifications)) return;
            for (const {type} of notifications) {
                if (type === NOTIF_TYPE) {
                    // Env.bus é o EventBus OWL global — qualquer componente
                    // que chamar useBus(env.bus, OWL_BUS_EVENT, cb) vai receber.
                    env.bus.trigger(OWL_BUS_EVENT);
                    break;
                }
            }
        };

        bus_service.addEventListener("notification", onNotification);
        bus_service.start();
    },
};

registry
    .category("services")
    .add("noc_helpdesk_live_update", helpdeskLiveUpdateService);

// ─── Hook de reload para controllers ─────────────────────────────────────────
//
// Deve ser chamado dentro do setup() do controller passando `this`.
//
// useBus() — hook do Odoo 16 (@web/core/utils/hooks):
//   - Registra o listener no onMounted
//   - Remove automaticamente no onWillUnmount
//   - Garante execução no contexto correto do componente OWL
//
// controller.render(true):
//   Padrão obrigatório no Odoo 16 após model.root.load().
//   O próprio Odoo faz isso em list_controller.js linha 159:
//     await list.load({ limit, offset });
//     this.render(true);  // FIXME WOWL reactivity
//   Sem render(true), o DOM não atualiza mesmo com dados novos no modelo.

function useHelpdeskLiveReload(controller) {
    let reloadTimer = null;

    const isEditing = () => {
        const root = controller.model?.root;
        if (!root) return false;
        // List view: linha em edição inline
        if (root.editedRecord) return true;
        // Kanban agrupado: quick-create fica em group.quickCreateRecord,
        // não em root diretamente
        if (root.groups?.some((g) => g.quickCreateRecord)) return true;
        return false;
    };

    const onTicketChanged = () => {
        clearTimeout(reloadTimer);
        reloadTimer = setTimeout(async () => {
            if (isEditing()) return;
            try {
                await controller.model.root.load();
                controller.render(true);
            } catch {
                // Controller desmontado ou erro de rede — ignora silenciosamente
            }
        }, RELOAD_DEBOUNCE_MS);
    };

    // UseBus registra/remove o listener seguindo o ciclo de vida OWL do controller.
    // env.bus aqui é o EventBus OWL global (não o WebSocket bus).
    useBus(controller.env.bus, OWL_BUS_EVENT, onTicketChanged);
}

// ─── List view ────────────────────────────────────────────────────────────────

class HelpdeskLiveListController extends ListController {
    setup() {
        super.setup();
        useHelpdeskLiveReload(this);
    }

    onClickCreate(ev) {
        if (ev.ctrlKey || ev.metaKey) {
            const hash = Object.fromEntries(
                new URLSearchParams(window.location.hash.slice(1))
            );
            hash.view_type = "form";
            delete hash.id;
            window.open("/web#" + new URLSearchParams(hash).toString(), "_blank");
            return;
        }
        this.createRecord();
    }
}

// Abre o chamado em nova aba quando Ctrl+Click (ou Cmd+Click no Mac)
class HelpdeskLiveListRenderer extends ListRenderer {
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

registry.category("views").add("helpdesk_live_list", {
    ...listView,
    Controller: HelpdeskLiveListController,
    Renderer: HelpdeskLiveListRenderer,
});

// ─── Kanban view ──────────────────────────────────────────────────────────────

class HelpdeskLiveKanbanController extends KanbanController {
    setup() {
        super.setup();
        useHelpdeskLiveReload(this);
    }
}

registry.category("views").add("helpdesk_live_kanban", {
    ...kanbanView,
    Controller: HelpdeskLiveKanbanController,
});
