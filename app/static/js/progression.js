// Profile chart: best snatch and C&J per competition. Two series, one kg axis,
// legend + direct end labels, coral rings on PRs, tooltip per point.
(function () {
  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function draw() {
    const el = document.getElementById("progression");
    const data = JSON.parse(document.getElementById("chart-data").textContent);
    if (!el || !window.Plotly || data.dates.length === 0) return;

    const ink = css("--ink"), ink2 = css("--ink-2"), coral = css("--coral");
    const font = "Archivo, system-ui, sans-serif";

    function series(key, name, color) {
      const prKey = key === "snatch" ? "pr_snatch" : "pr_cj";
      return {
        type: "scatter",
        mode: "lines+markers",
        name: name,
        x: data.dates,
        y: data[key],
        customdata: data.competitions,
        line: { color: color, width: 2, shape: "linear" },
        marker: {
          size: data[prKey].map((pr) => (pr ? 11 : 8)),
          color: color,
          line: { color: data[prKey].map((pr) => (pr ? coral : "#ffffff")), width: data[prKey].map((pr) => (pr ? 3 : 2)) },
        },
        connectgaps: true,
        hovertemplate: "<b>%{customdata}</b><br>%{x|%d.%m.%Y}<br>" + name + ": %{y} kg<extra></extra>",
      };
    }

    const traces = [
      series("cj", "Stød", css("--series-cj")),
      series("snatch", "Træk", css("--series-snatch")),
    ];

    // Direct labels at the last point of each series.
    const last = data.dates.length - 1;
    const annotations = [
      ["cj", "Stød", css("--series-cj")],
      ["snatch", "Træk", css("--series-snatch")],
    ]
      .filter(([key]) => data[key][last] != null)
      .map(([key, label]) => ({
        x: data.dates[last], y: data[key][last], text: label, showarrow: false,
        xanchor: "left", xshift: 10, font: { family: font, size: 13, color: ink },
      }));

    Plotly.newPlot(el, traces, {
      margin: { l: 48, r: 56, t: 16, b: 40 },
      paper_bgcolor: "#ffffff",
      plot_bgcolor: "#ffffff",
      font: { family: font, size: 13, color: ink2 },
      hovermode: "closest",
      hoverlabel: { bgcolor: css("--paper"), bordercolor: ink, font: { family: font, color: ink } },
      showlegend: true,
      legend: { orientation: "h", x: 0, y: 1.08, font: { family: font, size: 13, color: ink } },
      annotations: annotations,
      xaxis: { showgrid: false, linecolor: ink, ticks: "outside", tickcolor: ink, fixedrange: true },
      yaxis: { gridcolor: "#EFE6DA", zeroline: false, ticksuffix: " kg", fixedrange: true },
    }, { displayModeBar: false, responsive: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.addEventListener("load", draw));
  } else {
    window.addEventListener("load", draw);
  }
})();
