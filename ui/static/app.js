const palette = [
  "#0062ff",
  "#8a3ffc",
  "#ff832b",
  "#24a148",
  "#d12771",
  "#009d9a",
  "#a56eff",
  "#ff7eb6",
  "#fa4d56",
  "#0f62fe",
  "#42be65",
  "#be95ff",
  "#7d8de7",
  "#12c2e9",
  "#c471ed",
  "#f64f59",
  "#ee5396",
  "#f1c21b",
  "#198038",
  "#1192e8",
  "#fae100",
  "#0f7cd6",
  "#ff6f61",
  "#9f1853",
  "#6929c4",
  "#8d8d8d",
  "#3ddbd9",
  "#33b1ff",
  "#ffb6ff",
  "#ffadad",
  "#6f45c5",
];

const state = {
  metrics: [],
  start: dayStart(new Date()),
  end: new Date(),
  weather: null,
};

let janitzaChart;
let weatherChart;

document.addEventListener("DOMContentLoaded", () => {
  initCharts();
});

document.addEventListener("htmx:afterSwap", (event) => {
  if (event.target.id === "controls") {
    bindControls();
    refreshAll();
  }
});

function initCharts() {
  const left = document.getElementById("janitza-chart");
  if (left) {
    janitzaChart = echarts.init(left);
    janitzaChart.setOption(emptyOption("Selectează metrici din panel."));
  }
  const right = document.getElementById("weather-chart");
  if (right) {
    weatherChart = echarts.init(right);
    weatherChart.setOption(emptyOption("Alege un dataset meteo."));
  }
}

function emptyOption(message) {
  return {
    textStyle: { fontFamily: "Roboto, sans-serif" },
    title: { text: message, left: "center", top: "40%", textStyle: { color: "#8a8fb3" } },
  };
}

function bindControls() {
  const dateInput = document.getElementById("date-start");
  if (dateInput) {
    dateInput.addEventListener("change", () => {
      const chosen = new Date(dateInput.value);
      state.start = dayStart(chosen);
      state.end = dayEnd(chosen);
      refreshAll();
    });
  }

  document.querySelectorAll(".preset-btn").forEach((button) => {
    button.addEventListener("click", () => {
      setRange(button.dataset.range);
      refreshAll();
    });
  });

  const weatherSelect = document.querySelector(".control-group select");
  if (weatherSelect) {
    const saved = loadSelection();
    if (saved.weather && Array.from(weatherSelect.options).some((opt) => opt.value === saved.weather)) {
      state.weather = saved.weather;
    }
    if (state.weather) {
      weatherSelect.value = state.weather;
    } else {
      state.weather = weatherSelect.value;
      saveSelection({ weather: state.weather });
    }
    weatherSelect.addEventListener("change", () => {
      state.weather = weatherSelect.value;
      saveSelection({ weather: state.weather });
      refreshWeatherChart();
    });
  }

  const metricChips = document.querySelectorAll(".metric-chip input");
  const savedSelection = loadSelection();
  metricChips.forEach((checkbox) => {
    if (savedSelection.metrics.length && savedSelection.metrics.includes(checkbox.value)) {
      checkbox.checked = true;
    } else if (!savedSelection.metrics.length && checkbox.dataset.default === "1") {
      checkbox.checked = true;
    }
    checkbox.addEventListener("change", onMetricChange);
  });
  let selectedMetrics = Array.from(metricChips).filter((c) => c.checked).map((c) => c.value);
  state.metrics = selectedMetrics;
  saveSelection();
  refreshJanitzaChart();
}

function onMetricChange() {
  const selected = Array.from(document.querySelectorAll(".metric-chip input:checked")).map((node) => node.value);
  state.metrics = selected;
  saveSelection();
  refreshJanitzaChart();
}

function setRange(range) {
  const now = new Date();
  switch (range) {
    case "3days":
      state.start = new Date(now.getTime() - 3 * 86400000);
      break;
    case "week":
      state.start = new Date(now.getTime() - 7 * 86400000);
      break;
    case "month":
      state.start = new Date(now.getTime() - 30 * 86400000);
      break;
    case "year":
      state.start = new Date(now.getTime() - 365 * 86400000);
      break;
    default:
      state.start = new Date(now.getTime() - 86400000);
  }
  state.end = now;
}

