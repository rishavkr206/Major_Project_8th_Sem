const API_BASE = window.API_BASE || "http://127.0.0.1:8000";

function nav(active) {
    return `
    <header class="topbar">
        <a class="brand" href="index.html">
            <div class="brand-mark"><i class="fas fa-lungs"></i></div>
            <div>
                <div class="brand-title">Ventilator OS</div>
                <div class="brand-subtitle">Digital twin clinical dashboard</div>
            </div>
        </a>
        <nav class="nav-links">
            <a class="${active === "dashboard" ? "active" : ""}" href="index.html"><i class="fas fa-gauge-high"></i> Live Dashboard</a>
            <a class="${active === "tests" ? "active" : ""}" href="tests.html"><i class="fas fa-flask-vial"></i> Test Cases</a>
            <a class="${active === "models" ? "active" : ""}" href="models.html"><i class="fas fa-chart-simple"></i> Model Metrics</a>
            <a class="${active === "audit" ? "active" : ""}" href="audit.html"><i class="fas fa-link"></i> Audit & System</a>
        </nav>
    </header>`;
}

function alertClass(level) {
    const key = String(level || "").toLowerCase();
    if (key === "critical") return "critical";
    if (key === "warning") return "warning";
    return "stable";
}

function pct(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
    return `${(Number(value) * 100).toFixed(digits)}%`;
}

function num(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
    return Number(value).toFixed(digits);
}

async function apiGet(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`${path} failed with ${res.status}`);
    return res.json();
}

function renderKeyValueGrid(obj, unitMap = {}) {
    return Object.entries(obj || {}).map(([key, value]) => {
        const unit = unitMap[key] || "";
        return `
        <div class="metric panel">
            <div class="metric-label">${key.replaceAll("_", " ")}</div>
            <div class="metric-value">${num(value, 2)}${unit}</div>
        </div>`;
    }).join("");
}

window.VentilatorApp = { API_BASE, nav, alertClass, pct, num, apiGet, renderKeyValueGrid };
