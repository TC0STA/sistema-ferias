document.addEventListener("DOMContentLoaded", () => {
    if (typeof lucide !== "undefined") lucide.createIcons();
    const password = document.getElementById("loginPassword");
    const toggle = document.getElementById("passwordToggle");
    toggle?.addEventListener("click", () => {
        const show = password.type === "password";
        password.type = show ? "text" : "password";
        toggle.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
        toggle.innerHTML = `<i data-lucide="${show ? "eye-off" : "eye"}"></i>`;
        if (typeof lucide !== "undefined") lucide.createIcons();
        password.focus();
    });
});
