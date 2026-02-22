import { FormEvent, useEffect, useRef, useState } from "react";
import {
  apiUrl,
  clearCache,
  createJob,
  fetchConfig,
  fetchReview,
  fetchStatus,
  submitReview
} from "./api";
import type { AppConfigResponse, JobSettings, JobStatusResponse, ReviewRow } from "./types";

const defaultStatus: JobStatusResponse = {
  job_id: "",
  status: "queued",
  progress_done: 0,
  progress_total: 0,
  progress_pct: 0,
  message: "",
  counts: {
    total_rows: 0,
    auto_matched: 0,
    needs_review: 0,
    not_found: 0,
    filled_via_domain: 0,
    filled_via_social: 0
  },
  can_download: false
};

function App() {
  const [config, setConfig] = useState<AppConfigResponse | null>(null);
  const [settings, setSettings] = useState<JobSettings | null>(null);
  const [denylistText, setDenylistText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string>("");
  const [status, setStatus] = useState<JobStatusResponse>(defaultStatus);
  const [reviewRows, setReviewRows] = useState<ReviewRow[]>([]);
  const [reviewSelection, setReviewSelection] = useState<Record<number, string>>({});
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const loaded = await fetchConfig();
        setConfig(loaded);
        setSettings(loaded.defaults);
        setDenylistText(loaded.defaults.denylist_domains.join("\n"));
      } catch (err) {
        setError(String(err));
      }
    })();
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  function updateSetting<K extends keyof JobSettings>(key: K, value: JobSettings[K]) {
    setSettings((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function normalizeDenylist(rawText: string): string[] {
    return rawText
      .split("\n")
      .map((line) => line.trim().toLowerCase())
      .filter(Boolean);
  }

  function buildSettingsFromState(currentSettings: JobSettings, currentDenylistText: string): JobSettings {
    return {
      ...currentSettings,
      denylist_domains: normalizeDenylist(currentDenylistText)
    };
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || !settings) {
      setError("Choose an .xlsx file and settings first.");
      return;
    }

    const normalizedSettings = buildSettingsFromState(settings, denylistText);
    setError("");
    setReviewRows([]);
    setReviewSelection({});
    setBusy(true);

    try {
      const createdJobId = await createJob(file, normalizedSettings);
      setJobId(createdJobId);
      const initialStatus = await fetchStatus(createdJobId);
      setStatus(initialStatus);
      subscribeToEvents(createdJobId);
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  }

  function subscribeToEvents(createdJobId: string) {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    const source = new EventSource(apiUrl(`/api/jobs/${createdJobId}/events`));
    eventSourceRef.current = source;
    source.onmessage = async (event) => {
      const payload = JSON.parse(event.data) as JobStatusResponse;
      setStatus(payload);
      if (payload.status === "completed" || payload.status === "failed") {
        source.close();
        eventSourceRef.current = null;
        setBusy(false);
        if (payload.status === "completed") {
          const review = await fetchReview(createdJobId);
          setReviewRows(review.rows);
        }
      }
    };
    source.onerror = () => {
      source.close();
      eventSourceRef.current = null;
      setBusy(false);
    };
  }

  async function handleSubmitReview() {
    if (!jobId) {
      return;
    }
    const selections = reviewRows.map((row) => {
      const raw = reviewSelection[row.row_index];
      if (!raw || raw === "no_match") {
        return { row_index: row.row_index, candidate_index: null, no_match: true };
      }
      return { row_index: row.row_index, candidate_index: Number(raw), no_match: false };
    });
    setBusy(true);
    try {
      await submitReview(jobId, selections);
      const refreshedStatus = await fetchStatus(jobId);
      setStatus(refreshedStatus);
      const review = await fetchReview(jobId);
      setReviewRows(review.rows);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleClearCache() {
    setBusy(true);
    try {
      await clearCache();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <section className="panel">
        <h1>StartDate Finder</h1>
        <p className="muted">
          Upload an Excel file, enrich business start dates, review ambiguous CT registry matches, and export.
        </p>
      </section>

      <section className={`panel settings-panel${busy ? " processing" : ""}`}>
        <h2>1) Upload + Settings</h2>
        <form onSubmit={handleSubmit} className="form-grid">
          <label>
            Spreadsheet (.xlsx)
            <input
              type="file"
              accept=".xlsx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <label>
            High confidence threshold: {settings?.high_confidence_threshold.toFixed(2)}
            <input
              type="range"
              min={0.5}
              max={1}
              step={0.01}
              value={settings?.high_confidence_threshold ?? 0.85}
              onChange={(event) => updateSetting("high_confidence_threshold", Number(event.target.value))}
            />
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings?.prefer_earliest_known_date ?? false}
              onChange={(event) => updateSetting("prefer_earliest_known_date", event.target.checked)}
            />
            Prefer earliest known date
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings?.enable_rdap_lookup ?? true}
              onChange={(event) => updateSetting("enable_rdap_lookup", event.target.checked)}
            />
            Enable RDAP lookup
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings?.enable_whois_fallback ?? false}
              disabled={!config?.whois_key_present}
              onChange={(event) => updateSetting("enable_whois_fallback", event.target.checked)}
            />
            Enable WhoisXML fallback ({config?.whois_key_present ? "key detected" : "no key"})
          </label>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={settings?.enable_social_hints ?? false}
              disabled={!config?.feature_social_hints_env}
              onChange={(event) => updateSetting("enable_social_hints", event.target.checked)}
            />
            Enable social hints (best effort)
          </label>

          <label>
            Minimum plausible date
            <input
              type="date"
              value={settings?.min_plausible_date ?? "1900-01-01"}
              onChange={(event) => updateSetting("min_plausible_date", event.target.value)}
            />
          </label>

          <label>
            Domain denylist (one domain per line)
            <textarea
              rows={8}
              value={denylistText}
              onChange={(event) => setDenylistText(event.target.value)}
            />
          </label>

          <div className="button-row">
            <button type="submit" disabled={!file || busy}>
              {busy ? "Working..." : "Start Processing"}
            </button>
            <button type="button" onClick={handleClearCache} disabled={busy}>
              Clear Cache
            </button>
          </div>
        </form>
        {busy ? (
          <div className="processing-overlay" aria-hidden={!busy}>
            <span>Processing...</span>
          </div>
        ) : null}
      </section>

      <section className="panel">
        <h2>2) Progress</h2>
        <div className="progress-wrap">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${status.progress_pct}%` }} />
          </div>
          <span>
            {status.progress_done}/{status.progress_total} ({status.progress_pct.toFixed(1)}%)
          </span>
        </div>
        <p className="muted">{status.message}</p>
        {status.error ? <p className="error">{status.error}</p> : null}
      </section>

      <section className="panel">
        <h2>3) Summary</h2>
        <div className="summary-grid">
          <div>Total Rows: {status.counts.total_rows}</div>
          <div>Auto-matched: {status.counts.auto_matched}</div>
          <div>Needs Review: {status.counts.needs_review}</div>
          <div>Filled via Domain: {status.counts.filled_via_domain}</div>
          <div>Filled via Social: {status.counts.filled_via_social}</div>
          <div>Not Found: {status.counts.not_found}</div>
        </div>
        {status.can_download && jobId ? (
          <a className="download-link" href={apiUrl(`/api/jobs/${jobId}/download`)}>
            Download Enriched Excel
          </a>
        ) : null}
      </section>

      <section className="panel">
        <h2>4) Review</h2>
        {reviewRows.length === 0 ? (
          <p className="muted">No review rows.</p>
        ) : (
          <>
            <div className="review-table">
              {reviewRows.map((row) => (
                <div key={row.row_index} className="review-row">
                  <div className="review-main">
                    <strong>
                      Row {row.row_index}: {row.business}
                    </strong>
                    <span>
                      {row.city} {row.zip}
                    </span>
                    <span>{row.url}</span>
                  </div>
                  <label>
                    Candidate
                    <select
                      value={reviewSelection[row.row_index] ?? "no_match"}
                      onChange={(event) =>
                        setReviewSelection((prev) => ({
                          ...prev,
                          [row.row_index]: event.target.value
                        }))
                      }
                    >
                      <option value="no_match">No match</option>
                      {row.candidates.map((candidate, idx) => (
                        <option value={String(idx)} key={`${row.row_index}-${idx}`}>
                          {candidate.name} | sim {candidate.similarity.toFixed(1)} | {candidate.city} {candidate.zip} |{" "}
                          {candidate.registration_date_raw || "no date"}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              ))}
            </div>
            <button type="button" onClick={handleSubmitReview} disabled={busy}>
              Apply Review Choices
            </button>
          </>
        )}
      </section>

      {error ? (
        <section className="panel">
          <p className="error">{error}</p>
        </section>
      ) : null}
    </main>
  );
}

export default App;
