/* @odoo-module */

import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {onMounted} from "@odoo/owl";
import {registry} from "@web/core/registry";

// ─── Shared helpers ───────────────────────────────────────────────────────────

function normalizeTickets(payload) {
    const sourceTickets =
        payload?.tickets && payload.tickets.length
            ? payload.tickets
            : payload?.ticket_id
            ? [
                  {
                      ticket_id: payload.ticket_id,
                      ticket_name: payload.ticket_name,
                      alert_key: payload.alert_key,
                  },
              ]
            : [];

    return sourceTickets
        .filter((ticket) => Number.isInteger(ticket?.ticket_id) && ticket.ticket_id > 0)
        .map((ticket) => ({
            ticket_id: ticket.ticket_id,
            ticket_name: ticket.ticket_name || `Ticket #${ticket.ticket_id}`,
            alert_key: ticket.alert_key,
        }));
}

// ─── Cross-tab dismissed tickets ─────────────────────────────────────────────

const DISMISSED_TICKETS_KEY = "noc_helpdesk_dismissed_tickets";
const DISMISSED_TTL_MS = 5 * 60 * 1000;

function getDismissedTicketIds() {
    try {
        const entries = JSON.parse(localStorage.getItem(DISMISSED_TICKETS_KEY) || "[]");
        const cutoff = Date.now() - DISMISSED_TTL_MS;
        return new Set(entries.filter(([, ts]) => ts > cutoff).map(([id]) => id));
    } catch {
        return new Set();
    }
}

function dismissTicket(ticketId) {
    try {
        const entries = JSON.parse(localStorage.getItem(DISMISSED_TICKETS_KEY) || "[]");
        const cutoff = Date.now() - DISMISSED_TTL_MS;
        const fresh = entries.filter(([, ts]) => ts > cutoff);
        fresh.push([ticketId, Date.now()]);
        localStorage.setItem(DISMISSED_TICKETS_KEY, JSON.stringify(fresh));
    } catch {
        /* Sem acesso ao localStorage, ignora */
    }
}

// ─── Inactivity alert ─────────────────────────────────────────────────────────

class InactivityBlockingDialog extends ConfirmationDialog {
    setup() {
        super.setup();
        this.env.dialogData.close = () => {
            // Intentionally empty
        };
        onMounted(() => {
            const modalElement = this.modalRef.el;
            modalElement?.classList.add("o_list_tabs_chaos_dialog");
            const closeButton = modalElement?.querySelector(".btn-close");
            if (closeButton) {
                closeButton.remove();
            }
            const footer = modalElement?.querySelector(".modal-footer");
            if (footer) {
                footer.remove();
            }
            const bodyParagraph = modalElement?.querySelector(".modal-body p");
            if (!bodyParagraph) {
                return;
            }
            bodyParagraph.textContent = "";

            const intro = document.createElement("div");
            intro.className = "mb-3";
            intro.textContent =
                this.props.body ||
                "Tickets sem alteração detectados. Clique no ticket para abrir.";
            bodyParagraph.append(intro);

            const tickets = this.props.tickets || [];
            for (const ticket of tickets) {
                const ticketLink = document.createElement("a");
                ticketLink.href = "#";
                ticketLink.className = "o_ticket_alert_button d-block mb-2";
                ticketLink.textContent =
                    ticket.ticket_name || `Ticket #${ticket.ticket_id}`;
                ticketLink.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    if (this.props.openTicket) {
                        this.props.openTicket(ticket.ticket_id);
                        this.props.close();
                    }
                });
                bodyParagraph.append(ticketLink);
            }
        });
    }
}
InactivityBlockingDialog.props = {
    ...ConfirmationDialog.props,
    tickets: {type: Array, optional: true},
    openTicket: {type: Function, optional: true},
};

const GLOBAL_ALERT_CLOSE_KEY = "_listTabsInactivityAlertClose_";

