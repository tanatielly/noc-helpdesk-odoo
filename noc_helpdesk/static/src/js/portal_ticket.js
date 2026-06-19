/**
 * NOC Helpdesk — Portal Ticket Form
 *
 * Handles:
 *  - Show/hide conditional sections based on the selected portal type
 *  - Show loopback/hostname fields when an ACS type is chosen
 *  - Intercept form submit for "Configuração de Rede" and display a
 *    Bootstrap 5 modal warning before actually submitting
 */
document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("nocHelpdeskForm");
    if (!form) return;

    // ── Element references ────────────────────────────────────────────
    const typeSelect = document.getElementById("portal_type_select");
    const typeHidden = document.getElementById("portal_type_hidden");
    const categoryHidden = document.getElementById("portal_category_hidden");

    const sectionNetworkConfig = document.getElementById("section_network_config");
    const sectionAcs = document.getElementById("section_acs");
    const sectionPassword = document.getElementById("section_password");

    const acsTypeSelect = document.getElementById("portal_acs_type");
    const acsExtraFields = document.getElementById("section_acs_fields");

    const modalEl = document.getElementById("networkConfigModal");
    const confirmBtn = document.getElementById("confirmNetworkConfig");

    // Category IDs injected by the Qweb template via data-* attributes
    const catMap = {
        network_config: form.dataset.catNetworkConfig || "0",
        acs: form.dataset.catAcs || "0",
        password: form.dataset.catPassword || "0",
    };

    // ── Helper: toggle section visibility ────────────────────────────
    function _setRequired(section, required) {
        if (!section) return;
        section.querySelectorAll("input, select, textarea").forEach(function (el) {
            // Only touch elements that carry our data-conditionally-required marker
            if (el.dataset.conditionallyRequired !== undefined || required === false) {
                el.required = required;
            }
        });
    }

    function hideAll() {
        [sectionNetworkConfig, sectionAcs, sectionPassword].forEach(function (el) {
            if (el) el.style.display = "none";
        });
        // Remove required constraints from hidden sections
        _setRequired(sectionNetworkConfig, false);
        _setRequired(sectionAcs, false);
        _setRequired(sectionPassword, false);
        if (acsExtraFields) acsExtraFields.style.display = "none";
    }

    function showSection(type) {
        hideAll();

        categoryHidden.value = catMap[type] || "0";
        typeHidden.value = type || "";

        if (type === "network_config" && sectionNetworkConfig) {
            sectionNetworkConfig.style.display = "";
        } else if (type === "acs" && sectionAcs) {
            sectionAcs.style.display = "";
        } else if (type === "password" && sectionPassword) {
            sectionPassword.style.display = "";
        }
    }

    // ── Portal type selector ──────────────────────────────────────────
    if (typeSelect) {
        typeSelect.addEventListener("change", function () {
            showSection(this.value);
        });
    }

    // ── ACS sub-type selector — show loopback/hostname ────────────────
    if (acsTypeSelect && acsExtraFields) {
        acsTypeSelect.addEventListener("change", function () {
            acsExtraFields.style.display = this.value ? "" : "none";
        });
    }

    // ── Network Config: intercept submit and show modal ───────────────
    let _confirmed = false;

    form.addEventListener("submit", function (e) {
        if (typeHidden.value === "network_config" && !_confirmed && modalEl) {
            e.preventDefault();
            // Bootstrap 5 — window.bootstrap should be available in portal
            const bsModal = new window.bootstrap.Modal(modalEl);
            bsModal.show();
        }
    });

    if (confirmBtn && modalEl) {
        confirmBtn.addEventListener("click", function () {
            _confirmed = true;
            const bsModal = window.bootstrap.Modal.getInstance(modalEl);
            if (bsModal) bsModal.hide();
            form.submit();
        });
    }

    // ── Initialise hidden state ───────────────────────────────────────
    hideAll();
});
