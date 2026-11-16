// Point calculator (/point): Sinclair or Q-points for a typed bodyweight and total, or the
// other way round: the total a wanted score takes, and where a total places in Denmark.
// The formulas mirror core/scoring.py (sinclair_factor, q_points_factor, required_total,
// split_increase), core/qualification.py (dmClass, dmMissingKg) and core/ranking.py
// (placeAmong, topPercent); tests/test_points_js.py runs this file in Node and compares.
// Everything else comes from the page: Sinclair sets from vl.sinclair_coefficient, Q-points
// constants from core.scoring.Q_POINTS, DM classes from core.qualification, and the active
// lifters' best totals per class from core.ranking.class_totals.

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

// The smallest whole-kg total that reaches the wanted points.
function requiredTotal(targetPoints, factor) {
  return Math.ceil(targetPoints / factor - 1e-9);
}

// Missing kilos shared between snatch and C&J in proportion to the current lifts.
function splitIncrease(snatch, cj, missingKg) {
  if (missingKg <= 0) return [0, 0];
  const toSnatch = Math.floor((missingKg * snatch) / (snatch + cj) + 0.5);
  return [toSnatch, missingKg - toSnatch];
}

function placeAmong(totals, total) {
  return 1 + totals.filter((t) => t > total).length;
}

function topPercent(place, others) {
  return Math.ceil((100 * place) / (others + 1));
}

if (typeof module !== "undefined") {
  module.exports = {
    sinclairFactor, qPointsFactor, dmClass, dmMissingKg,
    requiredTotal, splitIncrease, placeAmong, topPercent,
  };
} else {
  (function () {
    const { sinclair: sets, qpoints, dm, ranking } = JSON.parse(document.getElementById("point-coefficients").textContent);
    // The site root, also when the static site is served under a sub-path (GitHub Pages).
    const base = new URL("../..", document.currentScript.src).pathname.replace(/\/$/, "");
    const form = document.getElementById("point-form");
    const $ = (id) => document.getElementById(id);
    const dk = (v, d) => v.toLocaleString("da-DK", { minimumFractionDigits: d, maximumFractionDigits: d });
    const kg = (v) => dk(v, Number.isInteger(v) ? 0 : 1);
    const minus = (label) => label.replace("-", "−");
    const number = (name) => {
      const v = parseFloat(String(form.elements[name].value).replace(",", "."));
      return Number.isFinite(v) && v > 0 ? v : null;
    };

    function updateDm(cls, total) {
      $("dm-class").textContent = cls ? minus(cls.label) : "–";
      $("dm-total").textContent = cls ? `${cls.qualifying_total} kg` : "–";
      if (!cls || total == null) {
        $("dm-gap").textContent = "–";
        return;
      }
      const missing = dmMissingKg(cls, total);
      $("dm-gap").textContent = missing > 0 ? `Mangler ${missing.toLocaleString("da-DK")} kg` : "Krav klaret";
    }

    // Where the total would place among the active lifters in the class.
    function updateRank(gender, cls, total) {
      const totals = cls ? (ranking[gender] || {})[cls.label] || [] : [];
      const link = $("rank-link");
      $("rank-class").textContent = cls ? minus(cls.label) : "–";
      link.hidden = !cls;
      if (cls) {
        const query = new URLSearchParams({ g: gender, status: "active", wc: cls.label, sort: "-tot" });
        link.href = `${base}/data?${query}`;
      }
      if (!cls || total == null) {
        $("rank-place").textContent = "–";
        $("rank-top").textContent = "–";
        $("rank-kicker").textContent = "Aktive i Danmark";
        return;
      }
      const place = placeAmong(totals, total);
      $("rank-place").textContent = `Nr. ${place} af ${totals.length + 1}`;
      $("rank-top").textContent = `Top ${topPercent(place, totals.length)} %`;
      $("rank-kicker").textContent = `${kg(total)} kg mod ${totals.length} aktive`;
    }

    // Reverse mode: what each lift has to become to reach the required total.
    function updatePath(required, sn, cj) {
      const show = required != null && sn != null && cj != null;
      $("path-section").hidden = !show;
      if (!show) return;
      const missing = Math.max(Math.ceil(required - (sn + cj)), 0);
      const [addSn, addCj] = splitIncrease(sn, cj, missing);
      $("path-sn").textContent = `${kg(sn + addSn)} kg`;
      $("path-cj").textContent = `${kg(cj + addCj)} kg`;
      $("path-total").textContent = `${kg(sn + cj + missing)} kg`;
      $("path-kicker").textContent = missing > 0
        ? `+${addSn} kg i træk · +${addCj} kg i stød`
        : "Du er der allerede";
    }

    function update() {
      const gender = form.elements.g.value;
      const isQ = form.elements.system.value === "q";
      const reverse = form.elements.mode.value === "total";
      const points = isQ ? "Q-point" : "Sinclair";
      $("point-period").hidden = isQ;
      $("field-total").hidden = reverse;
      $("field-target").hidden = !reverse;
      $("split-or").textContent = reverse ? "i dag" : "eller";
      $("target-label").textContent = `Ønsket ${points}`;
      $("pt-label").textContent = reverse ? "Krævet total" : isQ ? "Q-point" : "Sinclair-point";

      const bw = number("bw");
      const sn = number("sn"), cj = number("cj");
      const typed = number("total");
      const target = number("target");
      form.elements.total.placeholder = sn != null && cj != null ? String(sn + cj) : "kg";

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

      const required = reverse && factor != null && target != null ? requiredTotal(target, factor) : null;
      const total = reverse ? required : typed != null ? typed : sn != null && cj != null ? sn + cj : null;
      const cls = bw == null ? null : dmClass(bw, dm[gender]);
      updateDm(cls, total);
      updateRank(gender, cls, total);
      updatePath(required, sn, cj);

      if (factor == null) {
        $("pt-points").textContent = "–";
        $("pt-factor").textContent = "Skriv en kropsvægt";
        $("pt-note").textContent = "";
        return;
      }
      $("pt-factor").textContent = `Faktor ${dk(factor, 4)}`;
      if (reverse) {
        $("pt-points").textContent = required == null ? "–" : `${dk(required, 0)} kg`;
        $("pt-note").textContent = note || (required == null
          ? "Skriv det pointtal, du vil nå."
          : `${dk(required, 0)} kg × ${dk(factor, 4)} = ${dk(required * factor, 2)} ${points}`);
        return;
      }
      $("pt-points").textContent = total == null ? "–" : dk(total * factor, 2);
      $("pt-note").textContent = note
        || (total == null ? "Skriv en total, eller træk og stød." : `${dk(total, 0)} kg × ${dk(factor, 4)}`);
    }

    form.addEventListener("input", update);
    form.addEventListener("change", update);
    form.addEventListener("submit", (e) => e.preventDefault());
    form.hidden = false;
    $("dm-section").hidden = false;
    $("rank-section").hidden = false;
    update();
  })();
}
