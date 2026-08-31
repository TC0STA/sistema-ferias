const test = require("node:test");
const assert = require("node:assert/strict");

const {
    partitionEvents,
    overflowLabel,
    eventTypeLabel,
    selectHiddenEvent
} = require("../static/js/calendario_overflow.js");

const events = (count, tipo = "ferias") => Array.from(
    { length: count },
    (_, index) => ({ id: index + 1, nome: `Colaborador ${index + 1}`, tipo })
);

test("13 eventos exibem 3 e listam exatamente os 10 ocultos", () => {
    const allEvents = events(13);
    const partition = partitionEvents(allEvents);

    assert.deepEqual(partition.visible, allEvents.slice(0, 3));
    assert.deepEqual(partition.hidden, allEvents.slice(3));
    assert.equal(partition.hidden.length, 10);
    assert.equal(overflowLabel(partition.hidden.length), "+10 eventos");
});

test("4 eventos geram o singular e somente um item oculto", () => {
    const partition = partitionEvents(events(4));

    assert.equal(partition.visible.length, 3);
    assert.equal(partition.hidden.length, 1);
    assert.equal(overflowLabel(partition.hidden.length), "+1 evento");
});

test("um ou nenhum evento não gera indicador de excedente", () => {
    for (const count of [0, 1]) {
        const partition = partitionEvents(events(count));
        assert.equal(partition.hidden.length, 0);
        assert.equal(overflowLabel(partition.hidden.length), "");
        assert.deepEqual(partition.visible, events(count));
    }
});

test("eventos ocultos de retorno são preservados na listagem", () => {
    const allEvents = events(5, "retorno");
    const partition = partitionEvents(allEvents);

    assert.deepEqual(partition.hidden, allEvents.slice(3));
    assert.ok(partition.hidden.every((event) => event.tipo === "retorno"));
    assert.ok(partition.hidden.every((event) => eventTypeLabel(event) === "Retorno ao trabalho"));
});

test("selecionar colaborador oculto fecha a lista e abre o detalhe correto", () => {
    const selected = events(13)[8];
    const calls = [];

    selectHiddenEvent(
        selected,
        () => calls.push("close"),
        (event) => calls.push(["detail", event])
    );

    assert.deepEqual(calls, ["close", ["detail", selected]]);
});