function refreshAll() {
  refreshJanitzaChart();
  refreshWeatherChart();
}

async function refreshJanitzaChart() {
  if (!janitzaChart) return;
  if (!state.metrics.length) {
    janitzaChart.setOption(emptyOption("Selectează metrici din panel."));
    document.getElementById("janitza-table").innerHTML = "";
    return;
  }
  const url = new URL("/ui/api/janitza", window.location.origin);
  url.searchParams.set("start", state.start.toISOString());
  url.searchParams.set("end", state.end.toISOString());
  url.searchParams.set("metrics", state.metrics.join(","));
  const response = await fetch(url);
  if (!response.ok) return;
  const payload = await response.json();

  const series = payload.series.map((series) => {
    const color = getColor(series.name);
    const raw = series.data.map((point) => [point.timestamp, point.value]);
    const sampled = downsample(raw);
    return {
      name: series.name,
      type: "line",
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 3, shadowBlur: 10, shadowColor: `${color}55` },
      areaStyle: {
        opacity: 0.08,
        color: color,
      },
      itemStyle: { color },
      data: sampled,
    };
  });

  janitzaChart.setOption({
    textStyle: { fontFamily: "Roboto, sans-serif" },
    legend: { top: 12 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "time",
      axisLabel: { formatter: "{HH}:{mm}" },
    },
    yAxis: { type: "value", axisLabel: { formatter: (value) => value.toFixed(1) } },
    series,
  });

  const tableUrl = new URL("/ui/janitza/table", window.location.origin);
  tableUrl.searchParams.set("start", state.start.toISOString());
  tableUrl.searchParams.set("end", state.end.toISOString());
  tableUrl.searchParams.set("metrics", state.metrics.join(","));
  const table = await fetch(tableUrl);
  if (table.ok) {
    document.getElementById("janitza-table").innerHTML = await table.text();
  }
}

async function refreshWeatherChart() {
  if (!weatherChart || !state.weather) return;
  const url = new URL("/ui/api/weather", window.location.origin);
  url.searchParams.set("type", state.weather);
  url.searchParams.set("start", state.start.toISOString());
  url.searchParams.set("end", state.end.toISOString());

  const response = await fetch(url);
  if (!response.ok) return;
  const payload = await response.json();
  if (!payload.series || !payload.series.length) {
    weatherChart.setOption(emptyOption("Nicio serie selectată."));
    return;
  }

  const series = payload.series.map((series, idx) => {
    const color = palette[idx % palette.length];
    const raw = series.data.map((point) => [point.timestamp, point.value]);
    return {
      name: series.name,
      type: "line",
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 3, shadowBlur: 8, shadowColor: `${color}66` },
      areaStyle: { opacity: 0.07, color },
      itemStyle: { color },
      data: downsample(raw),
    };
  });

  weatherChart.setOption({
    textStyle: { fontFamily: "Roboto, sans-serif" },
    legend: { top: 12 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "time", axisLabel: { formatter: "{HH}:{mm}" } },
    yAxis: { type: "value" },
    series,
  });
}

function downsample(points) {
  if (!points || points.length <= 2000) {
    return points;
  }
  const step = Math.ceil(points.length / 2000);
  return points.filter((_, idx) => idx % step === 0);
}

function dayStart(date) {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function dayEnd(date) {
  const copy = new Date(date);
  copy.setHours(23, 59, 59, 999);
  return copy;
}

function getColor(metric) {
  const map = loadSelection().colors;
  if (!map[metric]) {
    const used = Object.values(map);
    const available = palette.find((color) => !used.includes(color)) || palette[used.length % palette.length];
    map[metric] = available;
    saveSelection({ colors: map });
  }
  return loadSelection().colors[metric];
}

function loadSelection() {
  try {
    const saved = JSON.parse(localStorage.getItem("progonzaui") || "{}");
    return {
      metrics: saved.metrics || [],
      colors: saved.colors || {},
      weather: saved.weather || null,
    };
  } catch (err) {
    return { metrics: [], colors: {}, weather: null };
  }
}

function saveSelection(partial = {}) {
  const current = loadSelection();
  const next = {
    metrics: state.metrics,
    colors: { ...current.colors, ...(partial?.colors || {}) },
    weather: partial.weather ?? current.weather ?? state.weather,
  };
  localStorage.setItem("progonzaui", JSON.stringify(next));
}
