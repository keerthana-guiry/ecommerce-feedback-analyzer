// Draws the charts on the Reports & Trends page.
(function () {
  const charts = FeedbackCharts;
  const data = charts.readData();
  if (!data.total) return;

  new Chart(document.getElementById("sentimentTrendChart"), {
    type: "bar",
    data: {
      labels: data.labels,
      datasets: Object.keys(charts.SENTIMENT_COLORS).map(function (name) {
        return {
          label: name,
          data: data.sentiment_series[name],
          backgroundColor: charts.SENTIMENT_COLORS[name],
          borderRadius: 2,
          maxBarThickness: 40
        };
      })
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 9, boxHeight: 9, usePointStyle: true } } },
      scales: {
        x: Object.assign(charts.labelAxis(8), { stacked: true }),
        y: charts.valueAxis({ stacked: true })
      }
    }
  });

  new Chart(document.getElementById("satisfactionChart"), {
    type: "line",
    data: {
      labels: data.labels,
      datasets: [
        {
          label: "Positive reviews (%)",
          data: data.positive_rate,
          yAxisID: "rate",
          borderColor: charts.EMERALD,
          borderWidth: 2,
          cubicInterpolationMode: "monotone",
          spanGaps: true,
          pointRadius: 2
        },
        {
          label: "Average rating (out of 5)",
          data: data.avg_rating,
          yAxisID: "rating",
          borderColor: "#14251f",
          borderWidth: 2,
          borderDash: [5, 4],
          cubicInterpolationMode: "monotone",
          spanGaps: true,
          pointRadius: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 9, boxHeight: 9, usePointStyle: true } } },
      scales: {
        x: charts.labelAxis(8),
        rate: charts.valueAxis({ position: "left", max: 100, ticks: { callback: function (v) { return v + "%"; }, maxTicksLimit: 5 } }),
        rating: charts.valueAxis({ position: "right", max: 5, grid: { display: false }, ticks: { maxTicksLimit: 6 } })
      }
    }
  });
})();
