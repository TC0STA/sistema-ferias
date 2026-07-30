document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector('form[action="/upload"]');
    const fileInput = document.getElementById("fileInput");
    const fileName = document.getElementById("fileName");
    const panel = document.getElementById("importValidation");
    const submitButton = document.getElementById("importSubmit");
    const cancelButton = document.getElementById("importCancel");
    const modeInputs = [...document.querySelectorAll('[name="modo_importacao"]')];
    if (!form || !fileInput || !panel || !submitButton) return;

    const buttonCopy = submitButton.querySelector("span");
    const escapeHtml = value => String(value ?? "").replace(
        /[&<>"']/g,
        character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        })[character]
    );

    const removeToken = () => {
        form.querySelector('[name="validacao_token"]')?.remove();
    };

    const selectedMode = () => (
        modeInputs.find(input => input.checked)?.value || "simulacao"
    );

    const initialButtonCopy = () => (
        selectedMode() === "simulacao"
            ? "Simular importação"
            : "Analisar planilha"
    );

    const resetValidation = () => {
        form.dataset.validated = "0";
        removeToken();
        panel.hidden = true;
        panel.innerHTML = "";
        submitButton.disabled = false;
        buttonCopy.textContent = initialButtonCopy();
        if (cancelButton) cancelButton.hidden = true;
    };

    const statusItem = (title, ok, value) => `
        <article class="${ok ? "is-valid" : "has-error"}">
            <i data-lucide="${ok ? "circle-check" : "circle-alert"}"></i>
            <span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(value)}</small></span>
        </article>
    `;

    const renderValidation = (data, duration) => {
        const comparison = data.comparacao;
        const summary = data.resumo || {};
        const period = summary.periodo || {};
        const previewRows = data.previa.map(item => `
            <tr>
                <td>${escapeHtml(item.nome)}</td>
                <td>${escapeHtml(item.matricula || "—")}</td>
                <td>${escapeHtml(item.inicio)}</td>
                <td>${escapeHtml(item.fim)}</td>
            </tr>
        `).join("");
        const errorRows = data.erros.map(item => `
            <li>
                <strong>Linha ${escapeHtml(item.linha)} · ${escapeHtml(item.campo)}</strong>
                <span>${escapeHtml(item.mensagem)}</span>
            </li>
        `).join("");
        const missing = data.estrutura.faltando.length
            ? `Faltando: ${data.estrutura.faltando.join(", ")}`
            : "Estrutura compatível";
        const dateMessage = data.datas.ok
            ? "Todas as datas são válidas"
            : `${data.datas.invalidas + data.datas.periodos_invertidos} problema(s)`;
        const fieldProblems = (
            data.campos_obrigatorios.nomes_vazios
            + data.campos_obrigatorios.matriculas_vazias
            + (data.campos_obrigatorios.departamentos_vazios || 0)
        );
        const altered = comparison.alterados ?? comparison.datas_alteradas ?? 0;
        const equal = comparison.iguais ?? comparison.sem_alteracoes ?? 0;
        const columns = (summary.colunas_identificadas || []).map(item => `
            ${statusItem(
                item.rotulo,
                item.identificada,
                item.coluna || "Não identificada"
            )}
        `).join("");
        const periodLabel = period.inicio && period.fim
            ? `${period.inicio} até ${period.fim}`
            : "Não disponível";

        panel.className = `import-validation ${data.pronta ? "is-ready" : "has-errors"}`;
        panel.innerHTML = `
            <header>
                <div>
                    <span>${data.simulacao ? "SIMULAÇÃO DA IMPORTAÇÃO" : "PREVIEW DA IMPORTAÇÃO"}</span>
                    <h2>${escapeHtml(data.arquivo)}</h2>
                    <p>${escapeHtml(data.registros)} registros analisados em ${escapeHtml(duration)}s</p>
                </div>
                <strong>${data.pronta ? "Pronta para importar" : `${data.total_erros} erro(s)`}</strong>
            </header>
            <div class="validation-status-grid">
                ${columns || statusItem("Estrutura", data.estrutura.ok, missing)}
                ${statusItem("Datas", data.datas.ok, dateMessage)}
                ${statusItem(
                    "Duplicidade",
                    data.duplicidade.ok,
                    `${data.duplicidade.total} registro(s)`
                )}
                ${statusItem(
                    "Campos obrigatórios",
                    data.campos_obrigatorios.ok,
                    fieldProblems ? `${fieldProblems} campo(s) vazio(s)` : "OK"
                )}
            </div>
            <section class="validation-statistics">
                <article><span>Registros encontrados</span><strong>${escapeHtml(summary.registros_encontrados ?? data.registros)}</strong></article>
                <article><span>Usuários únicos</span><strong>${escapeHtml(summary.usuarios_unicos ?? "Não disponível")}</strong></article>
                <article><span>Departamentos</span><strong>${escapeHtml(summary.departamentos ?? "Não disponível")}</strong></article>
                <article><span>Período encontrado</span><strong>${escapeHtml(periodLabel)}</strong></article>
                <article><span>Duplicados</span><strong>${escapeHtml(summary.duplicados ?? data.duplicidade.total)}</strong></article>
                <article><span>Datas inválidas</span><strong>${escapeHtml(summary.datas_invalidas ?? "Não disponível")}</strong></article>
            </section>
            <section class="validation-comparison">
                <div><span>Novos</span><strong>${escapeHtml(comparison.novos)}</strong></div>
                <div><span>Removidos</span><strong>${escapeHtml(comparison.removidos)}</strong></div>
                <div><span>Datas alteradas</span><strong>${escapeHtml(altered)}</strong></div>
                <div><span>Sem alterações</span><strong>${escapeHtml(equal)}</strong></div>
            </section>
            ${previewRows ? `
                <section class="validation-preview">
                    <h3>Pré-visualização dos primeiros registros</h3>
                    <div><table><thead><tr><th>Colaborador</th><th>Matrícula</th><th>Início</th><th>Fim</th></tr></thead><tbody>${previewRows}</tbody></table></div>
                </section>
            ` : ""}
            ${errorRows ? `
                <section class="validation-errors">
                    <h3>Problemas encontrados</h3>
                    <ul>${errorRows}</ul>
                    ${data.total_erros > data.erros.length
                        ? `<p>Outros ${data.total_erros - data.erros.length} erro(s) não exibidos.</p>`
                        : ""}
                </section>
            ` : ""}
            ${data.simulacao ? `
                <div class="simulation-notice">
                    <i data-lucide="shield-check"></i>
                    <strong>Simulação concluída. Nenhuma alteração foi gravada no banco ou no dashboard.</strong>
                </div>
            ` : ""}
            <footer>
                <i data-lucide="${data.pronta ? "badge-check" : "shield-alert"}"></i>
                <strong>${data.pronta
                    ? (data.simulacao
                        ? "Simulação concluída com segurança"
                        : "Planilha pronta para importação")
                    : "Corrija os problemas e analise o arquivo novamente"}</strong>
            </footer>
        `;
        panel.hidden = false;
        if (typeof lucide !== "undefined") lucide.createIcons();
    };

    fileInput.addEventListener("change", () => {
        fileName.textContent = fileInput.files[0]?.name || "Nenhum arquivo selecionado";
        resetValidation();
    });

    modeInputs.forEach(input => input.addEventListener("change", resetValidation));
    cancelButton?.addEventListener("click", () => {
        form.reset();
        fileName.textContent = "Nenhum arquivo selecionado";
        resetValidation();
    });

    form.addEventListener("submit", async event => {
        const mode = selectedMode();
        if (form.dataset.validated === "1" && mode === "definitivo") return;
        event.preventDefault();
        if (!fileInput.files.length) {
            fileInput.reportValidity();
            return;
        }

        submitButton.disabled = true;
        buttonCopy.textContent = mode === "simulacao"
            ? "Executando simulação..."
            : "Analisando planilha...";
        const payload = new FormData();
        payload.append("arquivo", fileInput.files[0]);
        payload.append("modo", mode);
        try {
            const response = await fetch("/api/importacao/validar", {
                method: "POST",
                body: payload
            });
            const result = await response.json();
            if (!response.ok || !result.ok) {
                throw new Error(result.mensagem || "Não foi possível analisar a planilha.");
            }
            renderValidation(result.validacao, result.duracao_segundos);
            if (result.validacao.pronta && mode === "definitivo") {
                const token = document.createElement("input");
                token.type = "hidden";
                token.name = "validacao_token";
                token.value = result.token;
                form.appendChild(token);
                form.dataset.validated = "1";
                buttonCopy.textContent = "Confirmar importação";
                if (cancelButton) cancelButton.hidden = false;
                window.FokusToast?.("Planilha validada e pronta para importar.", "success");
            } else if (result.validacao.pronta) {
                form.dataset.validated = "0";
                buttonCopy.textContent = "Executar nova simulação";
                if (cancelButton) cancelButton.hidden = false;
                window.FokusToast?.(
                    "Simulação concluída. Nenhuma alteração foi gravada.",
                    "success"
                );
            } else {
                form.dataset.validated = "0";
                buttonCopy.textContent = mode === "simulacao"
                    ? "Simular novamente"
                    : "Analisar novamente";
                if (cancelButton) cancelButton.hidden = false;
                window.FokusToast?.(
                    `Foram encontrados ${result.validacao.total_erros} erro(s) na planilha.`,
                    "warning"
                );
            }
        } catch (error) {
            form.dataset.validated = "0";
            buttonCopy.textContent = mode === "simulacao"
                ? "Simular novamente"
                : "Analisar novamente";
            window.FokusToast?.(error.message, "error");
        } finally {
            submitButton.disabled = false;
        }
    });
});
