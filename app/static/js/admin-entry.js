// Entry grid on the admin page: name autocomplete, keyboard flow and attempt colours.
//
// Autocomplete: typing in a name cell asks /admin/loeftere?q=… for matching lifters. Picking
// one stores its id in the row's hidden lifter_id and fills gender, birth year, club and class
// from the lifter's latest competition. Those cells then drop out of the Tab order, so the
// path is name → bodyweight → T1 … S3. Typing a different name forgets the pick and clears
// the cells it filled, unless they were changed by hand.
// Keys in the list: ↑/↓ move, Enter picks, Esc closes. Elsewhere in the grid, Enter moves to
// the next row's name (adding a row at the end) instead of submitting the form.
// Attempt cells turn green or red as you type, using the same notation as
// core/manual_entry.py: "95" made, "95x" or "-95" missed.
(function () {
  const grid = document.getElementById("entry-grid");
  if (!grid) return;
  const body = grid.tBodies[0];
  const FILLED = ["køn", "fødselsår", "klub", "vægtklasse"];
  const ATTEMPTS = ["t1", "t2", "t3", "s1", "s2", "s3"];
  const ATTEMPT_RE = /^\s*(-)?\s*(\d{1,3})\s*([xX])?\s*$/;

  const cell = (row, col) => row.querySelector(`[data-col="${col}"]`);

  // --- Attempt colours ---------------------------------------------------------------

  function colour(input) {
    const m = ATTEMPT_RE.exec(input.value);
    const valid = m && !(m[1] && m[3]) && Number(m[2]) > 0;
    input.classList.toggle("att-made", Boolean(valid && !m[1] && !m[3]));
    input.classList.toggle("att-miss", Boolean(valid && (m[1] || m[3])));
  }

  // --- Picking and forgetting a lifter ------------------------------------------------

  function markFilled(input) {
    input.dataset.auto = "1";
    input.tabIndex = -1;
  }

  function unmark(input) {
    delete input.dataset.auto;
    input.removeAttribute("tabindex");
  }

  function pick(row, lifter) {
    const name = cell(row, "navn");
    name.value = lifter.name;
    name.classList.add("linked");
    cell(row, "lifter_id").value = lifter.id;
    row.dataset.picked = lifter.name;
    const values = { "køn": lifter.gender, "fødselsår": lifter.birth_year,
                     "klub": lifter.club, "vægtklasse": lifter.weight_class };
    for (const col of FILLED) {
      const input = cell(row, col);
      input.value = values[col];
      markFilled(input);
    }
    close();
    cell(row, "kropsvægt").focus();
  }

  function forget(row) {
    cell(row, "lifter_id").value = "";
    cell(row, "navn").classList.remove("linked");
    delete row.dataset.picked;
    for (const col of FILLED) {
      const input = cell(row, col);
      if (input.dataset.auto) {
        input.value = "";
        unmark(input);
      }
    }
  }

  // --- Suggestion list ----------------------------------------------------------------

  const list = document.createElement("ul");
  list.id = "lifter-suggestions";
  list.className = "suggest";
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", "Løftere");
  list.hidden = true;
  document.body.appendChild(list);

  let owner = null; // the name input the list belongs to
  let pending = null; // the name input with a search waiting or in flight
  let results = [];
  let index = -1;
  let timer = null;
  let controller = null;

  function cancelSearch() {
    clearTimeout(timer);
    if (controller) controller.abort();
    pending = null;
  }

  function highlight(i) {
    index = i;
    Array.from(list.children).forEach((li, j) => li.setAttribute("aria-selected", String(j === i)));
    if (i >= 0) owner.setAttribute("aria-activedescendant", `suggest-${i}`);
    else owner.removeAttribute("aria-activedescendant");
  }

  function place() {
    const rect = owner.getBoundingClientRect();
    list.style.minWidth = `${Math.max(rect.width, 260)}px`;
    const left = Math.max(16, Math.min(rect.left, window.innerWidth - list.offsetWidth - 16));
    list.style.left = `${left + window.scrollX}px`;
    list.style.top = `${rect.bottom + window.scrollY + 2}px`;
  }

  function open(input, found) {
    owner = input;
    results = found;
    list.replaceChildren();
    if (!found.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "Ingen fundet. Ny løfter: udfyld køn og født.";
      list.appendChild(li);
    }
    found.forEach((lifter, i) => {
      const li = document.createElement("li");
      li.id = `suggest-${i}`;
      li.setAttribute("role", "option");
      const name = document.createElement("b");
      name.textContent = lifter.name;
      const sub = document.createElement("span");
      sub.className = "sub";
      sub.textContent = [lifter.club || "ukendt klub",
                         lifter.birth_year ? `f. ${lifter.birth_year}` : "",
                         lifter.weight_class].filter(Boolean).join(" · ");
      li.append(name, sub);
      li.addEventListener("mousedown", (event) => {
        event.preventDefault(); // keep focus in the name cell
        pick(input.closest("tr"), lifter);
      });
      list.appendChild(li);
    });
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    highlight(found.length ? 0 : -1);
    place();
  }

  function close() {
    if (pending === owner) cancelSearch(); // leave a search in another row alone
    list.hidden = true;
    results = [];
    index = -1;
    if (owner) {
      owner.setAttribute("aria-expanded", "false");
      owner.removeAttribute("aria-activedescendant");
    }
  }

  function search(input) {
    cancelSearch();
    const q = input.value.trim();
    if (q.length < 2) return close();
    pending = input;
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const r = await fetch(`/admin/loeftere?q=${encodeURIComponent(q)}`,
                              { signal: controller.signal, headers: { Accept: "application/json" } });
        const found = r.ok ? await r.json() : null;
        if (pending !== input) return; // superseded while waiting
        pending = null;
        if (found && document.activeElement === input) open(input, found);
        else close();
      } catch (err) {
        if (err.name !== "AbortError" && pending === input) {
          pending = null;
          close();
        }
      }
    }, 150);
  }

  // --- Rows ---------------------------------------------------------------------------

  function setupRow(row) {
    cell(row, "vlstat_id").tabIndex = -1; // rarely needed now that names autocomplete
    const name = cell(row, "navn");
    name.setAttribute("role", "combobox");
    name.setAttribute("aria-autocomplete", "list");
    name.setAttribute("aria-controls", list.id);
    name.setAttribute("aria-expanded", "false");
    ATTEMPTS.forEach((col) => colour(cell(row, col)));
    if (cell(row, "lifter_id").value) { // re-rendered after a validation error
      row.dataset.picked = name.value;
      name.classList.add("linked");
      FILLED.forEach((col) => cell(row, col).value && markFilled(cell(row, col)));
    }
  }

  function addRow() {
    const last = body.lastElementChild;
    const n = body.children.length;
    const row = last.cloneNode(true);
    delete row.dataset.picked;
    row.querySelectorAll("input").forEach(function (input) {
      input.name = input.name.replace(/^rows-\d+-/, "rows-" + n + "-");
      if (input.hasAttribute("aria-label")) {
        input.setAttribute("aria-label", input.getAttribute("aria-label").replace(/\d+$/, n + 1));
      }
      input.value = "";
      input.classList.remove("linked", "att-made", "att-miss");
      if (input.dataset.auto) unmark(input);
    });
    body.appendChild(row);
    setupRow(row);
    return row;
  }

  Array.from(body.rows).forEach(setupRow);

  document.getElementById("add-row").addEventListener("click", function () {
    cell(addRow(), "navn").focus();
  });

  body.addEventListener("input", function (event) {
    const input = event.target;
    const col = input.dataset.col;
    const row = input.closest("tr");
    if (col === "navn") {
      if (row.dataset.picked !== undefined && input.value !== row.dataset.picked) forget(row);
      search(input);
    } else if (ATTEMPTS.includes(col)) {
      colour(input);
    } else if (input.dataset.auto) {
      delete input.dataset.auto; // changed by hand: keep it if the name changes later
    }
  });

  body.addEventListener("keydown", function (event) {
    const input = event.target;
    if (input.tagName !== "INPUT") return;
    const listOpen = !list.hidden && owner === input;
    if (listOpen) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (!results.length) return;
        const step = event.key === "ArrowDown" ? 1 : -1;
        highlight((index + step + results.length) % results.length);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key === "Enter" && index >= 0) {
        event.preventDefault();
        pick(input.closest("tr"), results[index]);
        return;
      }
    }
    if (event.key === "Enter") {
      event.preventDefault(); // Enter never submits from the grid
      close();
      const next = input.closest("tr").nextElementSibling || addRow();
      cell(next, "navn").focus();
    }
  });

  body.addEventListener("focusout", function (event) {
    const left = event.target;
    // Checked later, since focus may be moving into the list or the next row by then.
    setTimeout(() => {
      if (owner === left && document.activeElement !== left) close();
    }, 0);
  });
  window.addEventListener("resize", () => !list.hidden && place());
})();
