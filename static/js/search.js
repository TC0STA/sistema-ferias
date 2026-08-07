(() => {
    if (window.__fokusGlobalSearchLoaded) return;
    window.__fokusGlobalSearchLoaded = true;

    document.addEventListener("DOMContentLoaded", () => {
        const modal = document.getElementById("globalSearchModal");
        const button = document.getElementById("globalSearchButton");
        const input = document.getElementById("globalSearchInput");
        const results = document.getElementById("globalSearchResults");
        const spinner = document.getElementById("globalSearchSpinner");
        const fullSearchLink = document.getElementById("fullSearchLink");
        if (!modal || !button || !input || !results) return;

        const startContent = results.innerHTML;
        const categoryMeta = {
            colaboradores: { label: "Colaboradores", icon: "user-round" },
            organizacao: { label: "Departamentos e filiais", icon: "building-2" },
            importacoes: { label: "Importações", icon: "file-spreadsheet" },
            calendario: { label: "Calendário", icon: "calendar-days" },
            historico: { label: "Histórico", icon: "history" },
            auditoria: { label: "Auditoria", icon: "scroll-text" },
            relatorios: { label: "Relatórios", icon: "chart-no-axes-combined" },
            configuracoes: { label: "Configurações", icon: "settings-2" }
        };

        let debounceTimer = null;
        let selectedIndex = -1;
        let requestController = null;
        let previousFocus = null;

        const escapeHtml = (value = "") => String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");

        const options = () => [...results.querySelectorAll("[data-search-option]")];

        const selectOption = (index) => {
            const items = options();
            items.forEach((item) => item.classList.remove("is-selected"));
            if (!items.length) {
                selectedIndex = -1;
                input.removeAttribute("aria-activedescendant");
                return;
            }
            selectedIndex = ((index % items.length) + items.length) % items.length;
            const selected = items[selectedIndex];
            selected.classList.add("is-selected");
            if (!selected.id) selected.id = `global-search-option-${selectedIndex}`;
            input.setAttribute("aria-activedescendant", selected.id);
            selected.scrollIntoView({ block: "nearest" });
        };

        const refreshIcons = () => {
            if (typeof lucide !== "undefined") lucide.createIcons();
        };

        const resetSearch = () => {
            window.clearTimeout(debounceTimer);
            requestController?.abort();
            requestController = null;
            spinner.hidden = true;
            input.value = "";
            results.innerHTML = startContent;
            selectedIndex = -1;
            fullSearchLink.href = "/pesquisa";
            refreshIcons();
        };

        const openModal = () => {
            if (!modal.hidden) return;
            previousFocus = document.activeElement;
            modal.hidden = false;
            button.setAttribute("aria-expanded", "true");
            document.body.classList.add("search-modal-open");
            window.requestAnimationFrame(() => input.focus());
        };

        const closeModal = () => {
            if (modal.hidden) return;
            modal.hidden = true;
            button.setAttribute("aria-expanded", "false");
            document.body.classList.remove("search-modal-open");
            resetSearch();
            previousFocus?.focus?.();
        };

        const renderLoading = () => {
            results.innerHTML = '<div class="search-loading-state" aria-label="Pesquisando"><span></span><span></span><span></span><span></span></div>';
            selectedIndex = -1;
            spinner.hidden = false;
        };

        const renderEmpty = (query) => {
            results.innerHTML = `
                <div class="search-empty-state">
                    <span><i data-lucide="search-x"></i></span>
                    <strong>Nenhum resultado encontrado</strong>
                    <small>Não encontramos informações para “${escapeHtml(query)}”. Tente outro nome, filial, departamento ou termo.</small>
                </div>`;
            selectedIndex = -1;
            refreshIcons();
        };

        const extractGroups = (html) => {
            const page = new DOMParser().parseFromString(html, "text/html");
            return [...page.querySelectorAll(".search-page-group[data-category]")]
                .map((group) => ({
                    category: group.dataset.category,
                    links: [...group.querySelectorAll(".search-result-link")].map((link) => ({
                        href: link.getAttribute("href"),
                        title: link.querySelector("strong")?.textContent?.trim() || "Resultado",
                        description: link.querySelector("small")?.textContent?.trim() || "Abrir no sistema"
                    }))
                }))
                .filter((group) => group.links.length);
        };

        const renderGroups = (groups) => {
            results.innerHTML = `<div class="command-results">${groups.map((group) => {
                const meta = categoryMeta[group.category] || { label: group.category, icon: "search" };
                return `
                    <section class="command-result-group">
                        <header><span>${escapeHtml(meta.label).toUpperCase()}</span><small>${group.links.length} resultado${group.links.length === 1 ? "" : "s"}</small></header>
                        <div>${group.links.map((item) => `
                            <a class="search-result-link" href="${escapeHtml(item.href)}" data-search-option>
                                <span class="search-result-icon category-${escapeHtml(group.category)}"><i data-lucide="${escapeHtml(meta.icon)}"></i></span>
                                <span class="search-result-copy"><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.description)}</small></span>
                                <i data-lucide="arrow-up-right"></i>
                            </a>`).join("")}
                        </div>
                    </section>`;
            }).join("")}</div>`;
            selectedIndex = -1;
            refreshIcons();
        };

        const performSearch = async (query) => {
            requestController?.abort();
            requestController = new AbortController();
            renderLoading();

            try {
                const url = `/pesquisa?q=${encodeURIComponent(query)}&modal=1`;
                const response = await fetch(url, {
                    signal: requestController.signal,
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                    cache: "no-store"
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const groups = extractGroups(await response.text());
                if (input.value.trim() !== query) return;
                groups.length ? renderGroups(groups) : renderEmpty(query);
            } catch (error) {
                if (error.name === "AbortError") return;
                results.innerHTML = `
                    <div class="search-empty-state">
                        <span><i data-lucide="wifi-off"></i></span>
                        <strong>Não foi possível pesquisar agora</strong>
                        <small>Use a pesquisa completa para continuar.</small>
                    </div>`;
                refreshIcons();
            } finally {
                if (input.value.trim() === query) spinner.hidden = true;
            }
        };

        input.addEventListener("input", () => {
            const query = input.value.trim();
            window.clearTimeout(debounceTimer);
            requestController?.abort();
            selectedIndex = -1;
            fullSearchLink.href = query ? `/pesquisa?q=${encodeURIComponent(query)}` : "/pesquisa";

            if (!query) {
                results.innerHTML = startContent;
                spinner.hidden = true;
                refreshIcons();
                return;
            }
            if (query.length < 2) {
                results.innerHTML = `
                    <div class="search-empty-state">
                        <span><i data-lucide="text-cursor-input"></i></span>
                        <strong>Continue digitando</strong>
                        <small>Digite pelo menos dois caracteres para pesquisar em todo o sistema.</small>
                    </div>`;
                spinner.hidden = true;
                refreshIcons();
                return;
            }
            debounceTimer = window.setTimeout(() => performSearch(query), 280);
        });

        input.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown") {
                event.preventDefault();
                selectOption(selectedIndex + 1);
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                selectOption(selectedIndex - 1);
            } else if (event.key === "Enter") {
                event.preventDefault();
                const selected = options()[selectedIndex];
                if (selected) window.location.assign(selected.href);
                else if (input.value.trim()) window.location.assign(fullSearchLink.href);
            }
        });

        results.addEventListener("mousemove", (event) => {
            const target = event.target.closest?.("[data-search-option]");
            if (!target) return;
            const index = options().indexOf(target);
            if (index !== -1 && index !== selectedIndex) selectOption(index);
        });

        button.addEventListener("click", (event) => {
            event.stopPropagation();
            openModal();
        });
        modal.querySelectorAll("[data-search-close]").forEach((control) => control.addEventListener("click", closeModal));

        document.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                event.stopImmediatePropagation();
                openModal();
            }
            if (event.key === "Escape" && !modal.hidden) {
                event.preventDefault();
                closeModal();
            }
        }, true);
    });
})();
