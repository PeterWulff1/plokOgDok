// Front-page search for the static site (GitHub Pages), where there's no /sog endpoint.
// Loads the prebuilt index once and renders the same markup as partials/search_results.html.
// Matching mirrors the server: clubs ignore case and Danish spelling (core.clubs.match_clubs),
// lifters match a case-insensitive substring of the name, most recently active first.
(() => {
  const input = document.getElementById("q");
  const out = document.getElementById("search-results");
  if (!input || !out || !input.dataset.index) return;

  // The site may live under a sub-path (/plokOgDok/); links in the index are root-relative.
  const base = new URL("../..", document.currentScript.src).pathname.replace(/\/$/, "");
  let index = null;

  const fold = (text) =>
    text.trim().toLowerCase()
      .replace(/æ/g, "ae").replace(/ø/g, "oe").replace(/å/g, "aa")
      .normalize("NFKD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function hit(href, who, meta, pr, prLabel) {
    const a = el("a");
    a.href = base + href;
    a.append(el("span", "who", who), el("span", "meta", meta));
    const p = el("span", "pr", pr);
    p.append(el("small", null, prLabel));
    a.append(p);
    return a;
  }

  function render(q) {
    out.replaceChildren();
    const folded = fold(q);
    if (q.trim().length < 2 || folded.length < 2) return;
    const lower = q.trim().toLowerCase();

    const clubs = index.clubs
      .filter((c) => fold(c.club).includes(folded))
      .sort((a, b) => fold(b.club).startsWith(folded) - fold(a.club).startsWith(folded))
      .slice(0, 4);
    const lifters = index.lifters
      .filter((l) => l.name.toLowerCase().includes(lower))
      .sort((a, b) => b.name.toLowerCase().startsWith(lower) - a.name.toLowerCase().startsWith(lower))
      .slice(0, 8);

    if (clubs.length) {
      out.append(el("div", "group-label", "Klubber"));
      for (const c of clubs) {
        out.append(hit(`/klub/${c.slug}`, c.club, `${c.active} aktive · sidst ${c.last}`, c.lifters, "løftere"));
      }
      if (lifters.length) out.append(el("div", "group-label", "Løftere"));
    }
    for (const l of lifters) {
      out.append(hit(`/loefter/${l.id}`, l.name, `${l.club || "Ukendt klub"} · sidst ${l.last}`, l.pr, "bedste total"));
    }
    if (!clubs.length && !lifters.length) {
      out.append(el("div", "none", `Ingen løftere eller klubber matcher “${q.trim()}”.`));
    }
  }

  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (!index) {
        const r = await fetch(base + input.dataset.index);
        index = await r.json();
      }
      render(input.value);
    }, 150);
  });
})();
