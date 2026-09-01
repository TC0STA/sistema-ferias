(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else root.FokusNavigationFeedback = api;
}(typeof globalThis !== "undefined" ? globalThis : this, () => {
    const create = (browserWindow) => {
        const reducedMotion = browserWindow.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const activeHighlights = new WeakMap();

        const restart = (element, className, duration) => {
            const highlightToken = {};
            activeHighlights.set(element, highlightToken);
            element.classList.remove(className);
            void element.offsetWidth;
            element.classList.add(className);
            browserWindow.setTimeout(() => {
                if (activeHighlights.get(element) !== highlightToken) return;
                element.classList.remove(className);
                activeHighlights.delete(element);
            }, duration);
        };

        const reveal = (element, options = {}) => {
            const {
                className = "highlight",
                duration = 2600,
                block = "center",
                inline = "nearest"
            } = options;

            restart(element, className, duration);
            element.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block, inline });
            if (!element.hasAttribute("tabindex")) element.setAttribute("tabindex", "-1");
            element.focus({ preventScroll: true });
        };

        return { reducedMotion, restart, reveal };
    };

    return { create };
}));
