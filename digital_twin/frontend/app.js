const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');

const ctx = document.getElementById('telemetryChart').getContext('2d');
const data = {
  labels: [],
  datasets: [
    { label: 'Oxygen %', data: [], borderColor: 'blue', fill: false, yAxisID: 'y' },
    { label: 'Pressure', data: [], borderColor: 'red', fill: false, yAxisID: 'y1' },
    { label: 'Breathing Rate', data: [], borderColor: 'green', fill: false, yAxisID: 'y' },
  ]
};

const chart = new Chart(ctx, {
  type: 'line',
  data,
  options: {
    scales: {
      y: { type: 'linear', position: 'left' },
      y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false } }
    }
  }
});

const alertsEl = document.getElementById('alerts');
const aiBox = document.getElementById('aiBox');

ws.onmessage = (evt) => {
  const msg = JSON.parse(evt.data);
  if (msg.type === 'telemetry') {
    const t = msg.data.telemetry;
    const ts = new Date(t.timestamp * 1000).toLocaleTimeString();
    data.labels.push(ts);
    data.datasets[0].data.push(t.oxygen);
    data.datasets[1].data.push(t.pressure);
    data.datasets[2].data.push(t.breathing_rate);
    if (data.labels.length > 60) {
      data.labels.shift();
      data.datasets.forEach(ds => ds.data.shift());
    }
    chart.update();

    // alerts
    alertsEl.innerHTML = '';
    for (const a of msg.data.alerts) {
      const li = document.createElement('li');
      li.textContent = `${a.type}: ${a.message}`;
      alertsEl.appendChild(li);
    }

    // ai
    const ai = t.ai || msg.data.ai || {};
    aiBox.innerHTML = `Hypoxia: ${(ai.hypoxia_prob||0).toFixed(2)}, Pressure risk: ${(ai.pressure_risk_prob||0).toFixed(2)}, Apnea: ${(ai.apnea_prob||0).toFixed(2)}`;
  }
};

ws.onopen = () => console.log('ws open');

document.getElementById('applyBtn').addEventListener('click', async () => {
  const oxygen = parseFloat(document.getElementById('oxygenIn').value || '95');
  const pressure = parseFloat(document.getElementById('pressureIn').value || '18');
  const breathing_rate = parseFloat(document.getElementById('breathingIn').value || '16');
  await fetch('/control', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ oxygen, pressure, breathing_rate }) });
});
