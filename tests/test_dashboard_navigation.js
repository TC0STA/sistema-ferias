const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const NavigationFeedback = require("../static/js/navigation_feedback.js");

const classList = (...initial) => {
    const values = new Set(initial);
    return {
        add: (name) => values.add(name),
        remove: (name) => values.delete(name),
        contains: (name) => values.has(name)
    };
};

const element = (classes = []) => ({
    classList: classList(...classes),
    dataset: {},
    attributes: new Map(),
    style: {
        properties: new Map(),
        setProperty(name, value) { this.properties.set(name, value); }
    },
    handlers: {},
    offsetWidth: 100,
    addEventListener(name, callback) { this.handlers[name] = callback; },
    hasAttribute(name) { return this.attributes.has(name); },
    setAttribute(name, value) { this.attributes.set(name, value); },
    closest() { return null; },
    scrollIntoView(options) { this.scrollOptions = options; },
    focus(options) { this.focusOptions = options; }
});

const setup = (reducedMotion = false) => {
    const todos = element(["metric-card", "metric-blue"]);
    todos.dataset.target = "todos-usuarios";
    todos.attributes.set("data-navigation-feedback", "");
    const iniciando = element(["metric-card", "metric-cyan"]);
    iniciando.dataset.target = "tabela-hoje";
    iniciando.attributes.set("data-navigation-feedback", "");
    const proximas = element(["metric-card", "metric-orange"]);
    proximas.dataset.target = "proximas-ferias";
    proximas.attributes.set("data-navigation-feedback", "");
    const pendencias = element(["metric-card", "metric-red"]);
    pendencias.dataset.target = "tabela-hoje";
    pendencias.attributes.set("data-navigation-feedback", "");
    const emFerias = element(["metric-card", "metric-green"]);
    emFerias.dataset.href = "/calendario?focus=hoje";
    emFerias.attributes.set("data-navigation-feedback", "");
    const todosTarget = element(["table-card"]);
    const hojeTarget = element(["table-card"]);
    const proximasTarget = element(["dashboard-card"]);
    const timers = [];
    const locations = [];
    let ready;

    const browserWindow = {
        FokusNavigationFeedback: NavigationFeedback,
        matchMedia: () => ({ matches: reducedMotion }),
        getComputedStyle(control) {
            const colors = [
                ["metric-blue", "#2563eb"],
                ["metric-cyan", "#0891b2"],
                ["metric-orange", "#f59e0b"],
                ["metric-red", "#dc2626"]
            ];
            const color = colors.find(([className]) => control.classList.contains(className))?.[1] || "";
            return { getPropertyValue: () => color };
        },
        requestAnimationFrame: (callback) => callback(),
        setTimeout: (callback, duration) => { timers.push({ callback, duration }); },
        location: { assign: (url) => locations.push(url), reload() {} }
    };
    const document = {
        addEventListener(name, callback) { if (name === "DOMContentLoaded") ready = callback; },
        getElementById(id) {
            return { "todos-usuarios": todosTarget, "tabela-hoje": hojeTarget, "proximas-ferias": proximasTarget }[id] || null;
        },
        querySelectorAll(selector) {
            if (selector === "[data-target]") return [todos, iniciando, proximas, pendencias];
            if (selector === "[data-href]") return [emFerias];
            return [];
        },
        body: { classList: classList() }
    };

    const source = fs.readFileSync(path.join(__dirname, "../static/js/dashboard.js"), "utf8");
    vm.runInNewContext(source, { window: browserWindow, document });
    ready();

    return { todos, iniciando, proximas, pendencias, emFerias, todosTarget, hojeTarget, proximasTarget, timers, locations };
};

test("template mantém os cinco cards no feedback e em seus destinos atuais", () => {
    const template = fs.readFileSync(path.join(__dirname, "../templates/dashboard.html"), "utf8");

    assert.match(template, /metric-blue[^>]+data-navigation-feedback[^>]+data-target="todos-usuarios"/);
    assert.match(template, /metric-green[^>]+data-navigation-feedback[^>]+data-href="\/calendario\?focus=hoje"/);
    assert.match(template, /metric-cyan[^>]+data-navigation-feedback[^>]+data-target="tabela-hoje"/);
    assert.match(template, /metric-orange[^>]+data-navigation-feedback[^>]+data-target="proximas-ferias"/);
    assert.match(template, /metric-red[^>]+data-navigation-feedback[^>]+data-target="tabela-hoje"/);
});

