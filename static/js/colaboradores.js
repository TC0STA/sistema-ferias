document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") {
        lucide.createIcons();
    }

    const menuToggle = document.getElementById("menuToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const setSidebarOpen = (open) => {
        document.body.classList.toggle("sidebar-open", open);
        menuToggle?.setAttribute("aria-expanded", String(open));
    };

    menuToggle?.addEventListener("click", () => {
        setSidebarOpen(!document.body.classList.contains("sidebar-open"));
    });
    sidebarOverlay?.addEventListener("click", () => setSidebarOpen(false));
    document.querySelectorAll(".sidebar-nav a").forEach((link) => {
        link.addEventListener("click", () => setSidebarOpen(false));
    });

    const search = document.getElementById("collaboratorSearch");
    const statusFilter = document.getElementById("statusFilter");
    const departmentFilter = document.getElementById("departmentFilter");
    const count = document.getElementById("collaboratorCount");
    const empty = document.getElementById("filterEmpty");
    const rows = [...document.querySelectorAll("#collaboratorsBody tr:not(.empty-row)")];

    const normalizeText = (value) => (
        String(value || "")
            .trim()
            .toLocaleLowerCase("pt-BR")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
    );

    const applyFilters = () => {
        const query = normalizeText(search?.value);
        const selectedStatus = statusFilter?.value || "";
        const selectedDepartment = normalizeText(departmentFilter?.value);
        let visible = 0;

        rows.forEach((row) => {
            const matchesSearch = !query
                || normalizeText(`${row.dataset.name} ${row.dataset.department}`).includes(query);
            const matchesStatus = !selectedStatus || row.dataset.status === selectedStatus;
            const matchesDepartment = !selectedDepartment
                || normalizeText(row.dataset.department) === selectedDepartment;
            const matches = matchesSearch && matchesStatus && matchesDepartment;
            row.hidden = !matches;
            if (matches) visible += 1;
        });

        if (count) count.textContent = `${visible} colaborador(es) encontrado(s)`;
        if (empty) empty.hidden = visible > 0 || rows.length === 0;
    };

    search?.addEventListener("input", applyFilters);
    statusFilter?.addEventListener("change", applyFilters);
    departmentFilter?.addEventListener("change", applyFilters);

    document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && search) {
            event.preventDefault();
            search.focus();
        }
        if (event.key === "Escape") {
            setSidebarOpen(false);
            search?.blur();
        }
    });
});
