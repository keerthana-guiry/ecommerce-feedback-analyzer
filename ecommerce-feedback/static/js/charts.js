// Shared chart settings, so every page's charts look the same.
const FeedbackCharts = (function () {
  const SENTIMENT_COLORS = {
    Positive: "#16a34a",
    Neutral: "#d97706",
    Mixed: "#64748b",
    Negative: "#dc2626"
  };
  const EMERALD = "#10b981";

  Chart.defaults.font.family = "'Inter', 'Segoe UI', Arial, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = "#64748b";

  function readData() {
    return JSON.parse(document.getElementById("chart-data").textContent);
  }

  function emeraldFill(context, strength) {
    const area = context.chart.chartArea;
    if (!area) return "transparent";
    const gradient = context.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    gradient.addColorStop(0, "rgba(16, 185, 129, " + strength + ")");
    gradient.addColorStop(1, "rgba(16, 185, 129, 0)");
    return gradient;
  }

  function labelAxis(limit) {
    return {
      grid: { display: false },
      border: { display: false },
      ticks: { maxTicksLimit: limit, maxRotation: 0 }
    };
  }

  function valueAxis(extra) {
    return Object.assign({
      beginAtZero: true,
      grid: { color: "#edf2ef" },
      border: { display: false },
      ticks: { precision: 0, maxTicksLimit: 5 }
    }, extra);
  }

  return {
    SENTIMENT_COLORS: SENTIMENT_COLORS,
    EMERALD: EMERALD,
    readData: readData,
    emeraldFill: emeraldFill,
    labelAxis: labelAxis,
    valueAxis: valueAxis
  };
})();
