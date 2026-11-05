// Draws the charts on the Dashboard page.
(function () {
  const charts = FeedbackCharts;
  const data = charts.readData();

  const dayLabels = data.labels.map(function (day) {
    return new Date(day + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" });
  });

  // Sparklines show the trend, so average out day-to-day noise
  function rollingAverage(series, size) {
    return series.map(function (_, index) {
      const values = series.slice(Math.max(index - size + 1, 0), index + 1).filter(function (v) { return v !== null; });
      if (!values.length) return null;
      return values.reduce(function (sum, v) { return sum + v; }, 0) / values.length;
    });
  }

  document.querySelectorAll("canvas[data-spark]").forEach(function (canvas) {
    new Chart(canvas, {
      type: "line",
      data: {
        labels: dayLabels,
        datasets: [{
          data: rollingAverage(data.kpis[Number(canvas.dataset.spark)].series, 5),
          borderColor: charts.EMERALD,
          borderWidth: 1.5,
          cubicInterpolationMode: "monotone",
          spanGaps: true,
          fill: true,
          backgroundColor: function (context) { return charts.emeraldFill(context, 0.18); },
          pointRadius: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
        layout: { padding: 2 }
      }
    });
  });

  const trendCanvas = document.getElementById("reviewTrendChart");
  if (trendCanvas) {
    new Chart(trendCanvas, {
      type: "line",
      data: {
        labels: dayLabels,
        datasets: [{
          label: "Reviews",
          data: data.kpis[0].series,
          borderColor: charts.EMERALD,
          borderWidth: 2,
          cubicInterpolationMode: "monotone",
          fill: true,
          backgroundColor: function (context) { return charts.emeraldFill(context, 0.22); },
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: charts.EMERALD
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false } },
        scales: { x: charts.labelAxis(7), y: charts.valueAxis() }
      }
    });
  }

  const distributionCanvas = document.getElementById("sentimentDistributionChart");
  if (distributionCanvas) {
    const names = Object.keys(charts.SENTIMENT_COLORS);
    new Chart(distributionCanvas, {
      type: "doughnut",
      data: {
        labels: names,
        datasets: [{
          data: names.map(function (name) { return data.distribution[name]; }),
          backgroundColor: names.map(function (name) { return charts.SENTIMENT_COLORS[name]; }),
          borderWidth: 2,
          borderColor: "#ffffff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: { legend: { position: "bottom", labels: { boxWidth: 9, boxHeight: 9, usePointStyle: true } } }
      }
    });
  }
})();
