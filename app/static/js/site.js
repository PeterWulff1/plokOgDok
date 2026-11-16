// Small details on every page. Nothing here is needed to read the site: without this script
// record marks are simply underlined and the search works with the mouse.
(() => {
  // --- Record marks draw themselves ---------------------------------------------------
  // The coral line under a record (.is-pr) is drawn in from the left the first time it
  // scrolls into view. Skipped when the visitor has asked for less motion.
  const marks = document.querySelectorAll(".is-pr");
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (marks.length && !calm && "IntersectionObserver" in window) {
    const seen = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.replace("pr-wait", "pr-draw");
        seen.unobserve(entry.target);
      }
    }, { threshold: 0.6 });
    for (const mark of marks) {
      mark.classList.add("pr-wait");
      seen.observe(mark);
    }
  }

  // --- Keyboard: "/" goes to the search, arrows walk the results ------------------------
  const q = document.getElementById("q");
  const results = document.getElementById("search-results");

  const typing = (el) =>
    el instanceof HTMLElement &&
    (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));

  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
    if (typing(event.target)) return;
    event.preventDefault();
    if (q) {
      q.focus();
      q.select();
    } else {
      // Other pages: go to the front page's search (the menu link knows the site's base path).
      const link = document.querySelector('.masthead nav a[href$="#sog"]');
      if (link) window.location.href = link.href;
    }
  });

  if (!q || !results) return;
  if (window.location.hash === "#sog") q.focus({ preventScroll: true });

  const hits = () => Array.from(results.querySelectorAll("a"));

  q.addEventListener("keydown", (event) => {
    const links = hits();
    if (event.key === "ArrowDown" && links.length) {
      event.preventDefault();
      links[0].focus();
    } else if (event.key === "Enter" && links.length) {
      event.preventDefault();
      links[0].click();
    } else if (event.key === "Escape" && q.value) {
      event.preventDefault();
      q.value = "";
      q.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });

  results.addEventListener("keydown", (event) => {
    const links = hits();
    const at = links.indexOf(document.activeElement);
    if (at < 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      (links[at + 1] || links[at]).focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      (at === 0 ? q : links[at - 1]).focus();
    } else if (event.key === "Escape") {
      q.focus();
    }
  });
})();