export const ticketInactivityAlertService = {
    dependencies: ["bus_service", "dialog", "orm"],
    start(env, {bus_service, dialog, orm}) {
        const openTicket = (ticketId) => {
            dismissTicket(ticketId);
            window.open(
                `/web#model=helpdesk.ticket&id=${ticketId}&view_type=form`,
                "_blank"
            );
        };

        const showAlert = (payload) => {
            const dismissed = getDismissedTicketIds();
            const receivedTickets = normalizeTickets(payload).filter(
                (t) => !dismissed.has(t.ticket_id)
            );
            if (!receivedTickets.length) {
                return;
            }
            const previousClose = window[GLOBAL_ALERT_CLOSE_KEY];
            if (typeof previousClose === "function") {
                previousClose();
            }
            const inactivityMinutes = payload?.inactivity_minutes || 30;
            const currentClose = dialog.add(
                InactivityBlockingDialog,
                {
                    title: env._t("Atenção! Tickets sem alterações"),
                    body: env._t(
                        `Os tickets abaixo ficaram ${inactivityMinutes} minutos sem alterações.\nCaso exista mais de um ticket na lista, você será notificado novamente em 5 minutos.`
                    ),
                    tickets: receivedTickets,
                    openTicket,
                },
                {
                    onClose: () => {
                        if (window[GLOBAL_ALERT_CLOSE_KEY] === currentClose) {
                            window[GLOBAL_ALERT_CLOSE_KEY] = null;
                        }
                    },
                }
            );
            window[GLOBAL_ALERT_CLOSE_KEY] = currentClose;
        };

        const onNotification = ({detail: notifications}) => {
            for (const {payload, type} of notifications) {
                if (type !== "noc_helpdesk/inactivity_alert") {
                    continue;
                }
                showAlert(payload);
            }
        };

        bus_service.addEventListener("notification", onNotification);
        bus_service.start();
        orm.call(
            "helpdesk.ticket",
            "get_inactivity_alert_payload_for_current_user",
            [],
            {}
        ).then((payload) => showAlert(payload));
    },
};

registry
    .category("services")
    .add("noc_helpdesk_ticket_inactivity_alert", ticketInactivityAlertService);

// ─── New ticket alert ─────────────────────────────────────────────────────────

class NewTicketBlockingDialog extends ConfirmationDialog {
    setup() {
        super.setup();
        this.env.dialogData.close = () => {
            // Intentionally empty
        };
        onMounted(() => {
            const modalElement = this.modalRef.el;
            modalElement?.classList.add("o_list_tabs_chaos_dialog");
            const closeButton = modalElement?.querySelector(".btn-close");
            if (closeButton) {
                closeButton.remove();
            }
            const footer = modalElement?.querySelector(".modal-footer");
            if (footer) {
                footer.remove();
            }
            const bodyParagraph = modalElement?.querySelector(".modal-body p");
            if (!bodyParagraph) {
                return;
            }
            bodyParagraph.textContent = "";

            const intro = document.createElement("div");
            intro.className = "mb-3";
            intro.textContent =
                this.props.body ||
                "Novos tickets detectados. Clique no ticket para abrir.";
            bodyParagraph.append(intro);

            const tickets = this.props.tickets || [];
            for (const ticket of tickets) {
                const ticketLink = document.createElement("a");
                ticketLink.href = "#";
                ticketLink.className = "o_ticket_alert_button d-block mb-2";
                ticketLink.textContent =
                    ticket.ticket_name || `Ticket #${ticket.ticket_id}`;
                ticketLink.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    if (this.props.openTicket) {
                        this.props.openTicket(ticket.ticket_id);
                        this.props.close();
                    }
                });
                bodyParagraph.append(ticketLink);
            }
        });
    }
}
NewTicketBlockingDialog.props = {
    ...ConfirmationDialog.props,
    tickets: {type: Array, optional: true},
    openTicket: {type: Function, optional: true},
};

const NEW_TICKET_GLOBAL_ALERT_CLOSE_KEY = "_listTabsNewTicketAlertClose_";

