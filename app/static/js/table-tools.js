// Filter and sort a server-rendered table in the browser, without new requests.
//
// Filters: <form class="filters" data-table="ID" hidden> with radio groups. A row is shown
// when, for every group with a non-empty value, row.dataset[group name] equals it.
// An optional <input type="search" data-search-for="ID"> also hides rows that don't contain
// every typed word (anywhere in the row's text, ignoring case).
// An optional [data-count-for="ID"] element gets data-count-text with {shown} and {total}.
// Sorting: <table id="ID" class="sortable"> with <th data-sort="num|text|date"><button>.
// Each cell's sort value is its data-v attribute; empty values always sort last.
// Numbers and dates sort largest/newest first on the first click, text A-Z.
(function () {
  function setup(table) {
    const body = table.tBodies[0];
    const rows = Array.from(body.rows);
    const form = document.querySelector(`form[data-table="${table.id}"]`);
    const count = document.querySelector(`[data-count-for="${table.id}"]`);
    const empty = document.querySelector(`[data-empty-for="${table.id}"]`);
    const search = document.querySelector(`input[data-search-for="${table.id}"]`);
    const texts = new Map();
    const text = (row) => {
      if (!texts.has(row)) texts.set(row, row.textContent.toLowerCase());
      return texts.get(row);
    };

    function filter() {
      if (!form && !search) return;
      const wanted = form ? Array.from(form.querySelectorAll("input:checked")).filter((i) => i.value) : [];
      const words = search ? search.value.toLowerCase().split(/\s+/).filter(Boolean) : [];
      let shown = 0;
      for (const row of rows) {
        row.hidden = !(wanted.every((i) => row.dataset[i.name] === i.value)
          && words.every((word) => text(row).includes(word)));
        if (!row.hidden) shown += 1;
      }
      if (count) {
        count.textContent = (count.dataset.countText || "{shown} af {total}")
          .replace("{shown}", shown).replace("{total}", rows.length);
      }
      if (empty) empty.hidden = shown > 0;
    }

    function sortBy(th) {
      const index = Array.from(th.parentNode.children).indexOf(th);
      const type = th.dataset.sort;
      const firstDir = type === "text" ? "ascending" : "descending";
      const dir = th.getAttribute("aria-sort") === firstDir
        ? (firstDir === "ascending" ? "descending" : "ascending")
        : firstDir;
      table.querySelectorAll("th[aria-sort]").forEach((h) => h.removeAttribute("aria-sort"));
      th.setAttribute("aria-sort", dir);

      const value = (row) => row.cells[index].dataset.v || "";
      const sign = dir === "ascending" ? 1 : -1;
      const sorted = rows.slice().sort((a, b) => {
        const va = value(a), vb = value(b);
        if (!va || !vb) return (va ? 0 : 1) - (vb ? 0 : 1);
        const cmp = type === "num" ? Number(va) - Number(vb) : va.localeCompare(vb, "da");
        return cmp * sign;
      });
      body.append(...sorted);
    }

    table.querySelectorAll("th[data-sort] button").forEach((button) => {
      button.addEventListener("click", () => sortBy(button.closest("th")));
    });
    if (search) search.addEventListener("input", filter);
    if (form) {
      form.addEventListener("change", filter);
      form.hidden = false;
    }
    filter();
  }

  function init() {
    document.querySelectorAll("table.sortable[id]").forEach(setup);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
