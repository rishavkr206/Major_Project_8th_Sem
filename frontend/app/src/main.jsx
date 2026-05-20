import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  CloudSun,
  Database,
  FlaskConical,
  Gauge,
  HeartPulse,
  History,
  LayoutDashboard,
  Link2,
  Loader2,
  RefreshCw,
  Server,
  ShieldCheck,
  Stethoscope,
  TestTube2,
  Wind,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, API_BASE } from "./api";
import "./styles.css";

const pages = [
  { id: "live", label: "Live ICU", icon: LayoutDashboard },
  { id: "tests", label: "Test Lab", icon: FlaskConical },
  { id: "models", label: "Model Metrics", icon: BarChart3 },
  { id: "audit", label: "Audit & System", icon: ShieldCheck },
];

const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "--" : Number(v).toFixed(d));
const pct = (v, d = 1) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "--" : `${(Number(v) * 100).toFixed(d)}%`);
const riskTone = (v) => (Number(v) >= 0.7 ? "danger" : Number(v) >= 0.25 ? "warning" : "good");
const alertTone = (level) => String(level || "stable").toLowerCase();

function useAsync(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const reload = async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await loader();
      setState({ data, loading: false, error: null });
      return data;
    } catch (error) {
      setState({ data: null, loading: false, error });
      return null;
    }
  };
  useEffect(() => {
    reload();
  }, deps);
  return { ...state, reload };
}

function App() {
  const [page, setPage] = useState("live");
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandIcon"><HeartPulse size={24} /></div>
          <div>
            <div className="brandName">Ventilator OS</div>
            <div className="brandMeta">Digital Twin ICU</div>
          </div>
        </div>
        <nav>
          {pages.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="apiBox">
          <Server size={16} />
          <div>
            <span>API</span>
            <strong>{API_BASE.replace("http://", "")}</strong>
          </div>
        </div>
      </aside>
      <main>
        {page === "live" && <LivePage />}
        {page === "tests" && <TestLabPage />}
        {page === "models" && <ModelMetricsPage />}
        {page === "audit" && <AuditPage />}
      </main>
    </div>
  );
}

function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <header className="pageHeader">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="actions">{actions}</div>
    </header>
  );
}

