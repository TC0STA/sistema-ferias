document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") {
        lucide.createIcons();
    }

    const input = document.getElementById("search");
    const field = document.getElementById("searchField");
    const tbody = document.getElementById("tbody");
    const resultCount = document.getElementById("resultCount");
    const noResults = document.getElementById("noResults");

    const normalizeText = (value) => (
        String(value || "")
            .trim()
            .toLocaleLowerCase("pt-BR")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
    );

    const placeholders = {
        all: "Pesquisar colaborador, data, execução ou status",
        nome: "Pesquisar colaborador",
        data: "Pesquisar por data",
        execucao: "Pesquisar por execução",
        status: "Pesquisar por status"
    };

    const filterRows = () => {
        if (!input || !field || !tbody) return;

        const query = normalizeText(input.value);
        const selectedField = field.value;
        const rows = [...tbody.querySelectorAll("tr:not(.empty-row)")];
        let visible = 0;

        rows.forEach((row) => {
            const searchable = selectedField === "all"
                ? `${row.dataset.nome} ${row.dataset.data} ${row.dataset.execucao} ${row.dataset.status}`
                : row.dataset[selectedField];
            const matches = query === "" || normalizeText(searchable).includes(query);
            row.hidden = !matches;
            if (matches) visible += 1;
        });

        if (resultCount) {
            resultCount.textContent = `${visible} registro(s) encontrado(s)`;
        }
        if (noResults) {
            noResults.hidden = visible > 0 || rows.length === 0;
        }
    };

    input?.addEventListener("input", filterRows);
    field?.addEventListener("change", () => {
        input.placeholder = placeholders[field.value] || placeholders.all;
        filterRows();
        input.focus();
    });
    filterRows();

    document.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            input?.focus();
        }
        if (event.key === "Escape") {
            input?.blur();
            setSidebarOpen(false);
        }
    });

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
});
