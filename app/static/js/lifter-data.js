// Data page (/data): filter, sort and draw every lifter from the JSON in the page.
// Filters live in the URL (?g=M&region=Fyn,Jylland&sin_min=250), so a view can be shared.
// Only filters, sorts and formats values; every number and flag comes from vl.v_lifter_data.
(function () {
  const PAGE = 100;
  const STEP = 5;
  // The site root, also when the static site is served under a sub-path (GitHub Pages).
  const base = new URL("../..", document.currentScript.src).pathname.replace(/\/$/, "");
  const data = JSON.parse(document.getElementById("data-lifters").textContent);
  const form = document.getElementById("data-filters");
  const classFilter = document.getElementById("class-filter");
  const sinOut = document.getElementById("sinclair-range");
  const sinMin = form.elements.sin_min;
  const sinMax = form.elements.sin_max;
  const table = document.getElementById("data-table");
  const body = table.tBodies[0];
  const count = document.getElementById("data-count");
  const empty = document.getElementById("data-empty");
  const more = document.getElementById("data-more");
  const STATUS = {
    active: (r) => r.active,
    former: (r) => !r.active,
  };

  let sortKey = "sin";
  let sortDir = -1;
  let shown = PAGE;

  const fmt = (v, decimals) => (v == null ? "–" : v.toFixed(decimals || 0).replace(".", ","));
  const classValue = (wc) => (wc ? Number(wc.slice(1)) + (wc[0] === "+" ? 0.5 : 0) : null);
  const radio = (name) => form.elements[name].value;
  const checked = (name) =>
    Array.from(form.querySelectorAll(`input[name="${name}"]:checked`), (i) => i.value);

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    if (text != null) node.textContent = text;
    return node;
  }

  // Weight classes for the chosen gender as words, lightest first, "+" class last.
  function fillClasses(gender, keep) {
    const classes = [...new Set(data.filter((r) => r.g === gender && r.wc).map((r) => r.wc))]
      .sort((a, b) => classValue(a) - classValue(b));
    classFilter.querySelectorAll("label:not(:first-of-type)").forEach((l) => l.remove());
    for (const wc of classes) {
      const label = el("label");
      label.append(el("input", { type: "radio", name: "wc", value: wc }), el("span", null, wc.replace("-", "−")));
      classFilter.append(label);
    }
    form.elements.wc.value = classes.includes(keep) ? keep : "";
  }

  // The Sinclair slider spans 0 to the best result for the chosen gender.
  function sliderBounds(gender) {
    const best = Math.max(...data.filter((r) => r.g === gender && r.sin != null).map((r) => r.sin));
    const top = Math.ceil(best / STEP) * STEP;
    for (const input of [sinMin, sinMax]) { input.min = 0; input.max = top; }
  }

  function sinRange() {
    const lo = Number(sinMin.value), hi = Number(sinMax.value);
    return { lo, hi, all: lo <= 0 && hi >= Number(sinMax.max) };
  }

  function showSinRange() {
    const { lo, hi, all } = sinRange();
    sinOut.textContent = all ? "alle" : `${lo}–${hi}`;
    const max = Number(sinMax.max) || 1;
    sinMin.parentNode.style.setProperty("--lo", `${(lo / max) * 100}%`);
    sinMin.parentNode.style.setProperty("--hi", `${(hi / max) * 100}%`);
  }

  function matcher() {
    const g = radio("g"), status = radio("status"), age = radio("age"), wc = radio("wc");
    const regions = checked("region");
    const sin = sinRange();
    return (r) =>
      r.g === g &&
      (!status || STATUS[status](r)) &&
      (!age || r.age === age) &&
      (!wc || r.wc === wc) &&
      (!regions.length || regions.includes(r.area)) &&
      (sin.all || (r.sin != null && r.sin >= sin.lo && r.sin <= sin.hi));
  }

  function compare(a, b) {
    const type = table.querySelector(`th[data-key="${sortKey}"]`).dataset.sort;
    let va = a[sortKey], vb = b[sortKey];
    if (type === "class") { va = classValue(va); vb = classValue(vb); }
    if (va == null || vb == null) return (va == null) - (vb == null);  // empty last
    const cmp = type === "text" ? String(va).localeCompare(String(vb), "da")
      : va < vb ? -1 : va > vb ? 1 : 0;
    return cmp * sortDir || a.name.localeCompare(b.name, "da");
  }

  function row(r) {
    const tr = el("tr");
    const name = el("td");
    name.append(el("a", { class: "name-link", href: `${base}/loefter/${r.id}` }, r.name));
    const sub = [r.club, r.wc && r.wc + " kg", r.active ? null : "inaktiv"].filter(Boolean);
    name.append(el("span", { class: "sub only-sm" }, sub.join(" · ")));
    tr.append(name);

    const club = el("td", { class: "hide-sm" });
    if (r.slug) club.append(el("a", { href: `${base}/klub/${r.slug}` }, r.club));
    else club.textContent = r.club || "–";
    tr.append(club);
    tr.append(el("td", { class: "hide-sm" }, r.area || "–"));
    tr.append(el("td", { class: "n hide-sm" }, r.wc ? r.wc.replace("-", "−") : "–"));
    tr.append(el("td", { class: "n" }, fmt(r.sn)));
    tr.append(el("td", { class: "n" }, fmt(r.cj)));
    tr.append(el("td", { class: "n hide-sm" }, fmt(r.tot)));
    const sin = el("td", { class: "n" });
    sin.append(el("b", null, fmt(r.sin, 1)));
    tr.append(sin);
    tr.append(el("td", { class: "n hide-sm" + (r.form ? "" : " faded") }, r.lastPrText || "–"));
    return tr;
  }

  function draw(resetPage) {
    if (resetPage) shown = PAGE;
    showSinRange();
    const rows = data.filter(matcher()).sort(compare);
    body.replaceChildren(...rows.slice(0, shown).map(row));
    count.textContent = `${rows.length} ${rows.length === 1 ? "løfter" : "løftere"}`;
    empty.hidden = rows.length > 0;
    more.hidden = rows.length <= shown;
    more.textContent = `Vis flere (${Math.min(PAGE, rows.length - shown)} af ${rows.length - shown})`;
    table.querySelectorAll("th[data-key]").forEach((th) => {
      if (th.dataset.key === sortKey) th.setAttribute("aria-sort", sortDir < 0 ? "descending" : "ascending");
      else th.removeAttribute("aria-sort");
    });
  }

  function saveUrl() {
    const s = new URLSearchParams();
    if (radio("g") === "M") s.set("g", "M");
    for (const name of ["status", "age", "wc"]) if (radio(name)) s.set(name, radio(name));
    const regions = checked("region");
    if (regions.length) s.set("region", regions.join(","));
    const sin = sinRange();
    if (!sin.all) { s.set("sin_min", sin.lo); s.set("sin_max", sin.hi); }
    if (sortKey !== "sin" || sortDir !== -1) s.set("sort", (sortDir < 0 ? "-" : "") + sortKey);
    const query = s.toString();
    history.replaceState(null, "", query ? `?${query}` : location.pathname);
  }

  function setGender(g, keepClass) {
    fillClasses(g, keepClass);
    sliderBounds(g);
    sinMin.value = sinMin.min;
    sinMax.value = sinMax.max;
  }

  function loadUrl() {
    const p = new URLSearchParams(location.search);
    const g = p.get("g") === "M" ? "M" : "F";
    form.elements.g.value = g;
    for (const name of ["status", "age"]) if (p.get(name)) form.elements[name].value = p.get(name);
    setGender(g, p.get("wc"));
    const regions = (p.get("region") || "").split(",");
    form.querySelectorAll('input[name="region"]').forEach((i) => { i.checked = regions.includes(i.value); });
    if (p.has("sin_min")) sinMin.value = p.get("sin_min");
    if (p.has("sin_max")) sinMax.value = p.get("sin_max");
    const sort = p.get("sort");
    const key = sort && sort.replace(/^-/, "");
    if (key && table.querySelector(`th[data-key="${key}"]`)) {
      sortKey = key;
      sortDir = sort.startsWith("-") ? -1 : 1;
    }
  }

  form.addEventListener("input", (e) => {
    if (e.target === sinMin && Number(sinMin.value) > Number(sinMax.value)) sinMin.value = sinMax.value;
    if (e.target === sinMax && Number(sinMax.value) < Number(sinMin.value)) sinMax.value = sinMin.value;
    if (e.target.name === "g") setGender(e.target.value, radio("wc"));
    draw(true);
    saveUrl();
  });
  document.getElementById("data-reset").addEventListener("click", () => {
    const g = radio("g");
    form.reset();
    form.elements.g.value = g;
    setGender(g, "");
    draw(true);
    saveUrl();
  });
  more.addEventListener("click", () => { shown += PAGE; draw(false); });
  table.querySelectorAll("th[data-key] button").forEach((button) => {
    button.addEventListener("click", () => {
      const th = button.closest("th");
      const key = th.dataset.key;
      if (key === sortKey) sortDir = -sortDir;
      else { sortKey = key; sortDir = th.dataset.sort === "text" ? 1 : -1; }
      draw(true);
      saveUrl();
    });
  });

  loadUrl();
  form.hidden = false;
  draw(true);
})();
