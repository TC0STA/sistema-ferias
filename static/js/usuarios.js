document.addEventListener("DOMContentLoaded", () => {
    const rows = [...document.querySelectorAll("[data-user-row]")];
    const search = document.getElementById("userSearch");
    const profile = document.getElementById("profileFilter");
    const status = document.getElementById("statusFilter");
    const empty = document.getElementById("usersEmpty");

    const normalize = value => (value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
    const filterRows = () => {
        const term = normalize(search?.value);
        let visible = 0;
        rows.forEach(row => {
            const matches = (!term || normalize(row.dataset.search).includes(term))
                && (!profile?.value || row.dataset.profile === profile.value)
                && (!status?.value || row.dataset.status === status.value);
            row.hidden = !matches;
            if (matches) visible += 1;
        });
        if (empty) empty.hidden = visible !== 0;
    };
    search?.addEventListener("input", filterRows);
    profile?.addEventListener("change", filterRows);
    status?.addEventListener("change", filterRows);

    const closeModal = modal => {
        if (!modal) return;
        modal.hidden = true;
        document.body.classList.remove("user-modal-open");
    };
    const openModal = modal => {
        if (!modal) return;
        modal.hidden = false;
        document.body.classList.add("user-modal-open");
        window.setTimeout(() => modal.querySelector("input:not([type='hidden']), select")?.focus(), 20);
    };
    document.querySelectorAll("[data-open-modal]").forEach(button => {
        button.addEventListener("click", () => openModal(document.getElementById(button.dataset.openModal)));
    });
    document.querySelectorAll("[data-close-modal]").forEach(button => {
        button.addEventListener("click", () => closeModal(button.closest(".user-modal")));
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeModal(document.querySelector(".user-modal:not([hidden])"));
    });

    const editModal = document.getElementById("editUserModal");
    const editForm = document.getElementById("editUserForm");
    document.querySelectorAll("[data-edit-user]").forEach(button => {
        button.addEventListener("click", () => {
            editForm.action = `/usuarios/${button.dataset.id}/editar`;
            editForm.elements.nome.value = button.dataset.name;
            editForm.elements.email.value = button.dataset.email;
            editForm.elements.perfil.value = button.dataset.profile;
            editForm.elements.ativo.value = button.dataset.active;
            openModal(editModal);
        });
    });

    const resetModal = document.getElementById("resetPasswordModal");
    const resetForm = document.getElementById("resetPasswordForm");
    const resetName = document.getElementById("resetUserName");
    document.querySelectorAll("[data-reset-user]").forEach(button => {
        button.addEventListener("click", () => {
            resetForm.reset();
            resetForm.action = `/usuarios/${button.dataset.id}/redefinir-senha`;
            resetName.textContent = `${button.dataset.name} (${button.dataset.username})`;
            openModal(resetModal);
        });
    });
});
