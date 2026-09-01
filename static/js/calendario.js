document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") lucide.createIcons();

    const menuToggle = document.getElementById("menuToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const drawer = document.getElementById("eventDrawer");
    const drawerBackdrop = document.getElementById("drawerBackdrop");
    const dayEventsModal = document.getElementById("dayEventsModal");
    const dayEventsBackdrop = document.getElementById("dayEventsBackdrop");
    const dayEventsList = document.getElementById("dayEventsList");
    const loader = document.getElementById("calendarLoader");
    const {
        partitionEvents,
        overflowLabel,
        eventTypeLabel,
        selectHiddenEvent
    } = window.CalendarOverflow;

    let activeWorkspace = null;
    let activeEvents = new Map();
    let lastDrawerTrigger = null;
    let lastDayEventsTrigger = null;

    const normalizeText = (value = "") => String(value)
        .trim()
        .toLocaleLowerCase("pt-BR")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");

    const escapeHtml = (value = "") => String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

    const parseBrazilianDate = (value) => {
        const [day, month, year] = String(value || "").split("/").map(Number);
        return day && month && year ? new Date(year, month - 1, day) : null;
    };

    const parseIsoDate = (value) => {
        const [year, month, day] = String(value || "").split("-").map(Number);
        return year && month && day ? new Date(year, month - 1, day) : null;
    };

    const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const addDays = (date, days) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
    const daysBetween = (start, end) => Math.round((startOfDay(end) - startOfDay(start)) / 86400000) + 1;
    const statusLabel = (event) => event.tipo === "retorno" ? "Retorno ao trabalho" : event.status;
    const navigationFeedback = window.FokusNavigationFeedback.create(window);

    const revealNavigationTarget = (workspace) => {
        if (new URLSearchParams(window.location.search).get("focus") !== "hoje") return;

        const target = workspace.querySelector(".calendar-day.today") || workspace.querySelector(".calendar-panel");
        if (!target) return;

        navigationFeedback.reveal(target, { className: "navigation-highlight", duration: 3200 });
    };

    const setSidebarOpen = (open) => {
        document.body.classList.toggle("sidebar-open", open);
        menuToggle?.setAttribute("aria-expanded", String(open));
    };

    menuToggle?.addEventListener("click", () => setSidebarOpen(!document.body.classList.contains("sidebar-open")));
    sidebarOverlay?.addEventListener("click", () => setSidebarOpen(false));
    document.querySelectorAll(".sidebar-nav a").forEach((link) => link.addEventListener("click", () => setSidebarOpen(false)));

    const fillDrawer = (event) => {
        const start = parseBrazilianDate(event.inicio);
        const end = parseBrazilianDate(event.fim);
        const initials = event.nome.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
        const status = document.getElementById("drawerStatus");

        document.getElementById("drawerPersonName").textContent = event.nome;
        document.getElementById("drawerProfileName").textContent = event.nome;
        document.getElementById("drawerProfileMeta").textContent = `${event.departamento} · ${event.filial || "Não informada"}`;
        document.getElementById("drawerAvatar").textContent = initials || "--";
        document.getElementById("drawerDepartment").textContent = event.departamento || "Não informado";
        document.getElementById("drawerBranch").textContent = event.filial || "Não informada";
        document.getElementById("drawerStart").textContent = event.inicio || "—";
        document.getElementById("drawerEnd").textContent = event.fim || "—";
        document.getElementById("drawerDays").textContent = start && end ? `${daysBetween(start, end)} dias` : "—";
        status.textContent = statusLabel(event);
        status.className = `status-pill status-${event.status_classe}`;
        document.getElementById("drawerProfileLink").href = `/colaboradores/${encodeURIComponent(event.nome)}`;
    };

    const openDrawer = (event, trigger = null) => {
        if (!event || !drawer) return;
        lastDrawerTrigger = trigger || document.activeElement;
        fillDrawer(event);
        drawerBackdrop.hidden = false;
        drawer.setAttribute("aria-hidden", "false");
        document.body.classList.add("drawer-open");
        window.requestAnimationFrame(() => {
            drawerBackdrop.classList.add("is-visible");
            drawer.classList.add("is-open");
            document.getElementById("closeEventDrawer")?.focus();
        });
    };

    const closeDrawer = () => {
        if (!drawer?.classList.contains("is-open")) return;
        drawer.classList.remove("is-open");
        drawerBackdrop.classList.remove("is-visible");
        drawer.setAttribute("aria-hidden", "true");
        document.body.classList.remove("drawer-open");
        window.setTimeout(() => { drawerBackdrop.hidden = true; }, 220);
        lastDrawerTrigger?.focus?.();
    };

    document.getElementById("closeEventDrawer")?.addEventListener("click", closeDrawer);
    drawerBackdrop?.addEventListener("click", closeDrawer);

    const closeDayEventsModal = (restoreFocus = true) => {
        if (!dayEventsModal || dayEventsModal.hidden) return;
        dayEventsModal.classList.remove("is-open");
        dayEventsBackdrop.classList.remove("is-visible");
        dayEventsModal.setAttribute("aria-hidden", "true");
        document.body.classList.remove("day-events-open");
        window.setTimeout(() => {
            dayEventsModal.hidden = true;
            dayEventsBackdrop.hidden = true;
        }, 180);
        if (restoreFocus) lastDayEventsTrigger?.focus?.();
    };

    const openDayEventsModal = (events, date, trigger) => {
        if (!dayEventsModal || !dayEventsBackdrop || !dayEventsList || !events.length) return;
        lastDayEventsTrigger = trigger || document.activeElement;
        document.getElementById("dayEventsDate").textContent = date;
        document.getElementById("dayEventsSummary").textContent = `${events.length} evento${events.length === 1 ? " oculto" : "s ocultos"}`;
        dayEventsList.replaceChildren();

        events.forEach((event) => {
            const visualStatus = event.tipo === "retorno" ? "return" : event.status_classe;
            const item = document.createElement("button");
            item.className = `day-event-item status-${visualStatus}`;
            item.type = "button";
            item.dataset.eventId = event.id;

            const marker = document.createElement("span");
            marker.className = "day-event-marker";
            const copy = document.createElement("span");
            copy.className = "day-event-copy";
            const name = document.createElement("strong");
            name.textContent = event.nome;
            const type = document.createElement("small");
            type.textContent = eventTypeLabel(event);
            const icon = document.createElement("i");
            icon.setAttribute("data-lucide", "chevron-right");

            copy.append(name, type);
            item.append(marker, copy, icon);
            item.addEventListener("click", () => selectHiddenEvent(
                event,
                () => closeDayEventsModal(false),
                (selectedEvent) => openDrawer(selectedEvent, lastDayEventsTrigger)
            ));
            dayEventsList.append(item);
        });

        dayEventsModal.hidden = false;
        dayEventsBackdrop.hidden = false;
        dayEventsModal.setAttribute("aria-hidden", "false");
        document.body.classList.add("day-events-open");
        if (typeof lucide !== "undefined") lucide.createIcons();
        window.requestAnimationFrame(() => {
            dayEventsBackdrop.classList.add("is-visible");
            dayEventsModal.classList.add("is-open");
            document.getElementById("closeDayEventsModal")?.focus();
        });
    };

    document.getElementById("closeDayEventsModal")?.addEventListener("click", () => closeDayEventsModal());
    dayEventsBackdrop?.addEventListener("click", () => closeDayEventsModal());

    const captureFilters = (workspace) => ({
        search: workspace?.querySelector("#calendarSearch")?.value || "",
        branch: workspace?.querySelector("#branchFilter")?.value || "",
        department: workspace?.querySelector("#departmentFilter")?.value || "",
        status: workspace?.querySelector("#statusFilter")?.value || "",
        period: workspace?.querySelector("#periodFilter")?.value || "month"
    });

    const restoreFilters = (workspace, filters) => {
        if (!filters) return;
        const values = {
            calendarSearch: filters.search,
            branchFilter: filters.branch,
            departmentFilter: filters.department,
            statusFilter: filters.status,
            periodFilter: filters.period
        };
        Object.entries(values).forEach(([id, value]) => {
            const control = workspace.querySelector(`#${id}`);
            if (!control || value === undefined) return;
            if (control.tagName === "SELECT" && ![...control.options].some((option) => option.value === value)) return;
            control.value = value;
        });
    };

    const initWorkspace = (workspace, savedFilters = null) => {
        activeWorkspace = workspace;
        const dataNode = workspace.querySelector("#calendarData");
        const calendarEvents = JSON.parse(dataNode?.textContent || "[]");
        activeEvents = new Map(calendarEvents.map((event) => [String(event.id), event]));

        const controls = {
            search: workspace.querySelector("#calendarSearch"),
            branch: workspace.querySelector("#branchFilter"),
            department: workspace.querySelector("#departmentFilter"),
            status: workspace.querySelector("#statusFilter"),
            period: workspace.querySelector("#periodFilter")
        };
        const days = [...workspace.querySelectorAll(".calendar-day")];
        const filterItems = [...workspace.querySelectorAll("[data-filter-item]")];
        const result = workspace.querySelector("#filterResult");
        const listCount = workspace.querySelector("#listResultCount");
        const emptyFilter = workspace.querySelector("#calendarEmptyFilter");

        restoreFilters(workspace, savedFilters);

        const periodRange = () => {
            const today = startOfDay(new Date());
            if (controls.period.value === "today") return [today, today];
            if (controls.period.value === "next7") return [today, addDays(today, 6)];
            if (controls.period.value === "next15") return [today, addDays(today, 14)];
            return null;
        };

        const eventMatches = (event) => {
            const search = normalizeText(controls.search.value);
            const branch = normalizeText(controls.branch.value);
            const department = normalizeText(controls.department.value);
            const status = controls.status.value;
            const range = periodRange();
            const eventDate = parseBrazilianDate(event.data_evento);

            if (search && !normalizeText(event.nome).includes(search)) return false;
            if (branch && normalizeText(event.filial) !== branch) return false;
            if (department && normalizeText(event.departamento) !== department) return false;
            if (status && event.status_classe !== status) return false;
            if (range && eventDate && (eventDate < range[0] || eventDate > range[1])) return false;
            return true;
        };

        const dayIsInPeriod = (day) => {
            const range = periodRange();
            if (!range) return true;
            const date = parseIsoDate(day.dataset.dateIso);
            return date && date >= range[0] && date <= range[1];
        };

        const eventOccursOnDay = (event, day) => {
            const date = parseIsoDate(day.dataset.dateIso);
            const eventDate = parseBrazilianDate(event.data_evento);
            return Boolean(date && eventDate && date.getTime() === eventDate.getTime());
        };

        const eventsForDay = (day) => (day.dataset.eventIds || "")
            .split(",")
            .filter(Boolean)
            .map((id) => activeEvents.get(id))
            .filter((event) => event && eventOccursOnDay(event, day));

        const renderDay = (day) => {
            const container = day.querySelector(".day-events");
            const more = container.querySelector(".more-events");
            container.querySelectorAll(".calendar-event").forEach((node) => node.remove());

            const visible = dayIsInPeriod(day) ? eventsForDay(day).filter(eventMatches) : [];
            const partition = partitionEvents(visible);
            partition.visible.forEach((event) => {
                const isReturnDay = event.tipo === "retorno";
                const visualStatus = isReturnDay ? "return" : event.status_classe;
                const button = document.createElement("button");
                button.className = `calendar-event status-${visualStatus}`;
                button.type = "button";
                button.dataset.eventId = event.id;
                button.title = `${event.nome} · ${statusLabel(event)}`;
                button.innerHTML = `<span class="event-name">${escapeHtml(event.nome)}</span>${isReturnDay ? '<i class="return-icon" data-lucide="log-in"></i>' : ""}`;
                button.addEventListener("click", (clickEvent) => {
                    clickEvent.stopPropagation();
                    openDrawer(event, button);
                });
                container.insertBefore(button, more);
            });

            const extra = partition.hidden.length;
            more.hidden = extra === 0;
            more.textContent = overflowLabel(extra);
            if (extra) {
                const openHiddenEvents = (interactionEvent) => {
                    interactionEvent?.stopPropagation();
                    openDayEventsModal(partition.hidden, day.dataset.date, more);
                };
                more.onclick = openHiddenEvents;
                more.onkeydown = (keyEvent) => {
                    if (keyEvent.key !== "Enter" && keyEvent.key !== " ") return;
                    keyEvent.preventDefault();
                    openHiddenEvents(keyEvent);
                };
                more.tabIndex = 0;
                more.setAttribute("role", "button");
                more.setAttribute("aria-label", `Ver ${extra} evento${extra === 1 ? " oculto" : "s ocultos"} de ${day.dataset.date}`);
            } else {
                more.onclick = null;
                more.onkeydown = null;
                more.removeAttribute("tabindex");
                more.removeAttribute("role");
                more.removeAttribute("aria-label");
            }
        };

        const applyFilters = () => {
            const matchingEvents = calendarEvents.filter(eventMatches);
            const matchingIds = new Set(matchingEvents.map((event) => String(event.id)));
            days.forEach(renderDay);

            filterItems.forEach((item) => {
                item.hidden = !matchingIds.has(item.dataset.eventId);
            });

            const visibleRows = workspace.querySelectorAll("#lista-ferias tbody tr[data-event-id]:not([hidden])").length;
            if (result) result.textContent = `${matchingEvents.length} evento${matchingEvents.length === 1 ? "" : "s"}`;
            if (listCount) listCount.textContent = `${visibleRows} registro${visibleRows === 1 ? "" : "s"}`;
            if (emptyFilter) emptyFilter.hidden = matchingEvents.length > 0 || calendarEvents.length === 0;
            if (typeof lucide !== "undefined") lucide.createIcons();
        };

        Object.values(controls).forEach((control) => {
            control?.addEventListener(control.type === "search" ? "input" : "change", applyFilters);
        });

        workspace.querySelector("#clearCalendarFilters")?.addEventListener("click", () => {
            controls.search.value = "";
            controls.branch.value = "";
            controls.department.value = "";
            controls.status.value = "";
            controls.period.value = "month";
            applyFilters();
            controls.search.focus();
        });

        workspace.querySelectorAll("[data-open-event], .agenda-item[data-event-id]").forEach((control) => {
            control.addEventListener("click", () => openDrawer(activeEvents.get(control.dataset.openEvent || control.dataset.eventId), control));
        });

        workspace.querySelectorAll("#lista-ferias tbody tr[data-event-id]").forEach((row) => {
            row.addEventListener("dblclick", () => openDrawer(activeEvents.get(row.dataset.eventId), row));
        });

        days.forEach((day) => {
            day.addEventListener("keydown", (keyEvent) => {
                if (keyEvent.key !== "Enter" && keyEvent.key !== " ") return;
                const firstEvent = eventsForDay(day).find(eventMatches);
                if (!firstEvent) return;
                keyEvent.preventDefault();
                openDrawer(firstEvent, day);
            });
        });

        workspace.querySelectorAll("a.month-nav").forEach((link) => {
            link.addEventListener("click", (clickEvent) => {
                if (clickEvent.ctrlKey || clickEvent.metaKey || clickEvent.shiftKey || clickEvent.altKey) return;
                clickEvent.preventDefault();
                navigateCalendar(link.href, true);
            });
        });

        applyFilters();
    };

    const navigateCalendar = async (url, pushHistory) => {
        const filters = captureFilters(activeWorkspace);
        closeDrawer();
        closeDayEventsModal(false);
        loader.hidden = false;
        activeWorkspace?.classList.add("is-loading");

        try {
            const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const html = await response.text();
            const parsed = new DOMParser().parseFromString(html, "text/html");
            const nextWorkspace = parsed.querySelector("#calendarWorkspace");
            if (!nextWorkspace) throw new Error("Calendário não encontrado");

            activeWorkspace.replaceWith(nextWorkspace);
            if (pushHistory) history.pushState({ calendar: true }, "", url);
            initWorkspace(nextWorkspace, filters);
            if (typeof lucide !== "undefined") lucide.createIcons();
            nextWorkspace.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (error) {
            window.location.assign(url);
        } finally {
            loader.hidden = true;
            activeWorkspace?.classList.remove("is-loading");
        }
    };

    window.addEventListener("popstate", () => navigateCalendar(window.location.href, false));

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            if (dayEventsModal?.classList.contains("is-open")) closeDayEventsModal();
            else if (drawer?.classList.contains("is-open")) closeDrawer();
            else setSidebarOpen(false);
        }
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            const input = activeWorkspace?.querySelector("#calendarSearch");
            if (!input) return;
            event.preventDefault();
            input.focus();
            input.select();
        }
    });

    const initialWorkspace = document.getElementById("calendarWorkspace");
    initWorkspace(initialWorkspace);
    window.requestAnimationFrame(() => revealNavigationTarget(initialWorkspace));
});
