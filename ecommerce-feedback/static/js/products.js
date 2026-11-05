// Draws the product comparison chart on the Product Insights page.
(function () {
  const charts = FeedbackCharts;
  const products = charts.readData().filter(function (p) { return p.total > 0; });
  const canvas = document.getElementById("productComparisonChart");
  if (!canvas || !products.length) return;

  const fields = { Positive: "positive", Neutral: "neutral", Mixed: "mixed", Negative: "negative" };

  new Chart(canvas, {
    type: "bar",
    data: {
      labels: products.map(function (p) { return p.name; }),
      datasets: Object.keys(fields).map(function (name) {
        return {
          label: name,
          data: products.map(function (p) { return Math.round((p[fields[name]] || 0) / p.total * 1000) / 10; }),
          backgroundColor: charts.SENTIMENT_COLORS[name],
          maxBarThickness: 22
        };
      })
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 9, boxHeight: 9, usePointStyle: true } },
        tooltip: { callbacks: { label: function (c) { return c.dataset.label + ": " + c.parsed.x + "%"; } } }
      },
      scales: {
        x: charts.valueAxis({ stacked: true, max: 100, ticks: { callback: function (v) { return v + "%"; } } }),
        y: { stacked: true, grid: { display: false }, border: { display: false } }
      }
    }
  });
})();
