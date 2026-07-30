document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") {
        lucide.createIcons();
    }

    const normalizeText = (value) => (
        value
            .trim()
            .toLocaleLowerCase("pt-BR")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
    );

    const chartCanvas = document.getElementById("graficoBloqueios");

    if (chartCanvas && typeof Chart !== "undefined") {
        const labels = JSON.parse(chartCanvas.dataset.labels || "[]");
        const valores = JSON.parse(chartCanvas.dataset.valores || "[]");
        const valueLabelsPlugin = {
            id: "valueLabels",
            afterDatasetsDraw(chart) {
                const { ctx } = chart;
                ctx.save();
                ctx.fillStyle = "#34455a";
                ctx.font = "700 13px Manrope";
                ctx.textAlign = "center";
                ctx.textBaseline = "bottom";

                chart.data.datasets.forEach((dataset, datasetIndex) => {
                    const meta = chart.getDatasetMeta(datasetIndex);
                    meta.data.forEach((bar, index) => {
                        const value = dataset.data[index];
                        if (value === null || value === undefined) return;
                        ctx.fillText(String(value), bar.x, bar.y - 8);
                    });
                });

                ctx.restore();
            }
        };

        new Chart(chartCanvas, {
            type: "bar",
            plugins: [valueLabelsPlugin],
            data: {
                labels,
                datasets: [{
                    label: "Bloqueios",
                    data: valores,
                    backgroundColor: "rgba(23, 105, 224, .78)",
                    borderColor: "#1769e0",
                    borderWidth: 1,
                    borderRadius: 8,
                    borderSkipped: false,
                    barPercentage: 0.78,
                    categoryPercentage: 0.82,
                    maxBarThickness: 68
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        top: 24
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: "#5f6f82",
                            font: {
                                family: "Manrope",
                                size: 13,
                                weight: "600"
                            },
                            padding: 9
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: "#6d7788",
                            precision: 0,
                            font: {
                                family: "Manrope",
                                size: 12
                            },
                            padding: 8
                        },
                        grid: {
                            color: "rgba(109, 119, 136, .12)"
                        }
                    }
                }
            }
        });
    }

    const filterTable = (inputId, tableId, cellIndex = 0) => {
        const input = document.getElementById(inputId);
        const table = document.querySelector(`#${tableId} table`);
        if (!input || !table) return;

        input.addEventListener("input", (event) => {
            const query = normalizeText(event.target.value);
            const rows = table.querySelectorAll("tbody tr:not(.empty-row)");

            rows.forEach((row) => {
                const cells = row.querySelectorAll("td");
                if (!cells.length) return;

                const text = normalizeText(cells[cellIndex].innerText);
                row.hidden = query !== "" && !text.includes(query);
            });
        });
    };

    filterTable("hojeSearch", "tabela-hoje");
    filterTable("proximosSearch", "tabela-proximos");
    filterTable("historicoSearch", "tabela-historico");
    filterTable("todosSearch", "todos-usuarios");

    const globalSearch = document.getElementById("dashboardSearch");

    if (globalSearch) {
        globalSearch.addEventListener("input", (event) => {
            const query = normalizeText(event.target.value);
            const rows = document.querySelectorAll(".tables-grid tbody tr:not(.empty-row)");

            rows.forEach((row) => {
                const firstCell = row.querySelector("td");
                if (!firstCell) return;

                const text = normalizeText(firstCell.innerText);
                row.hidden = query !== "" && !text.includes(query);
            });
        });
    }

    document.querySelectorAll(".metric-card[data-target], .dashboard-alert [data-target]").forEach((card) => {
        card.addEventListener("click", () => {
            const target = document.getElementById(card.dataset.target);
            if (!target) return;

            target.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

            target.classList.add("highlight");
            window.setTimeout(() => target.classList.remove("highlight"), 1400);
        });
    });

    const refreshButton = document.getElementById("refreshDashboard");
    if (refreshButton) {
        refreshButton.addEventListener("click", () => window.location.reload());
    }

    const menuToggle = document.getElementById("menuToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");

    const setSidebarOpen = (open) => {
        document.body.classList.toggle("sidebar-open", open);
        if (menuToggle) {
            menuToggle.setAttribute("aria-expanded", String(open));
        }
    };

    if (menuToggle) {
        menuToggle.addEventListener("click", () => {
            setSidebarOpen(!document.body.classList.contains("sidebar-open"));
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener("click", () => setSidebarOpen(false));
    }

    document.querySelectorAll(".sidebar-nav a").forEach((link) => {
        link.addEventListener("click", () => setSidebarOpen(false));
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            setSidebarOpen(false);
        }
    });
});
