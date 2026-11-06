// Point calculator (/point): Sinclair or Q-points for a typed bodyweight and total.
// The formulas mirror core/scoring.py (sinclair_factor, q_points_factor);
// tests/test_points_js.py runs this file in Node and compares them.
// Coefficients come from the page: Sinclair sets from vl.sinclair_coefficient, Q-points
// constants from core.scoring.Q_POINTS.

function sinclairFactor(bodyweight, a, b) {
  if (bodyweight >= b) return 1;
  return Math.pow(10, a * Math.pow(Math.log10(bodyweight / b), 2));
}

function qPointsFactor(bodyweight, c) {
  const b = Math.max(bodyweight, c.min_bodyweight) / 100;
  return c.scale / (c.b0 + c.b1 * Math.pow(b, -2) + c.b2 * Math.pow(b, 2));
}

if (typeof module !== "undefined") {
  module.exports = { sinclairFactor, qPointsFactor };
} else {
  (function () {
    const { sinclair: sets, qpoints } = JSON.parse(document.getElementById("point-coefficients").textContent);
    const form = document.getElementById("point-form");
    const $ = (id) => document.getElementById(id);
    const dk = (v, d) => v.toLocaleString("da-DK", { minimumFractionDigits: d, maximumFractionDigits: d });
    const number = (name) => {
      const v = parseFloat(String(form.elements[name].value).replace(",", "."));
      return Number.isFinite(v) && v > 0 ? v : null;
    };

    function update() {
      const system = form.elements.system.value;
      const gender = form.elements.g.value;
      const isQ = system === "q";
      $("point-period").hidden = isQ;
      document.querySelectorAll("[data-system]").forEach((el) => { el.hidden = el.dataset.system !== system; });
      $("pt-label").textContent = isQ ? "Q-point" : "Sinclair-point";

      const bw = number("bw");
      const sn = number("sn"), cj = number("cj");
      const typed = number("total");
      const total = typed != null ? typed : sn != null && cj != null ? sn + cj : null;
      form.elements.total.placeholder = sn != null && cj != null ? String(sn + cj) : "kg";

      let factor = null, note = "";
      if (isQ) {
        const c = qpoints[gender];
        $("pt-coef").textContent = `${dk(c.scale, 2)} / (${dk(c.b0, 1)} − ${dk(-c.b1, 2)} · B⁻² + ${dk(c.b2, 2)} · B²), B = kropsvægt / 100`;
        if (bw != null) {
          factor = qPointsFactor(bw, c);
          if (bw < c.min_bodyweight) note = `Under ${dk(c.min_bodyweight, 0)} kg regnes med ${dk(c.min_bodyweight, 0)} kg.`;
        }
      } else {
        const c = sets[Number(form.elements.period.value)][gender];
        $("pt-coef").textContent = `A = ${dk(c.a, 9)} · b = ${dk(c.b, 3)} kg`;
        if (bw != null) {
          factor = sinclairFactor(bw, c.a, c.b);
          if (bw >= c.b) note = `Over ${dk(c.b, 1)} kg tæller totalen fuldt ud (faktor 1).`;
        }
      }

      if (factor == null) {
        $("pt-points").textContent = "–";
        $("pt-factor").textContent = "Skriv en kropsvægt";
        $("pt-note").textContent = "";
        return;
      }
      $("pt-factor").textContent = `Faktor ${dk(factor, 4)}`;
      $("pt-points").textContent = total == null ? "–" : dk(total * factor, 2);
      $("pt-note").textContent = note
        || (total == null ? "Skriv en total, eller træk og stød." : `${dk(total, 0)} kg × ${dk(factor, 4)}`);
    }

    form.addEventListener("input", update);
    form.addEventListener("change", update);
    form.addEventListener("submit", (e) => e.preventDefault());
    form.hidden = false;
    update();
  })();
}
