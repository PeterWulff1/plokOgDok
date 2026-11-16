// Day and night. Loaded in <head> without defer, so the theme is set before the page paints
// (no flash of the wrong one). The visitor's choice is kept in localStorage; until they
// choose, the site follows the device's setting. site.css holds both palettes.
(() => {
  const KEY = "pod-theme";
  const root = document.documentElement;
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let chosen = null;
  try {
    chosen = localStorage.getItem(KEY);
  } catch (e) { /* private mode: follow the device */ }
  if (chosen !== "dark" && chosen !== "light") chosen = null;

  function apply() {
    root.dataset.theme = chosen || (system.matches ? "dark" : "light");
    const button = document.getElementById("theme-toggle");
    if (button) {
      const dark = root.dataset.theme === "dark";
      button.textContent = dark ? "Dag" : "Nat";
      button.setAttribute("aria-label", dark ? "Skift til dagtilstand" : "Skift til nattilstand");
      button.hidden = false;
    }
    // Charts read their colours from the palette and redraw (static/js/progression.js).
    document.dispatchEvent(new Event("themechange"));
  }

  apply();
  system.addEventListener("change", () => { if (!chosen) apply(); });
  document.addEventListener("DOMContentLoaded", () => {
    apply();
    const button = document.getElementById("theme-toggle");
    if (!button) return;
    button.addEventListener("click", () => {
      chosen = root.dataset.theme === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(KEY, chosen);
      } catch (e) { /* still switches for this page */ }
      apply();
    });
  });
})();
