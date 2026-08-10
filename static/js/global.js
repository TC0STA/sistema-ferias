document.addEventListener("DOMContentLoaded", () => {
    // O servidor pode estar em outro fuso horário. A sincronização exibida na
    // interface deve acompanhar o relógio local do computador que abriu o sistema.
    const localSyncTime = new Date();
    const padDatePart = value => String(value).padStart(2, "0");
    const formattedLocalSyncTime = [
        padDatePart(localSyncTime.getDate()),
        padDatePart(localSyncTime.getMonth() + 1),
        localSyncTime.getFullYear()
    ].join("/") + " " + [
        padDatePart(localSyncTime.getHours()),
        padDatePart(localSyncTime.getMinutes())
    ].join(":");
    document.querySelectorAll(".sync-meta strong").forEach(element => {
        element.textContent = formattedLocalSyncTime;
    });

    // Componente compartilhado de usuário no rodapé do menu lateral.
    const sidebarFooter = document.querySelector(".sidebar-footer");
    if (sidebarFooter && !sidebarFooter.querySelector(".sidebar-user")) {
        const profileName = document.querySelector(".profile-copy strong")?.textContent?.trim()
            || "Tiago Costa";
        const initials = profileName
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map(part => part[0]?.toUpperCase())
            .join("") || "TC";
        const sidebarUser = document.createElement("div");
        sidebarUser.className = "sidebar-user";
        sidebarUser.setAttribute("aria-label", `Usuário conectado: ${profileName}`);
        sidebarUser.innerHTML = `
            <span class="sidebar-user-avatar" aria-hidden="true"></span>
            <span class="sidebar-user-copy"><small>Usuário conectado</small><strong></strong></span>
        `;
        sidebarUser.querySelector(".sidebar-user-avatar").textContent = initials;
        sidebarUser.querySelector("strong").textContent = profileName;
        sidebarFooter.prepend(sidebarUser);
    }

    // Mantém uma nomenclatura consistente no menu sem tocar nas rotas.
    const navigationLabels = new Map([
        ["/dashboard", "Dashboard"],
        ["#dashboard", "Dashboard"],
        ["/importar", "Importação"],
        ["/colaboradores", "Colaboradores"],
        ["/calendario", "Calendário"],
        ["/relatorios", "Relatórios"],
        ["/historico", "Histórico"],
        ["/usuarios", "Usuários"],
        ["/configuracoes", "Configurações"]
    ]);
    document.querySelectorAll(".sidebar-nav .nav-link").forEach(link => {
        const label = navigationLabels.get(link.getAttribute("href"));
        const text = link.querySelector("span");
        if (label && text) text.textContent = label;
    });

    const savedTheme = localStorage.getItem("fokus-theme");
    const savedFont = localStorage.getItem("fokus-font-size");
    const savedColor = localStorage.getItem("fokus-color");
    if (savedTheme) document.documentElement.dataset.theme = savedTheme;
    if (savedFont) document.documentElement.dataset.fontSize = savedFont;
    if (savedColor) document.documentElement.dataset.color = savedColor;

    const center = document.getElementById("notificationCenter");
    const button = document.getElementById("notificationButton");
    const popover = document.getElementById("notificationPopover");
    const notificationItems = [...document.querySelectorAll(".notification-item")];
    const readNotificationsKey = "fokus-read-notifications";
    const notificationId = item => {
        const content = `${item.getAttribute("href") || ""}|${item.textContent}`
            .replace(/\s+/g, " ")
            .trim();
        let hash = 2166136261;
        for (let index = 0; index < content.length; index += 1) {
            hash ^= content.charCodeAt(index);
            hash = Math.imul(hash, 16777619);
        }
        return (hash >>> 0).toString(36);
    };
    const loadReadNotifications = () => {
        try {
            const saved = JSON.parse(localStorage.getItem(readNotificationsKey) || "[]");
            return new Set(Array.isArray(saved) ? saved : []);
        } catch (_) {
            return new Set();
        }
    };
    const readNotifications = loadReadNotifications();
    const updateNotificationCount = () => {
        const unreadCount = notificationItems.filter(item => !item.classList.contains("is-read")).length;
        const badge = button?.querySelector(":scope > span");
        const label = button?.querySelector(":scope > strong");
        const headingCount = popover?.querySelector(".notification-heading > em");
        if (badge) {
            badge.textContent = String(unreadCount);
            badge.hidden = unreadCount === 0;
        }
        if (label) label.textContent = unreadCount ? `${unreadCount} Alertas` : "Alertas";
        if (headingCount) {
            headingCount.textContent = `${unreadCount} nova(s)`;
            headingCount.hidden = unreadCount === 0;
        }
        button?.setAttribute(
            "aria-label",
            unreadCount ? `Abrir notificações: ${unreadCount} nova(s)` : "Abrir notificações"
        );
        return unreadCount;
    };
    notificationItems.forEach(item => {
        const id = notificationId(item);
        item.dataset.notificationId = id;
        if (readNotifications.has(id)) item.classList.add("is-read");
        item.addEventListener("click", () => {
            item.classList.add("is-read");
            readNotifications.add(id);
            try {
                localStorage.setItem(
                    readNotificationsKey,
                    JSON.stringify([...readNotifications].slice(-100))
                );
            } catch (_) {}
            updateNotificationCount();
        });
    });
    const unreadNotificationCount = updateNotificationCount();
    const setOpen = open => {
        if (!center || !button || !popover) return;
        popover.hidden = !open;
        button.setAttribute("aria-expanded", String(open));
        center.classList.toggle("is-open", open);
    };

    button?.addEventListener("click", event => {
        event.stopPropagation();
        setOpen(popover.hidden);
    });
    document.addEventListener("click", event => {
        if (center && !center.contains(event.target)) setOpen(false);
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") setOpen(false);
    });
    if (center?.dataset.autoOpen === "1" && unreadNotificationCount > 0) {
        window.setTimeout(() => setOpen(true), 250);
    }
    if (center?.dataset.sound === "1" && unreadNotificationCount > 0) {
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gain = audioContext.createGain();
            oscillator.frequency.value = 760;
            gain.gain.setValueAtTime(0.06, audioContext.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.22);
            oscillator.connect(gain).connect(audioContext.destination);
            oscillator.start();
            oscillator.stop(audioContext.currentTime + 0.22);
        } catch (_) {}
    }

    const searchCenter = document.getElementById("globalSearchCenter");
    if (searchCenter && !searchCenter.hasAttribute("data-command-search")) {
        const searchButton = document.getElementById("globalSearchButton");
        const searchPopover = document.getElementById("globalSearchPopover");
        const searchInput = document.getElementById("globalSearchInput");
        const setSearchOpen = open => {
            if (!searchButton || !searchPopover) return;
            searchPopover.hidden = !open;
            searchButton.setAttribute("aria-expanded", String(open));
            searchCenter.classList.toggle("is-open", open);
            if (open) window.setTimeout(() => searchInput?.focus(), 30);
        };
        searchButton?.addEventListener("click", event => {
            event.stopPropagation();
            setSearchOpen(searchPopover.hidden);
            setOpen(false);
        });
        document.addEventListener("click", event => {
            if (!searchCenter.contains(event.target)) setSearchOpen(false);
        });
        document.addEventListener("keydown", event => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                const localSearch = document.getElementById("globalSearch");
                if (localSearch) return;
                event.preventDefault();
                event.stopImmediatePropagation();
                setSearchOpen(true);
            }
            if (event.key === "Escape") setSearchOpen(false);
        });
    }

    const ensureToastRegion = () => {
        let region = document.getElementById("toastRegion");
        if (region) return region;
        region = document.createElement("div");
        region.id = "toastRegion";
        region.className = "toast-region";
        region.setAttribute("aria-live", "polite");
        region.setAttribute("aria-label", "Mensagens do sistema");
        document.body.appendChild(region);
        return region;
    };

    const toastIcons = {
        success: "circle-check",
        warning: "triangle-alert",
        error: "circle-x",
        info: "info"
    };

    const showToast = (message, type = "info", duration = 4500) => {
        if (!message) return;
        const region = ensureToastRegion();
        const toast = document.createElement("div");
        toast.className = `system-toast toast-${type}`;
        toast.setAttribute("role", type === "error" ? "alert" : "status");
        toast.innerHTML = `
            <span class="toast-icon"><i data-lucide="${toastIcons[type] || toastIcons.info}"></i></span>
            <span class="toast-copy"><strong></strong></span>
            <button type="button" aria-label="Fechar mensagem"><i data-lucide="x"></i></button>
            <span class="toast-timer" aria-hidden="true"></span>
        `;
        toast.querySelector(".toast-copy strong").textContent = message;
        toast.style.setProperty("--toast-duration", `${duration}ms`);
        const close = () => {
            toast.classList.add("is-leaving");
            window.setTimeout(() => toast.remove(), 220);
        };
        toast.querySelector("button")?.addEventListener("click", close);
        region.appendChild(toast);
        if (typeof lucide !== "undefined") lucide.createIcons();
        window.requestAnimationFrame(() => toast.classList.add("is-visible"));
        window.setTimeout(close, duration);
    };
    window.FokusToast = showToast;

    document.querySelectorAll(".admin-feedback").forEach(feedback => {
        const message = feedback.textContent.replace(/\s+/g, " ").trim();
        showToast(message, feedback.classList.contains("error") ? "error" : "success");
        feedback.hidden = true;
    });

    const params = new URLSearchParams(window.location.search);
    if (params.get("importado") === "1") {
        showToast("Importação concluída com sucesso.", "success");
    }

    const bodyToast = document.body.dataset.toastMessage;
    if (bodyToast) {
        showToast(bodyToast, document.body.dataset.toastType || "info");
    }

    let modalResolve = null;
    const ensureConfirmModal = () => {
        let modal = document.getElementById("systemConfirmModal");
        if (modal) return modal;
        modal = document.createElement("div");
        modal.id = "systemConfirmModal";
        modal.className = "system-modal";
        modal.hidden = true;
        modal.innerHTML = `
            <button class="system-modal-backdrop" type="button" aria-label="Cancelar"></button>
            <section class="system-modal-card" role="dialog" aria-modal="true" aria-labelledby="systemModalTitle" aria-describedby="systemModalMessage">
                <span class="system-modal-icon"><i data-lucide="circle-help"></i></span>
                <div>
                    <span class="system-modal-eyebrow">CONFIRMAÇÃO</span>
                    <h2 id="systemModalTitle">Confirmar ação</h2>
                    <p id="systemModalMessage"></p>
                </div>
                <div class="system-modal-actions">
                    <button class="modal-cancel" type="button">Cancelar</button>
                    <button class="modal-confirm" type="button">Confirmar</button>
                </div>
            </section>
        `;
        document.body.appendChild(modal);
        if (typeof lucide !== "undefined") lucide.createIcons();
        const finish = result => {
            modal.hidden = true;
            document.body.classList.remove("modal-open");
            modalResolve?.(result);
            modalResolve = null;
        };
        modal.querySelector(".system-modal-backdrop")?.addEventListener("click", () => finish(false));
        modal.querySelector(".modal-cancel")?.addEventListener("click", () => finish(false));
        modal.querySelector(".modal-confirm")?.addEventListener("click", () => finish(true));
        modal.addEventListener("keydown", event => {
            if (event.key === "Escape") finish(false);
        });
        return modal;
    };

    const requestConfirmation = (message, confirmLabel = "Confirmar") => {
        const modal = ensureConfirmModal();
        modal.querySelector("#systemModalMessage").textContent = message;
        modal.querySelector(".modal-confirm").textContent = confirmLabel;
        modal.hidden = false;
        document.body.classList.add("modal-open");
        window.setTimeout(() => modal.querySelector(".modal-cancel")?.focus(), 20);
        return new Promise(resolve => {
            modalResolve = resolve;
        });
    };
    window.FokusConfirm = requestConfirmation;

    const confirmedForms = new WeakSet();
    document.addEventListener("submit", async event => {
        const submitter = event.submitter;
        const message = submitter?.dataset.confirm;
        if (!message || confirmedForms.has(event.target)) {
            confirmedForms.delete(event.target);
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        const label = submitter.dataset.confirmLabel
            || submitter.textContent.replace(/\s+/g, " ").trim()
            || "Confirmar";
        const confirmed = await requestConfirmation(message, label);
        if (!confirmed) return;
        confirmedForms.add(event.target);
        event.target.requestSubmit(submitter);
    }, true);

    document.addEventListener("submit", async event => {
        const submitter = event.submitter;
        const action = submitter?.getAttribute("formaction") || event.target.getAttribute("action");
        if (action !== "/backup/gerar") return;
        event.preventDefault();
        showToast("Gerando o backup do sistema...", "info", 3000);
        try {
            const response = await fetch(action, {
                method: "POST",
                body: new FormData(event.target)
            });
            if (!response.ok) throw new Error("Falha ao gerar backup");
            const blob = await response.blob();
            const disposition = response.headers.get("Content-Disposition") || "";
            const match = disposition.match(/filename="?([^";]+)"?/i);
            const filename = match?.[1] || "backup_fokus_ferias.zip";
            const downloadUrl = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = downloadUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
            showToast("Backup realizado com sucesso.", "success");
        } catch (_) {
            showToast("Não foi possível realizar o backup.", "error");
        }
    });

    const uploadForm = document.querySelector('form[action="/upload"]');
    const ensureImportLoading = () => {
        let overlay = document.getElementById("importLoading");
        if (overlay) return overlay;
        overlay = document.createElement("div");
        overlay.id = "importLoading";
        overlay.className = "import-loading";
        overlay.hidden = true;
        overlay.innerHTML = `
            <section class="import-loading-card" role="status" aria-live="polite">
                <span class="import-loading-icon"><i data-lucide="file-up"></i></span>
                <span class="import-loading-eyebrow">PROCESSANDO ARQUIVO</span>
                <h2>Importando planilha...</h2>
                <div class="import-progress" aria-label="Progresso da importação">
                    <span></span>
                </div>
                <ol>
                    <li class="is-active"><i data-lucide="loader-circle"></i><span>Lendo colaboradores...</span></li>
                    <li><i data-lucide="chart-no-axes-combined"></i><span>Gerando indicadores...</span></li>
                    <li><i data-lucide="layout-dashboard"></i><span>Atualizando dashboard...</span></li>
                </ol>
                <p>Não feche esta janela enquanto os dados são processados.</p>
            </section>
        `;
        document.body.appendChild(overlay);
        if (typeof lucide !== "undefined") lucide.createIcons();
        return overlay;
    };

    uploadForm?.addEventListener("submit", event => {
        const fileInput = uploadForm.querySelector('input[type="file"]');
        if (
            uploadForm.dataset.validated !== "1"
            || !fileInput?.files?.length
            || !uploadForm.checkValidity()
        ) return;
        const overlay = ensureImportLoading();
        const bar = overlay.querySelector(".import-progress span");
        const steps = [...overlay.querySelectorAll("li")];
        overlay.hidden = false;
        document.body.classList.add("loading-open");
        bar.style.width = "18%";
        const activate = (index, progress) => {
            steps.forEach((step, stepIndex) => {
                step.classList.toggle("is-active", stepIndex === index);
                step.classList.toggle("is-complete", stepIndex < index);
            });
            bar.style.width = `${progress}%`;
        };
        window.setTimeout(() => activate(1, 52), 850);
        window.setTimeout(() => activate(2, 82), 1800);
        window.setTimeout(() => {
            steps[2]?.classList.add("is-complete");
            bar.style.width = "96%";
        }, 2900);
    });

    const helpContent = [
        [/^\/calendario/, ["Calendário", "Esta tela apresenta os períodos de férias, retornos e próximos bloqueios."]],
        [/^\/dashboard/, ["Dashboard", "Acompanhe indicadores, bloqueios, movimentações e o resumo operacional do sistema."]],
        [/^\/historico/, ["Histórico", "Consulte os períodos e registros processados anteriormente."]],
        [/^\/colaboradores/, ["Colaboradores", "Consulte e atualize os dados profissionais e os períodos de férias."]],
        [/^\/relatorios/, ["Relatórios", "Analise os indicadores e exporte informações da operação."]],
        [/^\/configuracoes/, ["Configurações", "Personalize importações, notificações, backups e preferências do sistema."]],
        [/^\/auditoria/, ["Auditoria", "Consulte as ações realizadas, seus responsáveis e resultados."]],
        [/^\/usuarios/, ["Administração de Usuários", "Crie, edite e controle os acessos ao sistema."]],
        [/^\/alertas/, ["Centro de Alertas", "Reúne avisos operacionais que precisam de acompanhamento."]],
        [/^\/operacoes/, ["Centro de Operações", "Mostra as atividades e movimentações mais recentes do sistema."]],
        [/^\/importar/, ["Importar planilha", "Envie a planilha atualizada para recalcular os dados do sistema."]],
        [/^\//, ["Início", "Visão resumida das informações mais importantes do sistema Fokus Férias."]]
    ];
    const currentHelp = helpContent.find(([pattern]) => pattern.test(window.location.pathname));
    if (currentHelp && document.querySelector(".topbar")) {
        const helpButton = document.createElement("button");
        helpButton.type = "button";
        helpButton.className = "help-button";
        helpButton.setAttribute("aria-label", `Ajuda sobre ${currentHelp[1][0]}`);
        helpButton.innerHTML = '<i data-lucide="circle-help"></i><span>Ajuda</span>';
        document.body.appendChild(helpButton);
        if (typeof lucide !== "undefined") lucide.createIcons();
        helpButton.addEventListener("click", () => {
            const modal = ensureConfirmModal();
            modal.querySelector(".system-modal-eyebrow").textContent = "AJUDA DA TELA";
            modal.querySelector("#systemModalTitle").textContent = currentHelp[1][0];
            modal.querySelector("#systemModalMessage").textContent = currentHelp[1][1];
            modal.querySelector(".modal-confirm").hidden = true;
            modal.querySelector(".modal-cancel").textContent = "Entendi";
            modal.hidden = false;
            document.body.classList.add("modal-open");
            modalResolve = () => {
                modal.querySelector(".system-modal-eyebrow").textContent = "CONFIRMAÇÃO";
                modal.querySelector("#systemModalTitle").textContent = "Confirmar ação";
                modal.querySelector(".modal-confirm").hidden = false;
                modal.querySelector(".modal-cancel").textContent = "Cancelar";
            };
            window.setTimeout(() => modal.querySelector(".modal-cancel")?.focus(), 20);
        });
    }

    const livePaths = [
        "/", "/dashboard", "/calendario", "/relatorios", "/historico",
        "/colaboradores", "/alertas", "/operacoes"
    ];
    const shouldWatchData = livePaths.some(path => (
        path === "/" ? window.location.pathname === "/" : window.location.pathname.startsWith(path)
    ));
    if (shouldWatchData) {
        const storageKey = "fokus-data-version";
        const checkDataVersion = async () => {
            if (document.hidden) return;
            try {
                const response = await fetch("/api/versao-dados", { cache: "no-store" });
                if (!response.ok) return;
                const { versao } = await response.json();
                const previous = sessionStorage.getItem(storageKey);
                sessionStorage.setItem(storageKey, versao);
                if (previous && versao && previous !== versao) {
                    showToast("Novos dados recebidos. Atualizando a tela...", "info", 1800);
                    window.setTimeout(() => window.location.reload(), 900);
                }
            } catch (_) {}
        };
        window.setTimeout(checkDataVersion, 1600);
        window.setInterval(checkDataVersion, 12000);
    }
});