test("dashboard remove importações e mantém detalhamento operacional aberto", () => {
    const template = fs.readFileSync(path.join(__dirname, "../templates/dashboard.html"), "utf8");
    const cardIds = ["tabela-hoje", "tabela-proximos", "todos-usuarios", "tabela-historico"];
    const positions = cardIds.map((id) => template.indexOf(`id="${id}"`));

    assert.doesNotMatch(template, /class="dashboard-card imports-card"/);
    assert.doesNotMatch(template, /<details[^>]+class="operational-details"/);
    assert.doesNotMatch(template, /data-lucide="chevron-down"/);
    assert.match(template, /<section class="operational-details" id="calendario">/);
    assert.ok(positions.every((position) => position >= 0));
    assert.deepEqual(positions, [...positions].sort((a, b) => a - b));
});

test("layout mantém hierarquia e destaque dos cards do dashboard", () => {
    const stylesheet = fs.readFileSync(path.join(__dirname, "../static/css/dashboard.css"), "utf8");

    assert.match(stylesheet, /\.metric-grid\s*\{[^}]*grid-template-columns:\s*repeat\(5,/);
    assert.match(stylesheet, /\.upcoming-card, \.chart-card\s*\{\s*grid-column:\s*1 \/ -1;/);
    assert.match(stylesheet, /\.chart-wrapper\s*\{[^}]*height:\s*clamp\(280px, 28vw, 350px\);/);
    assert.match(stylesheet, /\.tables-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,/);
    assert.match(stylesheet, /\.table-card\s*\{[^}]*min-height:\s*280px;/);
    assert.match(stylesheet, /\.table-card\.highlight\s*\{\s*animation:\s*dashboard-table-highlight 3s ease;/);
    assert.match(stylesheet, /#todos-usuarios\s*\{\s*--table-highlight-color:\s*var\(--dash-blue\);/);
    assert.match(stylesheet, /#tabela-hoje\s*\{\s*--table-highlight-color:\s*var\(--dash-red\);/);
    assert.match(stylesheet, /@media \(prefers-reduced-motion: reduce\)[\s\S]+\.table-card\.highlight\s*\{\s*outline-color:\s*var\(--table-highlight-color\);/);
});

const assertInternalCardFeedback = (card, target, expectedColor) => {
    card.handlers.click();
    card.handlers.click();

    assert.equal(card.classList.contains("is-selected"), true);
    assert.equal(target.classList.contains("highlight"), true);
    assert.equal(target.scrollOptions.behavior, "smooth");
    if (expectedColor) {
        assert.equal(target.style.properties.get("--table-highlight-color"), expectedColor);
    }
};

test("Total de colaboradores preserva o destino e repete os dois destaques", () => {
    const { todos, todosTarget } = setup();
    assertInternalCardFeedback(todos, todosTarget, "#2563eb");
});

test("Iniciando hoje preserva o destino e repete os dois destaques", () => {
    const { iniciando, hojeTarget } = setup();
    assertInternalCardFeedback(iniciando, hojeTarget, "#0891b2");
});

test("Próximas férias preserva o destino e repete os dois destaques", () => {
    const { proximas, proximasTarget } = setup();
    assertInternalCardFeedback(proximas, proximasTarget);
    assert.equal(proximasTarget.style.properties.has("--table-highlight-color"), false);
});

test("Pendências preserva o destino e repete os dois destaques", () => {
    const { pendencias, hojeTarget } = setup();
    assertInternalCardFeedback(pendencias, hojeTarget, "#dc2626");
});

test("card Em férias destaca antes de abrir o calendário focado em hoje", () => {
    const { emFerias, timers, locations } = setup();

    emFerias.handlers.click();
    emFerias.handlers.click();
    const navigationTimer = timers.find(({ duration }) => duration === 700);

    assert.equal(emFerias.classList.contains("is-selected"), true);
    assert.equal(emFerias.attributes.get("aria-busy"), "true");
    assert.ok(navigationTimer);
    assert.equal(timers.filter(({ duration }) => duration === 700).length, 2);
    navigationTimer.callback();
    assert.deepEqual(locations, ["/calendario?focus=hoje"]);
});

test("movimento reduzido mantém os destaques e evita scroll e espera animados", () => {
    const { todos, todosTarget, emFerias, timers } = setup(true);

    todos.handlers.click();
    emFerias.handlers.click();

    assert.equal(todos.classList.contains("is-selected"), true);
    assert.equal(todosTarget.classList.contains("highlight"), true);
    assert.equal(todosTarget.scrollOptions.behavior, "auto");
    assert.ok(timers.some(({ duration }) => duration === 180));
});
