document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") lucide.createIcons();

    const menuToggle = document.getElementById("menuToggle");
    const sidebarOverlay = document.getElementById("sidebarOverlay");
    const setSidebarOpen = open => {
        document.body.classList.toggle("sidebar-open", open);
        menuToggle?.setAttribute("aria-expanded", String(open));
    };
    menuToggle?.addEventListener("click", () => {
        setSidebarOpen(!document.body.classList.contains("sidebar-open"));
    });
    sidebarOverlay?.addEventListener("click", () => setSidebarOpen(false));
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") setSidebarOpen(false);
    });

    const settingsForm = document.getElementById("settingsForm");
    const applyAppearance = () => {
        const theme = settingsForm?.querySelector("[name='tema']:checked")?.value;
        const fontSize = settingsForm?.querySelector("[name='tamanho_fonte']")?.value;
        const color = settingsForm?.querySelector("[name='cor_principal']")?.value;
        if (theme) document.documentElement.dataset.theme = theme;
        if (fontSize) document.documentElement.dataset.fontSize = fontSize;
        if (color) document.documentElement.dataset.color = color;
    };
    settingsForm?.querySelectorAll("[name='tema'], [name='tamanho_fonte'], [name='cor_principal']").forEach(field => {
        field.addEventListener("change", applyAppearance);
    });
    settingsForm?.addEventListener("submit", event => {
        const theme = settingsForm.querySelector("[name='tema']:checked")?.value || "claro";
        const fontSize = settingsForm.querySelector("[name='tamanho_fonte']")?.value || "normal";
        const color = settingsForm.querySelector("[name='cor_principal']")?.value || "azul-fokus";
        localStorage.setItem("fokus-theme", theme);
        localStorage.setItem("fokus-font-size", fontSize);
        localStorage.setItem("fokus-color", color);
    });
    if (settingsForm) applyAppearance();
});
