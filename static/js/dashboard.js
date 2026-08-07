document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") lucide.createIcons();

    const normalizeText = (value = "") => value
        .trim()
        .toLocaleLowerCase("pt-BR")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");

    const greeting = document.getElementById("dynamicGreeting");
    if (greeting) {
        const hour = new Date().getHours();
        greeting.textContent = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
    }

    const chartCanvas = document.getElementById("graficoBloqueios");
    if (chartCanvas && typeof Chart !== "undefined") {
        const labels = JSON.parse(chartCanvas.dataset.labels || "[]");
        const valores = JSON.parse(chartCanvas.dataset.valores || "[]");
        const hasData = labels.length > 0 && valores.some((value) => Number(value) > 0);

        new Chart(chartCanvas, {
            type: "bar",
            data: {
                labels: hasData ? labels : ["Sem dados"],
                datasets: [{
                    label: "Bloqueios",
                    data: hasData ? valores : [0],
                    backgroundColor: "rgba(37, 99, 235, .78)",
                    hoverBackgroundColor: "#2563eb",
                    borderRadius: 7,
                    borderSkipped: false,
                    barPercentage: .72,
                    categoryPercentage: .78,
                    maxBarThickness: 52
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { intersect: false, mode: "index" },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#172033",
                        titleFont: { family: "Inter", size: 11, weight: "600" },
                        bodyFont: { family: "Inter", size: 11 },
                        padding: 10,
                        cornerRadius: 8,
                        displayColors: false
                    }
                },
                scales: {
                    x: {
                        border: { display: false },
                        grid: { display: false },
                        ticks: { color: "#7b8899", font: { family: "Inter", size: 10, weight: "500" }, maxRotation: 0, autoSkip: true, maxTicksLimit: 7 }
                    },
                    y: {
                        beginAtZero: true,
                        border: { display: false },
                        grid: { color: "rgba(125, 142, 163, .12)" },
                        ticks: { color: "#8995a5", precision: 0, font: { family: "Inter", size: 9 }, padding: 8 }
                    }
                }
            }
        });
    }

    const searchInput = document.getElementById("dashboardSearch");
    const searchableRows = [...document.querySelectorAll("[data-searchable-row]")];
    if (searchInput) {
        searchInput.addEventListener("input", ({ target }) => {
            const query = normalizeText(target.value);
            searchableRows.forEach((row) => {
                row.hidden = query !== "" && !normalizeText(row.innerText).includes(query);
            });
        });

        document.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
        });
    }

    const revealTarget = (targetId) => {
        const target = document.getElementById(targetId);
        if (!target) return;

        const details = target.closest("details");
        if (details) details.open = true;

        window.requestAnimationFrame(() => {
            target.scrollIntoView({ behavior: "smooth", block: "center" });
            target.classList.add("highlight");
            window.setTimeout(() => target.classList.remove("highlight"), 1400);
        });
    };

    document.querySelectorAll("[data-target]").forEach((control) => {
        control.addEventListener("click", () => revealTarget(control.dataset.target));
    });

    const refreshButton = document.getElementById("refreshDashboard");
    const loader = document.getElementById("dashboardLoader");
    if (refreshButton) {
        refreshButton.addEventListener("click", () => {
            refreshButton.disabled = true;
            refreshButton.setAttribute("aria-busy", "true");
            if (loader) loader.hidden = false;
            window.setTimeout(() => window.location.reload(), 350);
        });
    }

    const menuToggle = document.getElementById("menuToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const setSidebarOpen = (open) => {
        document.body.classList.toggle("sidebar-open", open);
        if (menuToggle) menuToggle.setAttribute("aria-expanded", String(open));
    };

    if (menuToggle) {
        menuToggle.addEventListener("click", () => setSidebarOpen(!document.body.classList.contains("sidebar-open")));
    }
    if (sidebarOverlay) sidebarOverlay.addEventListener("click", () => setSidebarOpen(false));
    document.querySelectorAll(".sidebar-nav a").forEach((link) => link.addEventListener("click", () => setSidebarOpen(false)));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setSidebarOpen(false);
    });
});
