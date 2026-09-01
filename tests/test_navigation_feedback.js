const test = require("node:test");
const assert = require("node:assert/strict");

const { create } = require("../static/js/navigation_feedback.js");

const fixture = (reducedMotion = false) => {
    const classes = new Set();
    const history = [];
    const timers = [];
    const element = {
        classList: {
            add: (name) => { classes.add(name); history.push(["add", name]); },
            remove: (name) => { classes.delete(name); history.push(["remove", name]); }
        },
        offsetWidth: 100,
        attributes: new Map(),
        hasAttribute(name) { return this.attributes.has(name); },
        setAttribute(name, value) { this.attributes.set(name, value); },
        scrollIntoView(options) { this.scrollOptions = options; },
        focus(options) { this.focusOptions = options; }
    };
    const browserWindow = {
        matchMedia: () => ({ matches: reducedMotion }),
        setTimeout: (callback, duration) => { timers.push({ callback, duration }); }
    };

    return { feedback: create(browserWindow), element, classes, history, timers };
};

test("reinicia o destaque a cada clique e o remove no tempo configurado", () => {
    const { feedback, element, classes, history, timers } = fixture();

    feedback.restart(element, "is-selected", 1000);
    feedback.restart(element, "is-selected", 1000);

    assert.equal(history.filter(([action]) => action === "add").length, 2);
    assert.deepEqual(timers.map(({ duration }) => duration), [1000, 1000]);
    timers[0].callback();
    assert.equal(classes.has("is-selected"), true);
    timers.at(-1).callback();
    assert.equal(classes.has("is-selected"), false);
});

test("destino recebe scroll suave, foco e destaque temporário", () => {
    const { feedback, element, classes, timers } = fixture();

    feedback.reveal(element, { className: "navigation-highlight", duration: 3200 });

    assert.equal(classes.has("navigation-highlight"), true);
    assert.deepEqual(element.scrollOptions, { behavior: "smooth", block: "center", inline: "nearest" });
    assert.deepEqual(element.focusOptions, { preventScroll: true });
    assert.equal(element.attributes.get("tabindex"), "-1");
    assert.equal(timers[0].duration, 3200);
    timers[0].callback();
    assert.equal(classes.has("navigation-highlight"), false);
});

test("movimento reduzido troca o scroll animado por posicionamento imediato", () => {
    const { feedback, element } = fixture(true);

    feedback.reveal(element);

    assert.equal(feedback.reducedMotion, true);
    assert.equal(element.scrollOptions.behavior, "auto");
});
