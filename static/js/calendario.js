document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") lucide.createIcons();

    const menuToggle = document.getElementById("menuToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const dayModal = document.getElementById("dayModal");
    const modalTitle = document.getElementById("dayModalTitle");
    const modalContent = document.getElementById("dayModalContent");
    const tooltip = document.getElementById("calendarTooltip");
    const statusFilters = [...document.querySelectorAll(".status-filter")];
    const allFilter = document.getElementById("filterAll");
    const calendarEvents = JSON.parse(document.getElementById("calendarData")?.textContent || "[]");
    const eventsById = new Map(calendarEvents.map((event) => [String(event.id), event]));

    const escapeHtml = (value) => String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

    const setSidebarOpen = (open) => {
        document.body.classList.toggle("sidebar-open", open);
        menuToggle?.setAttribute("aria-expanded", String(open));
    };

    menuToggle?.addEventListener("click", () => setSidebarOpen(!document.body.classList.contains("sidebar-open")));
    sidebarOverlay?.addEventListener("click", () => setSidebarOpen(false));
    document.querySelectorAll(".sidebar-nav a").forEach((link) => link.addEventListener("click", () => setSidebarOpen(false)));

    const locatePerson = (name) => {
        const target = [...document.querySelectorAll("#lista-ferias tbody tr[data-person]")]
            .find((row) => row.dataset.person === name && !row.hidden);
        if (!target) return;
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("calendar-highlight");
        window.setTimeout(() => target.classList.remove("calendar-highlight"), 1800);
    };
    document.querySelectorAll(".agenda-item[data-person]").forEach((item) => {
        item.addEventListener("click", () => locatePerson(item.dataset.person));
    });

    const selectedStatuses = () => new Set(
        statusFilters.filter((input) => input.checked).map((input) => input.value)
    );
    const eventsForDay = (day) => (
        (day.dataset.eventIds || "")
            .split(",")
            .filter(Boolean)
            .map((id) => eventsById.get(id))
            .filter(Boolean)
    );

    const renderDay = (day, selected) => {
        const container = day.querySelector(".day-events");
        const more = container.querySelector(".more-events");
        container.querySelectorAll(".calendar-event").forEach((event) => event.remove());
        const visible = eventsForDay(day).filter((event) => selected.has(event.status_classe));

        visible.slice(0, 2).forEach((event) => {
            more.insertAdjacentHTML("beforebegin", `
                <button class="calendar-event event-color-${event.cor} status-${escapeHtml(event.status_classe)}" type="button"
                    data-person="${escapeHtml(event.nome)}"
                    data-start="${escapeHtml(event.inicio)}"
                    data-end="${escapeHtml(event.fim)}"
                    data-block="${escapeHtml(event.bloqueio)}"
                    data-department="${escapeHtml(event.departamento)}"
                    data-status="${escapeHtml(event.status)}"
                    data-status-class="${escapeHtml(event.status_classe)}"
                    aria-describedby="calendarTooltip">
                    <span class="event-name">${escapeHtml(event.nome)}</span>
                </button>`);
        });

        const extra = Math.max(0, visible.length - 2);
        more.hidden = extra === 0;
        more.textContent = `+${extra} pessoa(s)`;
    };

    const applyFilters = () => {
        const selected = selectedStatuses();
        allFilter.checked = statusFilters.every((input) => input.checked);
        document.querySelectorAll(".calendar-day").forEach((day) => renderDay(day, selected));
        document.querySelectorAll(".agenda-item[data-status], #lista-ferias tbody tr[data-status]").forEach((item) => {
            item.hidden = !selected.has(item.dataset.status);
        });
    };

    allFilter?.addEventListener("change", () => {
        statusFilters.forEach((input) => { input.checked = allFilter.checked; });
        applyFilters();
    });
    statusFilters.forEach((input) => input.addEventListener("change", applyFilters));
    applyFilters();
    const initialPerson = document.body.dataset.searchPerson;
    if (initialPerson) window.setTimeout(() => locatePerson(initialPerson), 120);

    const openDayModal = (day) => {
        const selected = selectedStatuses();
        const events = eventsForDay(day).filter((event) => selected.has(event.status_classe));
        modalTitle.textContent = `📅 ${day.dataset.date}`;

        if (!events.length) {
            modalContent.innerHTML = `<div class="modal-empty"><i data-lucide="calendar-x"></i><strong>Nenhum colaborador</strong><span>Não há férias com os filtros selecionados neste dia.</span></div>`;
        } else {
            modalContent.innerHTML = events.map((event) => `
                <article class="modal-person">
                    <div class="modal-person-heading">
                        <strong>${escapeHtml(event.nome)}</strong>
                        <a href="/colaboradores/${encodeURIComponent(event.nome)}">Ver perfil</a>
                    </div>
                    <div class="modal-person-grid">
                        <div><span>Início</span><strong>${escapeHtml(event.inicio)}</strong></div>
                        <div><span>Fim</span><strong>${escapeHtml(event.fim)}</strong></div>
                        <div><span>Bloqueio</span><strong>${escapeHtml(event.bloqueio)}</strong></div>
                        <div><span>Departamento</span><strong>${escapeHtml(event.departamento)}</strong></div>
                        <div><span>Status</span><strong class="modal-status status-${escapeHtml(event.status_classe)}">${escapeHtml(event.status)}</strong></div>
                    </div>
                </article>
            `).join("");
        }
        if (typeof lucide !== "undefined") lucide.createIcons();
        dayModal.showModal();
    };

    document.querySelectorAll(".calendar-day").forEach((day) => {
        day.addEventListener("click", () => openDayModal(day));
        day.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openDayModal(day);
            }
        });
    });
    document.getElementById("closeDayModal")?.addEventListener("click", () => dayModal.close());
    dayModal?.addEventListener("click", (event) => {
        if (event.target === dayModal) dayModal.close();
    });

    const showTooltip = (event) => {
        tooltip.innerHTML = `
            <strong>${escapeHtml(event.dataset.person)}</strong>
            <div class="tooltip-grid">
                <span>Início</span><b>${escapeHtml(event.dataset.start)}</b>
                <span>Fim</span><b>${escapeHtml(event.dataset.end)}</b>
                <span>Departamento</span><b>${escapeHtml(event.dataset.department)}</b>
                <span>Status</span><b>${escapeHtml(event.dataset.status)}</b>
            </div>`;
        tooltip.hidden = false;
        const rect = event.getBoundingClientRect();
        tooltip.style.left = `${Math.min(window.innerWidth - 252, Math.max(10, rect.left + rect.width / 2 - 120))}px`;
        tooltip.style.top = `${rect.top > 180 ? rect.top - tooltip.offsetHeight - 9 : rect.bottom + 9}px`;
    };
    const hideTooltip = () => { tooltip.hidden = true; };

    document.addEventListener("mouseover", (event) => {
        const target = event.target.closest?.(".calendar-event");
        if (target && !target.contains(event.relatedTarget)) showTooltip(target);
    });
    document.addEventListener("mouseout", (event) => {
        const target = event.target.closest?.(".calendar-event");
        if (target && !target.contains(event.relatedTarget)) hideTooltip();
    });
    document.addEventListener("focusin", (event) => {
        const target = event.target.closest?.(".calendar-event");
        if (target) showTooltip(target);
    });
    document.addEventListener("focusout", (event) => {
        if (event.target.closest?.(".calendar-event")) hideTooltip();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        if (dayModal?.open) dayModal.close();
        else setSidebarOpen(false);
        hideTooltip();
    });
});