export const ticketNewAlertService = {
    dependencies: ["bus_service", "dialog", "orm"],
    start(env, {bus_service, dialog, orm}) {
        const openTicket = (ticketId) => {
            dismissTicket(ticketId);
            window.open(
                `/web#model=helpdesk.ticket&id=${ticketId}&view_type=form`,
                "_blank"
            );
        };

        const showAlert = (payload) => {
            const dismissed = getDismissedTicketIds();
            const receivedTickets = normalizeTickets(payload).filter(
                (t) => !dismissed.has(t.ticket_id)
            );
            if (!receivedTickets.length) {
                return;
            }
            const previousClose = window[NEW_TICKET_GLOBAL_ALERT_CLOSE_KEY];
            if (typeof previousClose === "function") {
                previousClose();
            }
            const checkIntervalMinutes = payload?.check_interval_minutes || 5;
            const currentClose = dialog.add(
                NewTicketBlockingDialog,
                {
                    title: env._t("Atenção! Novos tickets"),
                    body: env._t(
                        `Os tickets abaixo foram criados nos últimos ${checkIntervalMinutes} minutos e ainda não possuem responsável.\nCaso exista mais de um ticket na lista, você será notificado novamente em breve.`
                    ),
                    tickets: receivedTickets,
                    openTicket,
                },
                {
                    onClose: () => {
                        if (
                            window[NEW_TICKET_GLOBAL_ALERT_CLOSE_KEY] === currentClose
                        ) {
                            window[NEW_TICKET_GLOBAL_ALERT_CLOSE_KEY] = null;
                        }
                    },
                }
            );
            window[NEW_TICKET_GLOBAL_ALERT_CLOSE_KEY] = currentClose;
        };

        const onNotification = ({detail: notifications}) => {
            for (const {payload, type} of notifications) {
                if (type !== "noc_helpdesk/new_ticket_alert") {
                    continue;
                }
                showAlert(payload);
            }
        };

        bus_service.addEventListener("notification", onNotification);
        bus_service.start();
        orm.call(
            "helpdesk.ticket",
            "get_new_tickets_alert_payload_for_current_user",
            [],
            {}
        ).then((payload) => showAlert(payload));
    },
};

registry
    .category("services")
    .add("noc_helpdesk_ticket_new_alert", ticketNewAlertService);

// ─── Activity start alert ──────────────────────────────────────────────────────

export const activityStartAlertService = {
    dependencies: ["action", "bus_service", "notification"],
    start(env, {action, bus_service, notification}) {
        const showAlert = (payload) => {
            const summary = payload?.activity_summary || "Atividade";
            const resName = payload?.res_name;
            const resModel = payload?.res_model;
            const resId = payload?.res_id;

            const message = resName ? `${summary} — ${resName}` : summary;

            notification.add(message, {
                title: env._t("Hora de iniciar a atividade!"),
                type: "warning",
                sticky: true,
                buttons:
                    resModel && resId
                        ? [
                              {
                                  name: env._t("Abrir"),
                                  primary: true,
                                  onClick: async () => {
                                      await action.doAction({
                                          type: "ir.actions.act_window",
                                          res_model: resModel,
                                          res_id: resId,
                                          views: [[false, "form"]],
                                          view_mode: "form",
                                          target: "current",
                                      });
                                  },
                              },
                          ]
                        : [],
            });
        };

        const onNotification = ({detail: notifications}) => {
            for (const {payload, type} of notifications) {
                if (type !== "noc_helpdesk/activity_start_alert") {
                    continue;
                }
                showAlert(payload);
            }
        };

        bus_service.addEventListener("notification", onNotification);
        bus_service.start();
    },
};

registry
    .category("services")
    .add("noc_helpdesk_activity_start_alert", activityStartAlertService);

// ─── Manutenção Programada Informativa alert ───────────────────────────────────

export const manutencaoProgramadaAlertService = {
    dependencies: ["action", "bus_service", "notification"],
    start(env, {action, bus_service, notification}) {
        const showAlert = (payload) => {
            const ticketName = payload?.ticket_name || `Ticket #${payload?.ticket_id}`;
            const ticketId = payload?.ticket_id;
            const isStart = payload?.event === "start";

            const title = isStart
                ? env._t("Manutenção Programada — INÍCIO")
                : env._t("Manutenção Programada — FIM");
            const message = isStart
                ? env._t(`Iniciando manutenção: ${ticketName}`)
                : env._t(`Encerrando manutenção: ${ticketName}`);

            notification.add(message, {
                title,
                type: "warning",
                sticky: true,
                buttons: ticketId
                    ? [
                          {
                              name: env._t("Abrir"),
                              primary: true,
                              onClick: async () => {
                                  await action.doAction({
                                      type: "ir.actions.act_window",
                                      res_model: "helpdesk.ticket",
                                      res_id: ticketId,
                                      views: [[false, "form"]],
                                      view_mode: "form",
                                      target: "current",
                                  });
                              },
                          },
                      ]
                    : [],
            });
        };

        const onNotification = ({detail: notifications}) => {
            for (const {payload, type} of notifications) {
                if (type !== "noc_helpdesk/manutencao_alert") {
                    continue;
                }
                showAlert(payload);
            }
        };

        bus_service.addEventListener("notification", onNotification);
        bus_service.start();
    },
};

