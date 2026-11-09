// Point calculator (/point): Sinclair or Q-points for a typed bodyweight and total.
// The formulas mirror core/scoring.py (sinclair_factor, q_points_factor);
// tests/test_points_js.py runs this file in Node and compares them.
// Coefficients come from the page: Sinclair sets from vl.sinclair_coefficient, Q-points
// constants from core.scoring.Q_POINTS. DM classes and qualifying totals come from
// core.qualification, which dmClass and dmMissingKg mirror.

function sinclairFactor(bodyweight, a, b) {
  if (bodyweight >= b) return 1;
  return Math.pow(10, a * Math.pow(Math.log10(bodyweight / b), 2));
}

function qPointsFactor(bodyweight, c) {
  const b = Math.max(bodyweight, c.min_bodyweight) / 100;
  return c.scale / (c.b0 + c.b1 * Math.pow(b, -2) + c.b2 * Math.pow(b, 2));
}

function dmClass(bodyweight, classes) {
  return classes.find((c) => c.ceiling === null || bodyweight <= c.ceiling);
}

function dmMissingKg(cls, total) {
  return Math.max(cls.qualifying_total - total, 0);
}

if (typeof module !== "undefined") {
  module.exports = { sinclairFactor, qPointsFactor, dmClass, dmMissingKg };
} else {
  (function () {
    const { sinclair: sets, qpoints, dm } = JSON.parse(document.getElementById("point-coefficients").textContent);
    const form = document.getElementById("point-form");
    const $ = (id) => document.getElementById(id);
    const dk = (v, d) => v.toLocaleString("da-DK", { minimumFractionDigits: d, maximumFractionDigits: d });
    const number = (name) => {
      const v = parseFloat(String(form.elements[name].value).replace(",", "."));
      return Number.isFinite(v) && v > 0 ? v : null;
    };

    function updateDm(gender, bw, total) {
      const cls = bw == null ? null : dmClass(bw, dm[gender]);
      $("dm-class").textContent = cls ? cls.label.replace("-", "−") : "–";
      $("dm-total").textContent = cls ? `${cls.qualifying_total} kg` : "–";
      if (!cls || total == null) {
        $("dm-gap").textContent = "–";
        return;
      }
      const missing = dmMissingKg(cls, total);
      $("dm-gap").textContent = missing > 0 ? `Mangler ${missing.toLocaleString("da-DK")} kg` : "Krav klaret";
    }

    function update() {
      const system = form.elements.system.value;
      const gender = form.elements.g.value;
      const isQ = system === "q";
      $("point-period").hidden = isQ;
      $("pt-label").textContent = isQ ? "Q-point" : "Sinclair-point";

      const bw = number("bw");
      const sn = number("sn"), cj = number("cj");
      const typed = number("total");
      const total = typed != null ? typed : sn != null && cj != null ? sn + cj : null;
      form.elements.total.placeholder = sn != null && cj != null ? String(sn + cj) : "kg";
      updateDm(gender, bw, total);

      let factor = null, note = "";
      if (isQ) {
        const c = qpoints[gender];
        if (bw != null) {
          factor = qPointsFactor(bw, c);
          if (bw < c.min_bodyweight) note = `Under ${dk(c.min_bodyweight, 0)} kg regnes med ${dk(c.min_bodyweight, 0)} kg.`;
        }
      } else {
        const c = sets[Number(form.elements.period.value)][gender];
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
    $("dm-section").hidden = false;
    update();
  })();
}
