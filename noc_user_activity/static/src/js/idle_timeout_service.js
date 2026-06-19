/* @odoo-module */

import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {registry} from "@web/core/registry";

const EVENTS = ["mousemove", "keydown", "mousedown", "touchstart", "scroll", "click"];
const LOGOUT_URL = "/web/session/logout?redirect=/web/login";
const HEARTBEAT_MS = 5 * 60 * 1000;

export const idleTimeoutService = {
    dependencies: ["dialog", "rpc"],
    async start(env, {dialog, rpc}) {
        let idleTimer = null;
        let warningTimer = null;
        let warningClose = null;
        let isActive = true;

        let timeoutMs = 30 * 60 * 1000;
        let warningMs = 28 * 60 * 1000;

        try {
            const cfg = await rpc("/noc_user_activity/get_settings", {});
            if (cfg && cfg.timeout_minutes > 0) {
                const warningMinutes = cfg.warning_minutes || 2;
                timeoutMs = cfg.timeout_minutes * 60 * 1000;
                warningMs = (cfg.timeout_minutes - warningMinutes) * 60 * 1000;
            }
        } catch {
            // Usa os valores padrão se o RPC falhar
        }

        const scheduleLogout = () => {
            clearTimeout(idleTimer);
            clearTimeout(warningTimer);

            warningTimer = setTimeout(() => {
                warningClose = dialog.add(ConfirmationDialog, {
                    title: env._t("Sessão Expirando"),
                    body: env._t(
                        "Você será desconectado em breve por inatividade. Clique em Continuar para permanecer conectado."
                    ),
                    confirmLabel: env._t("Continuar"),
                    confirm: () => {
                        warningClose = null;
                        isActive = true;
                        scheduleLogout();
                    },
                    cancelLabel: env._t("Sair agora"),
                    cancel: () => {
                        window.location.href = LOGOUT_URL;
                    },
                });
            }, warningMs);

            idleTimer = setTimeout(() => {
                if (warningClose) {
                    warningClose();
                    warningClose = null;
                }
                window.location.href = LOGOUT_URL;
            }, timeoutMs);
        };

        const onActivity = () => {
            isActive = true;
            scheduleLogout();
        };

        const sendHeartbeat = async () => {
            if (!isActive) {
                return;
            }
            isActive = false;
            try {
                await rpc("/noc_user_activity/heartbeat", {});
            } catch {
                // Ignora erros de rede ou sessão já encerrada
            }
        };

        for (const ev of EVENTS) {
            window.addEventListener(ev, onActivity, {passive: true});
        }

        scheduleLogout();
        sendHeartbeat();
        setInterval(sendHeartbeat, HEARTBEAT_MS);
    },
};

registry
    .category("services")
    .add("noc_user_activity_idle_timeout", idleTimeoutService);
