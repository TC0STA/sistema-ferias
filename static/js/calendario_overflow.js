(function (root, factory) {
    const overflow = factory();
    if (typeof module === "object" && module.exports) module.exports = overflow;
    root.CalendarOverflow = overflow;
}(typeof globalThis !== "undefined" ? globalThis : this, () => {
    const visibleLimit = 3;

    const partitionEvents = (events) => ({
        visible: events.slice(0, visibleLimit),
        hidden: events.slice(visibleLimit)
    });

    const overflowLabel = (hiddenCount) => (
        hiddenCount > 0
            ? `+${hiddenCount} evento${hiddenCount === 1 ? "" : "s"}`
            : ""
    );

    const eventTypeLabel = (event) => (
        event.tipo === "retorno" ? "Retorno ao trabalho" : "Férias"
    );

    const selectHiddenEvent = (event, closeList, openDetail) => {
        closeList();
        openDetail(event);
    };

    return {
        visibleLimit,
        partitionEvents,
        overflowLabel,
        eventTypeLabel,
        selectHiddenEvent
    };
}));