registry
    .category("services")
    .add(
        "noc_helpdesk_manutencao_programada_alert",
        manutencaoProgramadaAlertService
    );

// ─── Plantão alert ────────────────────────────────────────────────────────────

const PLANTAO_GLOBAL_ALERT_CLOSE_KEY = "_plantaoAlertClose_";

export const plantaoAlertService = {
    dependencies: ["bus_service", "dialog", "notification", "orm"],
    start(env, {bus_service, dialog, notification, orm}) {
        const showPlantaoDialog = () => {
            const prev = window[PLANTAO_GLOBAL_ALERT_CLOSE_KEY];
            if (typeof prev === "function") prev();

            const currentClose = dialog.add(
                ConfirmationDialog,
                {
                    title: env._t("Assumir Plantão"),
                    body: env._t(
                        "Deseja assumir o plantão agora? Todos os chamados abertos serão atribuídos a você."
                    ),
                    confirmLabel: env._t("Assumir Plantão"),
                    confirm: async () => {
                        await orm.call("helpdesk.ticket", "action_assumir_plantao", []);
                        notification.add(env._t("Plantão assumido com sucesso!"), {
                            type: "success",
                        });
                    },
                    cancel: () => {
                        /* Noop */
                    },
                },
                {
                    onClose: () => {
                        if (window[PLANTAO_GLOBAL_ALERT_CLOSE_KEY] === currentClose) {
                            window[PLANTAO_GLOBAL_ALERT_CLOSE_KEY] = null;
                        }
                    },
                }
            );
            window[PLANTAO_GLOBAL_ALERT_CLOSE_KEY] = currentClose;
        };

        const onNotification = ({detail: notifications}) => {
            for (const {payload, type} of notifications) {
                if (type === "noc_helpdesk/plantao_alert") {
                    showPlantaoDialog();
                } else if (type === "noc_helpdesk/plantao_assumed") {
                    const close = window[PLANTAO_GLOBAL_ALERT_CLOSE_KEY];
                    if (typeof close === "function") {
                        close();
                        window[PLANTAO_GLOBAL_ALERT_CLOSE_KEY] = null;
                    }
                    notification.add(
                        env._t(`${payload.user_name} assumiu o plantão.`),
                        {type: "info"}
                    );
                }
            }
        };

        bus_service.addEventListener("notification", onNotification);
        bus_service.start();

        orm.call(
            "helpdesk.ticket",
            "get_plantao_shift_alert_for_current_user",
            []
        ).then((result) => {
            if (result?.show) showPlantaoDialog();
        });
    },
};

registry.category("services").add("noc_helpdesk_plantao_alert", plantaoAlertService);

// ─── Férias alert ─────────────────────────────────────────────────────────────

export const feriasAlertService = {
    dependencies: ["action", "bus_service", "notification"],
    start(env, {action, bus_service, notification}) {
        const onNotification = ({detail: notifications}) => {
            for (const {payload, type} of notifications) {
                if (type !== "noc_helpdesk/ferias_alert") {
                    continue;
                }
                const {ferias_id, employee_name, date_from, date_to, duration} =
                    payload;
                notification.add(
                    env._t(
                        `${employee_name} — ${date_from} a ${date_to} (${duration} dias)`
                    ),
                    {
                        title: env._t("Solicitação de Férias Aguardando Aprovação"),
                        type: "warning",
                        sticky: true,
                        buttons: [
                            {
                                name: env._t("Abrir"),
                                primary: true,
                                onClick: async () => {
                                    await action.doAction({
                                        type: "ir.actions.act_window",
                                        res_model: "helpdesk.ferias",
                                        res_id: ferias_id,
                                        views: [[false, "form"]],
                                        view_mode: "form",
                                        target: "current",
                                    });
                                },
                            },
                        ],
                    }
                );
            }
        };

        bus_service.addEventListener("notification", onNotification);
        bus_service.start();
    },
};

registry.category("services").add("noc_helpdesk_ferias_alert", feriasAlertService);