function Button({ children, onClick, variant = "primary", disabled }) {
  return (
    <button className={`btn ${variant}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

function Metric({ label, value, note, tone = "" }) {
  return (
    <section className="metric">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
      {note && <small>{note}</small>}
    </section>
  );
}

function Empty({ icon: Icon = Database, title, text }) {
  return (
    <div className="empty">
      <Icon size={34} />
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function LoadingBlock({ label = "Loading" }) {
  return (
    <div className="empty">
      <Loader2 className="spin" size={32} />
      <strong>{label}</strong>
    </div>
  );
}

function LivePage() {
  const [selected, setSelected] = useState("");
  const [history, setHistory] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [multiRisk, setMultiRisk] = useState(null);
  const [riskHistory, setRiskHistory] = useState([]);
  const [loadingPatient, setLoadingPatient] = useState(false);
  const [streamingEnabled, setStreamingEnabled] = useState(true);
  const [predicting, setPredicting] = useState(false);
  const historyRef = useRef([]);
  const streamBusyRef = useRef(false);
  const patients = useAsync(api.patients, []);
  const health = useAsync(api.health, []);
  const connectionError = patients.error || health.error;

  useEffect(() => {
    if (!selected && patients.data?.patients?.length) {
      setSelected(String(patients.data.patients[0]));
    }
  }, [patients.data, selected]);

  const updateHistory = (rows) => {
    historyRef.current = rows;
    setHistory(rows);
  };

  const pushRiskHistory = (classification) => {
    if (!classification) return;
    setRiskHistory((prev) => {
      const entry = {
        t: prev.length + 1,
        Hypoxia_Risk: classification.Hypoxia_Risk?.probability ?? null,
        Tachycardia_Risk: classification.Tachycardia_Risk?.probability ?? null,
        Hypotension_Risk: classification.Hypotension_Risk?.probability ?? null,
        Tachypnea_Risk: classification.Tachypnea_Risk?.probability ?? null,
        VILI_Risk: classification.VILI_Risk?.probability ?? null,
        Shock_Risk: classification.Shock_Risk?.probability ?? null,
      };
      return [...prev.slice(-19), entry];
    });
  };

  const loadPatient = async () => {
    if (!selected) return;
    setLoadingPatient(true);
    try {
      const hist = await api.history(selected);
      const rows = hist.history || [];
      updateHistory(rows);
      const latest = rows[rows.length - 1];
      if (latest) {
        const rec = await api.recommend(selected, { ...latest, history: rows.slice(-96) });
        setRecommendation(rec);
        try {
          const risk = await api.risks(selected, rows.slice(-64));
          setMultiRisk(risk);
          pushRiskHistory(risk.predictions?.classification);
        } catch {
          setMultiRisk(null);
        }
      }
    } finally {
      setLoadingPatient(false);
    }
  };

  const advanceStream = async () => {
    if (!selected || !historyRef.current.length || streamBusyRef.current) return;
    streamBusyRef.current = true;
    try {
      const tickResult = await api.tick(selected);
      const latest = tickResult.latest_record;
      if (!latest) return;
      const nextHistory = [...historyRef.current, latest].slice(-96);
      updateHistory(nextHistory);

      if (nextHistory.length >= 12) {
        setPredicting(true);
        const recent96 = nextHistory.slice(-96);
        const [recResult, riskResult] = await Promise.allSettled([
          api.recommend(selected, { ...latest, history: recent96 }),
          api.risks(selected, recent96.slice(-64)),
        ]);

        if (recResult.status === "fulfilled") {
          setRecommendation(recResult.value);
        }
        if (riskResult.status === "fulfilled") {
          setMultiRisk(riskResult.value);
          pushRiskHistory(riskResult.value.predictions?.classification);
        }
      }
    } catch (error) {
      console.warn("Live stream tick failed", error);
    } finally {
      streamBusyRef.current = false;
      setPredicting(false);
    }
  };

  useEffect(() => {
    loadPatient();
  }, [selected]);

  useEffect(() => {
    if (!selected || !streamingEnabled) return undefined;
    const interval = setInterval(() => {
      advanceStream();
    }, 2000);
    return () => clearInterval(interval);
  }, [selected, streamingEnabled]);

  const latest = history[history.length - 1] || {};
  const chartData = useMemo(
    () => history.slice(-80).map((row, i) => ({
      t: i + 1,
      SpO2: Number(row.SpO2),
      HR: Number(row.HR),
      MAP: Number(row.MAP),
      RespRate: Number(row.RespRate),
    })),
    [history]
  );

  return (
    <>
      <PageHeader
        eyebrow="Command center"
        title="Live Ventilator Digital Twin"
        description="A clinical operations view for patient state, LSTM predictions, PPO recommendation, multi-risk outputs, and twin replay."
        actions={
          <>
            <select value={selected} onChange={(e) => setSelected(e.target.value)} className="select">
              {(patients.data?.patients || []).map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
            <Button onClick={loadPatient} disabled={loadingPatient}><RefreshCw size={16} /> Refresh</Button>
            <Button
              variant="secondary"
              onClick={() => setStreamingEnabled((current) => !current)}
            >
              {streamingEnabled ? "Live stream On" : "Live stream Off"}
            </Button>
          </>
        }
      />

      {connectionError ? (
        <section className="panel xl">
          <Empty
            icon={AlertTriangle}
            title="API connection failed"
            text={`Unable to reach ${API_BASE}. Start the backend on port 8001, then click Reconnect.`}
          />
          <div className="actions">
            <Button
              onClick={async () => {
                await Promise.all([patients.reload(), health.reload()]);
              }}
            >
              <RefreshCw size={16} /> Reconnect API
            </Button>
          </div>
        </section>
      ) : null}

      {!connectionError && (patients.data?.patients || []).length === 0 ? (
        <section className="panel xl">
          <Empty
            icon={Database}
            title="No patients available"
            text="Patient list is empty. Check /patients in the API and verify dataset loading in /health."
          />
        </section>
      ) : null}

      <section className="grid four">
        <Metric label="SpO2" value={`${fmt(latest.SpO2)}%`} tone={Number(latest.SpO2) < 92 ? "danger" : "good"} note="Observed" />
        <Metric label="Heart Rate" value={fmt(latest.HR, 0)} note="BPM" />
        <Metric label="MAP" value={fmt(latest.MAP, 0)} note="mmHg" />
        <Metric label="Resp Rate" value={fmt(latest.RespRate, 0)} note="breaths/min" />
      </section>

      <section className="liveGrid">
        <div className="panel xl">
          <div className="panelHead">
            <h2>Patient Trajectory</h2>
            <span>{history.length} samples</span>
          </div>
          {loadingPatient ? <LoadingBlock label="Loading patient stream" /> : (
            <ResponsiveContainer width="100%" height={330}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="spo2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(148,163,184,.16)" vertical={false} />
                <XAxis dataKey="t" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" domain={[70, 130]} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148,163,184,.25)", borderRadius: 8 }} />
                <Area type="monotone" dataKey="SpO2" stroke="#38bdf8" fill="url(#spo2)" strokeWidth={3} />
                <Line type="monotone" dataKey="HR" stroke="#fb7185" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="MAP" stroke="#34d399" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="panel">
          <div className="panelHead">
            <h2>LSTM Forecast</h2>
            <span className={`chip ${recommendation?.lstm_forecast_source === "lstm_keras" ? "good" : "warning"}`}>
              {recommendation?.lstm_forecast_source || "pending"}
            </span>
          </div>
          <div className="grid two compact">
            <Metric label="Next SpO2" value={`${fmt(recommendation?.pred_next_spo2)}%`} />
            <Metric label="Hypoxia" value={pct(recommendation?.hypoxia_prob)} tone={riskTone(recommendation?.hypoxia_prob)} />
          </div>
          <h3>Recommendation</h3>
          <SettingsGrid settings={recommendation?.proposed} />
          <div className="hint">
            {predicting
              ? "Updating predictions in real time..."
              : health.data?.lstm?.artifacts_found
                ? "LSTM artifacts detected by API health check."
                : "Using fallback unless LSTM artifacts are trained."}
          </div>
        </div>
      </section>

      <section className="grid two">
        <RealtimeForecastPanel recommendation={recommendation} multiRisk={multiRisk} predicting={predicting} />
        <MultiRiskPanel data={multiRisk} />
      </section>

      <section className="panel xl">
        <div className="panelHead">
          <h2>Risk trend</h2>
          <span>Realtime risk probability forecast over recent ticks</span>
        </div>
        {riskHistory.length === 0 ? (
          <Empty title="Risk trend unavailable" text="Wait for the live stream to collect multi-risk predictions." />
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={riskHistory}>
              <CartesianGrid stroke="rgba(148,163,184,.16)" vertical={false} />
              <XAxis dataKey="t" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" domain={[0, 1]} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148,163,184,.25)", borderRadius: 8 }} />
              <Legend />
              <Line type="monotone" dataKey="Hypoxia_Risk" stroke="#f97316" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Tachycardia_Risk" stroke="#fb7185" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Hypotension_Risk" stroke="#34d399" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Tachypnea_Risk" stroke="#60a5fa" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="VILI_Risk" stroke="#c084fc" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Shock_Risk" stroke="#f43f5e" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      <section className="grid two">
        <TwinReplayPanel selected={selected} history={history} recommendation={recommendation} />
      </section>
    </>
  );
}
function RealtimeForecastPanel({ recommendation, multiRisk, predicting }) {
  const regression = multiRisk?.predictions?.regression || {};
  const classification = multiRisk?.predictions?.classification || {};
  const riskEntries = Object.entries(classification);

  return (
    <div className="panel">
      <div className="panelHead">
        <h2>Realtime Forecast</h2>
        <span className={`chip ${predicting ? 'warning' : 'good'}`}>
          {predicting ? 'Updating' : 'Live'}
        </span>
      </div>
      <div className="grid two compact">
        <Metric label="Next SpO2" value={`${fmt(recommendation?.pred_next_spo2)}%`} />
        <Metric label="Hypoxia" value={pct(recommendation?.hypoxia_prob)} tone={riskTone(recommendation?.hypoxia_prob)} />
      </div>
      <div className="table">
        <div><span>Predicted vital</span><strong>Value</strong></div>
        {Object.entries(regression).map(([key, payload]) => (
          <div key={key}>
            <span>{key.replaceAll('_', ' ')}</span>
            <strong>{fmt(payload?.prediction)}</strong>
          </div>
        ))}
      </div>
      <div className="riskList">
        {riskEntries.length === 0 ? (
          <div className="emptyHint">Waiting for multi-risk scoring...</div>
        ) : riskEntries.map(([key, payload]) => (
          <div key={key}>
            <span>{key.replaceAll('_', ' ')}</span>
            <div className="bar"><i style={{ width: `${Math.min(100, Number(payload?.probability) * 100)}%` }} /></div>
            <strong className={payload?.risk ? 'danger' : 'good'}>{pct(payload?.probability)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
function SettingsGrid({ settings }) {
  const rows = settings || {};
  return (
    <div className="settingsGrid">
      {["PEEP", "FiO2", "TidalVol"].map((key) => (
        <div key={key}>
          <span>{key}</span>
          <strong>{fmt(rows[key])}</strong>
        </div>
      ))}
    </div>
  );
}

function MultiRiskPanel({ data }) {
  const regression = data?.predictions?.regression || {};
  const classification = data?.predictions?.classification || {};
  return (
    <div className="panel">
      <div className="panelHead">
        <h2>Multi-Risk LSTM</h2>
        <span className="chip">{data?.source || "not loaded"}</span>
      </div>
      {!data ? <Empty title="Multi-risk unavailable" text="The page still works with recommendation output. Train/load multi-risk artifacts to populate this panel." /> : (
        <>
          <h3>Next Vitals</h3>
          <div className="table">
            {Object.entries(regression).map(([k, v]) => (
              <div key={k}><span>{k.replaceAll("_", " ")}</span><strong>{fmt(v.prediction)}</strong></div>
            ))}
          </div>
          <h3>Risk Heads</h3>
          <div className="riskList">
            {Object.entries(classification).map(([k, v]) => (
              <div key={k}>
                <span>{k.replaceAll("_", " ")}</span>
                <div className="bar"><i style={{ width: `${Math.min(100, Number(v.probability) * 100)}%` }} /></div>
                <strong className={v.risk ? "danger" : "good"}>{pct(v.probability)}</strong>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TwinReplayPanel({ selected, history, recommendation }) {
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const run = async () => {
    if (!history.length || !recommendation?.proposed) return;
    setRunning(true);
    try {
      const latest = history[history.length - 1];
      const data = await api.twinReplay({
        stay_id: Number(selected),
        history: history.slice(-32),
        current_spo2: latest.SpO2,
        proposed: recommendation.proposed,
        steps: 8,
        noise_scale: 0,
      });
      setResult(data.result);
    } finally {
      setRunning(false);
    }
  };
  const trajectory = (result?.trajectory || []).map((v, i) => ({ step: i, SpO2: v }));
  return (
    <div className="panel">
      <div className="panelHead">
        <h2>Digital Twin Replay</h2>
        <Button onClick={run} disabled={running || !recommendation}><TestTube2 size={16} /> Simulate</Button>
      </div>
      {!result ? <Empty icon={Wind} title="Replay ready" text="Run a deterministic replay using the current PPO recommendation." /> : (
        <>
          <div className="grid three compact">
            <Metric label="Mean SpO2" value={`${fmt(result.mean_spo2)}%`} />
            <Metric label="Delta SpO2" value={fmt(result.delta_spo2)} tone={Number(result.delta_spo2) < 0 ? "danger" : "good"} />
            <Metric label="Uncertainty" value={fmt(result.uncertainty)} />
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trajectory}>
              <CartesianGrid stroke="rgba(148,163,184,.16)" vertical={false} />
              <XAxis dataKey="step" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" domain={[70, 100]} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148,163,184,.25)", borderRadius: 8 }} />
              <Line type="monotone" dataKey="SpO2" stroke="#22d3ee" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}

function TestLabPage() {
  const scenarios = useAsync(api.scenarios, []);
  const [group, setGroup] = useState("control");
  const results = scenarios.data?.results || {};
  const groups = Object.keys(results);
  useEffect(() => {
    if (!results[group] && groups.length) setGroup(groups[0]);
  }, [scenarios.data]);
  const all = groups.flatMap((g) => results[g].map((item) => ({ group: g, ...item })));
  const selected = results[group] || [];
  const controlCases = results.control || [];
  const infectionCases = results.health_status || [];
  const historyLengthCases = results.lstm_history_length || [];
  const selectedSummaryRows = selected.map((item) => ({
    scenario: item.scenario_name,
    spo2: fmt(item.pred_spo2),
    hypoxia: pct(item.hypoxia_prob),
    hr: fmt(item.predicted_vitals?.Next_HR, 0),
    map: fmt(item.predicted_vitals?.Next_MAP, 0),
    resp: fmt(item.predicted_vitals?.Next_RespRate, 0),
    tv: fmt(item.predicted_vitals?.Next_TidalVol, 0),
  }));
  const healthStatusRows = controlCases.concat(infectionCases).map((item) => ({
    scenario: item.scenario_name,
    spo2: fmt(item.pred_spo2),
    hypoxia: pct(item.hypoxia_prob),
    hr: fmt(item.predicted_vitals?.Next_HR, 0),
    map: fmt(item.predicted_vitals?.Next_MAP, 0),
    resp: fmt(item.predicted_vitals?.Next_RespRate, 0),
    tv: fmt(item.predicted_vitals?.Next_TidalVol, 0),
  }));
  const historyLengthRows = historyLengthCases.map((item) => ({
    window: `${item.history_length} values`,
    spo2: fmt(item.pred_spo2),
    hypoxia: pct(item.hypoxia_prob),
    hr: fmt(item.predicted_vitals?.Next_HR, 0),
    map: fmt(item.predicted_vitals?.Next_MAP, 0),
    resp: fmt(item.predicted_vitals?.Next_RespRate, 0),
    tv: fmt(item.predicted_vitals?.Next_TidalVol, 0),
  }));
  const chartData = selected.map((item) => ({
    name: item.scenario_name.replace("Weather Impact: ", "").replace("Anomaly: ", ""),
    hypoxia: Number(item.hypoxia_prob) * 100,
    spo2: Number(item.pred_spo2),
  }));

  return (
    <>
      <PageHeader
        eyebrow="Scenario laboratory"
        title="Professional LSTM Test Suite"
        description="Compare every demo scenario with all predicted vitals, all risk heads, and traceable findings."
        actions={<Button onClick={scenarios.reload}><RefreshCw size={16} /> Run Again</Button>}
      />
      {scenarios.loading ? <LoadingBlock label="Running scenarios" /> : scenarios.error ? <Empty icon={AlertTriangle} title="Scenario API failed" text={scenarios.error.message} /> : (
        <>
          <section className="grid four">
            <Metric label="Cases" value={all.length} note="Total scenarios" />
            <Metric label="Critical" value={all.filter((x) => x.alert_level === "CRITICAL").length} tone="danger" />
            <Metric label="Warning" value={all.filter((x) => x.alert_level === "WARNING").length} tone="warning" />
            <Metric label="Mean Risk" value={pct(all.reduce((s, x) => s + Number(x.hypoxia_prob), 0) / Math.max(all.length, 1))} />
          </section>
          <section className="grid two">
            <div className="panel">
              <h2>Healthy vs Lung Infection</h2>
              <div className="table">
                <div><span>Scenario</span><strong>SpO2 / Hypoxia / HR / MAP / RR / TV</strong></div>
                {healthStatusRows.map((row) => (
                  <div key={row.scenario}>
                    <span>{row.scenario}</span>
                    <strong>{row.spo2}% / {row.hypoxia} / {row.hr} / {row.map} / {row.resp} / {row.tv}</strong>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel">
              <h2>LSTM Window Sizes</h2>
              <div className="table">
                <div><span>History length</span><strong>SpO2 / Hypoxia / HR / MAP / RR / TV</strong></div>
                {historyLengthRows.map((row) => (
                  <div key={row.window}>
                    <span>{row.window}</span>
                    <strong>{row.spo2}% / {row.hypoxia} / {row.hr} / {row.map} / {row.resp} / {row.tv}</strong>
                  </div>
                ))}
              </div>
            </div>
          </section>
          <section className="panel xl">
            <div className="panelHead"><h2>Selected Group Metrics</h2><span>Numerical metrics for the active scenario group</span></div>
            <div className="dataGridTable">
              <div className="tableHeader">
                <span>Scenario</span>
                <span>SpO2</span>
                <span>Hypoxia</span>
                <span>HR</span>
                <span>MAP</span>
                <span>RR</span>
                <span>TV</span>
              </div>
              {selectedSummaryRows.map((row) => (
                <div key={row.scenario} className="tableRow">
                  <span>{row.scenario}</span>
                  <span>{row.spo2}%</span>
                  <span>{row.hypoxia}</span>
                  <span>{row.hr}</span>
                  <span>{row.map}</span>
                  <span>{row.resp}</span>
                  <span>{row.tv}</span>
                </div>
              ))}
            </div>
          </section>
          <section className="split">
            <div className="panel">
              <h2>Scenario Groups</h2>
              <div className="groupList">
                {groups.map((g) => <button key={g} className={group === g ? "active" : ""} onClick={() => setGroup(g)}>{g.replaceAll("_", " ")}<span>{results[g].length}</span></button>)}
              </div>
            </div>
            <div className="panel xl">
              <div className="panelHead"><h2>{group.replaceAll("_", " ")}</h2><span>Graphs & trends</span></div>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid stroke="rgba(148,163,184,.16)" vertical={false} />
                  <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148,163,184,.25)", borderRadius: 8 }} />
                  <Bar dataKey="spo2" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="hypoxia" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="panel xl">
            <div className="panelHead">
              <h2>Trend view</h2>
              <span>Line graph for the same selected group</span>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="rgba(148,163,184,.16)" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148,163,184,.25)", borderRadius: 8 }} />
                <Legend />
                <Line type="monotone" dataKey="spo2" stroke="#38bdf8" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="hypoxia" stroke="#f59e0b" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </section>
          <section className="scenarioGrid">
            {selected.map((item) => <ScenarioCard key={item.scenario_name} item={item} />)}
          </section>
        </>
      )}
    </>
  );
}

function ScenarioCard({ item }) {
  return (
    <article className="panel scenario">
      <div className="panelHead">
        <h2>{item.scenario_name}</h2>
        <span className={`chip ${alertTone(item.alert_level)}`}>{item.alert_level}</span>
      </div>
      <div className="grid three compact">
        <Metric label="Pred SpO2" value={`${fmt(item.pred_spo2)}%`} />
        <Metric label="Hypoxia" value={pct(item.hypoxia_prob)} tone={riskTone(item.hypoxia_prob)} />
        <Metric label="Samples" value={item.observations} />
      </div>
      <div className="dualTables">
        <MiniTable title="All Predicted Vitals" rows={item.predicted_vitals} />
        <RiskTable rows={item.risk_predictions} />
      </div>
      <ul>
        {(item.key_findings || []).map((f) => <li key={f}>{f}</li>)}
      </ul>
    </article>
  );
}

function MiniTable({ title, rows }) {
  return (
    <div>
      <h3>{title}</h3>
      <div className="table">
        {Object.entries(rows || {}).map(([k, v]) => <div key={k}><span>{k.replaceAll("_", " ")}</span><strong>{fmt(v)}</strong></div>)}
      </div>
    </div>
  );
}

function RiskTable({ rows }) {
  return (
    <div>
      <h3>All Risk Heads</h3>
      <div className="riskList small">
        {Object.entries(rows || {}).map(([k, v]) => (
          <div key={k}>
            <span>{k.replaceAll("_", " ")}</span>
            <strong className={v.risk ? "danger" : "good"}>{pct(v.probability)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function ModelMetricsPage() {
  const evaluation = useAsync(api.evaluation, []);
  const reports = evaluation.data?.reports || {};
  const dual = reports.lstm_dual_head || {};
  const multi = reports.multi_risk_lstm || {};
  const regressionTargets = ["Next_SpO2", "Next_HR", "Next_MAP", "Next_RespRate", "Next_TidalVol"];
  const riskTargets = ["Hypoxia_Risk", "Tachycardia_Risk", "Hypotension_Risk", "Tachypnea_Risk", "VILI_Risk", "Shock_Risk"];
  const riskChart = riskTargets.map((name) => ({
    name: name.replace("_Risk", ""),
    AUROC: Number(multi[`${name}_auroc`] || 0),
    F1: Number(multi[`${name}_f1_optimal`] || 0),
  }));

  return (
    <>
      <PageHeader
        eyebrow="Evaluation center"
        title="Accuracy, Error & Classification Metrics"
        description="A focused view of the saved model reports: regression error for next vitals and classifier quality for each risk head."
        actions={<Button onClick={evaluation.reload}><RefreshCw size={16} /> Refresh</Button>}
      />
      {evaluation.loading ? <LoadingBlock label="Loading metrics" /> : (
        <>
          <section className="grid four">
            <Metric label="Dual SpO2 MAE" value={fmt(dual.next_spo2_mae, 3)} />
            <Metric label="Dual SpO2 RMSE" value={fmt(dual.next_spo2_rmse, 3)} />
            <Metric label="Hypoxia AUROC" value={fmt(dual.hypoxia_auroc, 3)} tone="good" />
            <Metric label="VILI Best F1" value={fmt(multi.VILI_Risk_f1_optimal, 3)} tone="good" />
          </section>
          <section className="grid two">
            <div className="panel">
              <h2>Multi-Risk Classification</h2>
              <ResponsiveContainer width="100%" height={310}>
                <BarChart data={riskChart}>
                  <CartesianGrid stroke="rgba(148,163,184,.16)" vertical={false} />
                  <XAxis dataKey="name" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" domain={[0, 1]} />
                  <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(148,163,184,.25)", borderRadius: 8 }} />
                  <Bar dataKey="AUROC" fill="#34d399" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="F1" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="panel">
              <h2>Dual-Head LSTM</h2>
              <div className="table">
                <div><span>Next SpO2 MAE</span><strong>{fmt(dual.next_spo2_mae, 4)}</strong></div>
                <div><span>Next SpO2 RMSE</span><strong>{fmt(dual.next_spo2_rmse, 4)}</strong></div>
                <div><span>Hypoxia AUROC</span><strong>{fmt(dual.hypoxia_auroc, 4)}</strong></div>
                <div><span>Average Precision</span><strong>{fmt(dual.hypoxia_avg_prec, 4)}</strong></div>
                <div><span>F1 @ 0.5</span><strong>{fmt(dual.hypoxia_f1_thresh05, 4)}</strong></div>
              </div>
            </div>
          </section>
          <section className="grid two">
            <div className="panel">
              <h2>Next Vital Regression</h2>
              <div className="table">
                {regressionTargets.map((t) => <div key={t}><span>{t}</span><strong>MAE {fmt(multi[`${t}_mae`], 3)} | RMSE {fmt(multi[`${t}_rmse`], 3)}</strong></div>)}
              </div>
            </div>
            <div className="panel">
              <h2>Risk Thresholds</h2>
              <div className="table">
                {riskTargets.map((t) => <div key={t}><span>{t}</span><strong>AUROC {fmt(multi[`${t}_auroc`], 3)} | F1 {fmt(multi[`${t}_f1_optimal`], 3)} @ {fmt(multi[`${t}_optimal_threshold`], 2)}</strong></div>)}
              </div>
            </div>
          </section>
        </>
      )}
    </>
  );
}

function AuditPage() {
  const audit = useAsync(async () => {
    const [verify, health, fiware] = await Promise.all([
      api.auditVerify(),
      api.health(),
      api.fiware().catch(() => ({ enabled: false, health: { reachable: false } })),
    ]);
    return { verify, health, fiware };
  }, []);
  const data = audit.data || {};

  return (
    <>
      <PageHeader
        eyebrow="Trust and operations"
        title="Audit Chain & System Health"
        description="Verify the immutable audit trail, inspect dataset status, and confirm whether model artifacts are loaded."
        actions={<Button onClick={audit.reload}><RefreshCw size={16} /> Refresh</Button>}
      />
      {audit.loading ? <LoadingBlock label="Checking system" /> : (
        <>
          <section className="grid four">
            <Metric label="Audit Chain" value={data.verify?.valid ? "Valid" : "Invalid"} tone={data.verify?.valid ? "good" : "danger"} note={data.verify?.message} />
            <Metric label="Dataset" value={data.health?.dataset_index_loaded ? "Loaded" : "Simulator"} note={`${data.health?.index_rows || 0} rows`} />
            <Metric label="LSTM Artifacts" value={data.health?.lstm?.artifacts_found ? "Found" : "Missing"} tone={data.health?.lstm?.artifacts_found ? "good" : "warning"} />
            <Metric label="FIWARE" value={data.fiware?.enabled ? "Enabled" : "Off"} note={data.fiware?.base_url || "local mode"} />
          </section>
          <section className="grid two">
            <JsonPanel title="Audit Verification" data={data.verify} icon={Link2} />
            <JsonPanel title="API Health" data={data.health} icon={Server} />
          </section>
        </>
      )}
    </>
  );
}

function JsonPanel({ title, data, icon: Icon }) {
  return (
    <div className="panel">
      <div className="panelHead"><h2>{title}</h2><Icon size={18} /></div>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
