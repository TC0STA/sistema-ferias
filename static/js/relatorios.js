document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") lucide.createIcons();

    const font = { family: "Manrope", size: 10, weight: "600" };
    const gridColor = "rgba(104, 119, 139, .11)";
    const readData = (id, key) => {
        const element = document.getElementById(id);
        if (!element) return [];
        try { return JSON.parse(element.dataset[key] || "[]"); }
        catch { return []; }
    };
    const valueLabels = {
        id: "valueLabels",
        afterDatasetsDraw(chart) {
            const { ctx } = chart;
            ctx.save();
            ctx.fillStyle = "#425267";
            ctx.font = "700 10px Manrope";
            ctx.textAlign = "center";
            chart.data.datasets.forEach((dataset, datasetIndex) => {
                chart.getDatasetMeta(datasetIndex).data.forEach((bar, index) => {
                    const value = dataset.data[index];
                    if (!value) return;
                    ctx.fillText(String(value), bar.x, bar.y - 7);
                });
            });
            ctx.restore();
        }
    };

    const verticalBar = (id, color) => {
        const canvas = document.getElementById(id);
        if (!canvas || typeof Chart === "undefined") return;
        new Chart(canvas, {
            type: "bar",
            plugins: [valueLabels],
            data: {
                labels: readData(id, "labels").map(label => label.slice(0, 3)),
                datasets: [{
                    data: readData(id, "values"),
                    backgroundColor: color,
                    borderRadius: 6,
                    borderSkipped: false,
                    maxBarThickness: 28
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 15 } },
                plugins: { legend: { display: false }, tooltip: { displayColors: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: "#68778b", font } },
                    y: { beginAtZero: true, ticks: { color: "#8a97a6", precision: 0, font }, grid: { color: gridColor } }
                }
            }
        });
    };
    verticalBar("vacationsMonthChart", "rgba(23, 105, 224, .78)");
    verticalBar("blocksMonthChart", "rgba(118, 87, 213, .76)");

    const departmentCanvas = document.getElementById("departmentChart");
    if (departmentCanvas && typeof Chart !== "undefined") {
        new Chart(departmentCanvas, {
            type: "bar",
            data: {
                labels: readData("departmentChart", "labels"),
                datasets: [{
                    data: readData("departmentChart", "values"),
                    backgroundColor: ["#1769e0", "#3686ed", "#63a1ee", "#8bb9ed", "#b6d3ee"],
                    borderRadius: 7,
                    borderSkipped: false,
                    maxBarThickness: 24
                }]
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { displayColors: false } },
                scales: {
                    x: { beginAtZero: true, ticks: { color: "#8a97a6", precision: 0, font }, grid: { color: gridColor } },
                    y: { grid: { display: false }, ticks: { color: "#526175", font } }
                }
            }
        });
    }

    const statusCanvas = document.getElementById("statusChart");
    if (statusCanvas && typeof Chart !== "undefined") {
        new Chart(statusCanvas, {
            type: "doughnut",
            data: {
                labels: ["Em férias", "Programadas", "Concluídas"],
                datasets: [{
                    data: readData("statusChart", "values"),
                    backgroundColor: ["#1ca66f", "#e9a008", "#a7b2bf"],
                    borderColor: "#fff",
                    borderWidth: 5,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "70%",
                plugins: { legend: { display: false } }
            }
        });
    }

    const form = document.getElementById("reportFilters");
    form?.querySelectorAll("select").forEach(select => {
        select.addEventListener("change", () => form.requestSubmit());
    });

    const menuToggle = document.getElementById("menuToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const setSidebarOpen = open => {
        document.body.classList.toggle("sidebar-open", open);
        menuToggle?.setAttribute("aria-expanded", String(open));
    };
    menuToggle?.addEventListener("click", () => setSidebarOpen(!document.body.classList.contains("sidebar-open")));
    sidebarOverlay?.addEventListener("click", () => setSidebarOpen(false));
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") setSidebarOpen(false);
    });
});
