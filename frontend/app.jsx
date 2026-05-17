const { useState, useEffect, useRef, useCallback, useMemo } = React;

// ── Utilities ──────────────────────────────────────────────────────────────

const API = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(text || `${r.status}`);
    }
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },
};

function fmtBytes(b) {
  if (b == null) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDuration(s) {
  if (s == null) return '—';
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch { return iso; }
}

function fmtShortDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

// ── Status Badge ───────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}

// ── Toast ──────────────────────────────────────────────────────────────────

function Toast({ message, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 3500);
    return () => clearTimeout(t);
  }, []);
  return <div className="toast">{message}</div>;
}

// ── Toggle ─────────────────────────────────────────────────────────────────

function Toggle({ value, onChange, label }) {
  return (
    <div className="toggle-wrap" onClick={() => onChange(!value)}>
      <div className={`toggle ${value ? 'on' : ''}`} />
      {label && <span className="text-sm text-slate-300">{label}</span>}
    </div>
  );
}

// ── Virtual Table ──────────────────────────────────────────────────────────

const ROW_HEIGHT = 36;
const VISIBLE_BUFFER = 10;

function VirtualTable({ rows, onRowClick, expandedRow }) {
  const containerRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(600);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setContainerHeight(el.clientHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const handleScroll = useCallback((e) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - VISIBLE_BUFFER);
  const visibleCount = Math.ceil(containerHeight / ROW_HEIGHT) + VISIBLE_BUFFER * 2;
  const endIdx = Math.min(rows.length, startIdx + visibleCount);
  const visibleRows = rows.slice(startIdx, endIdx);

  const totalHeight = rows.length * ROW_HEIGHT;
  const offsetY = startIdx * ROW_HEIGHT;

  const cols = [
    { key: 'source',           label: 'Source',     w: '90px'  },
    { key: 'filename',         label: 'Filename',   w: '160px' },
    { key: 'path',             label: 'Path',       w: 'auto'  },
    { key: 'modified_ts',      label: 'Modified',   w: '120px' },
    { key: 'size_bytes',       label: 'Size',       w: '80px'  },
    { key: 'match_strings',    label: 'Matched On', w: '140px' },
    { key: 'match_line_number',label: 'Line #',     w: '60px'  },
  ];

  return (
    <div
      ref={containerRef}
      className="virtual-scroll-container"
      style={{ height: '100%', overflowY: 'auto' }}
      onScroll={handleScroll}
    >
      <table className="results-table" style={{ tableLayout: 'fixed', width: '100%' }}>
        <colgroup>
          {cols.map(c => <col key={c.key} style={{ width: c.w }} />)}
        </colgroup>
        <thead>
          <tr>
            {cols.map(c => <th key={c.key}>{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {/* Top spacer */}
          {offsetY > 0 && (
            <tr style={{ height: `${offsetY}px` }}>
              <td colSpan={cols.length} style={{ padding: 0, border: 0 }} />
            </tr>
          )}

          {visibleRows.map((row, i) => {
            const absIdx = startIdx + i;
            const isExpanded = expandedRow === row.id;
            return (
              <React.Fragment key={row.id || absIdx}>
                <tr
                  className={isExpanded ? 'expanded' : ''}
                  style={{ height: ROW_HEIGHT }}
                  onClick={() => onRowClick(isExpanded ? null : row.id)}
                >
                  <td title={row.source}>{row.source}</td>
                  <td title={row.filename}>{row.filename}</td>
                  <td title={row.path} style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {row.path}
                  </td>
                  <td>{fmtShortDate(row.modified_ts)}</td>
                  <td>{fmtBytes(row.size_bytes)}</td>
                  <td>
                    {(row.match_strings || []).map((s, j) => (
                      <span key={j} className="match-tag">{s}</span>
                    ))}
                  </td>
                  <td>{row.match_line_number ?? '—'}</td>
                </tr>
                {isExpanded && (
                  <tr className="expanded">
                    <td colSpan={cols.length} style={{ padding: '0.5rem 0.75rem' }}>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                        <strong>Full path:</strong> {row.path}
                      </div>
                      {row.match_line && (
                        <pre className="match-preview">{row.match_line}</pre>
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}

          {/* Bottom spacer */}
          {totalHeight - offsetY - visibleRows.length * ROW_HEIGHT > 0 && (
            <tr style={{ height: `${totalHeight - offsetY - visibleRows.length * ROW_HEIGHT}px` }}>
              <td colSpan={cols.length} style={{ padding: 0, border: 0 }} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Configure Tab ──────────────────────────────────────────────────────────

const DEFAULT_CONFIG = {
  name: '',
  sources: {
    file_share:    { enabled: false, path: '' },
    system_log:    { enabled: false, path: '' },
    windows_event: { enabled: false, channels: ['Application', 'System', 'Security'] },
    database:      { enabled: false, connection_string: '', log_table: '', timestamp_column: 'timestamp', message_column: 'message' },
  },
  filters: {
    date_from: '',
    date_to: '',
    filename_pattern: '*.log',
    content_search: {
      enabled: false,
      strings_text: '',
      case_sensitive: false,
      match_mode: 'any',
    },
  },
  performance: {
    max_threads: 16,
    max_file_size_mb: 500,
    skip_binary: true,
  },
};

const EVENT_CHANNELS = ['Application', 'System', 'Security', 'Setup'];

function ConfigureTab({ onScanStarted }) {
  const [cfg, setCfg] = useState(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const setField = (path, val) => {
    setCfg(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const keys = path.split('.');
      let cur = next;
      for (let i = 0; i < keys.length - 1; i++) cur = cur[keys[i]];
      cur[keys[keys.length - 1]] = val;
      return next;
    });
  };

  const buildPayload = () => {
    const sources = [];
    const s = cfg.sources;

    if (s.file_share.enabled)
      sources.push({ type: 'file_share', enabled: true, path: s.file_share.path });
    if (s.system_log.enabled)
      sources.push({ type: 'system_log', enabled: true, path: s.system_log.path });
    if (s.windows_event.enabled)
      sources.push({ type: 'windows_event', enabled: true, event_channels: s.windows_event.channels });
    if (s.database.enabled)
      sources.push({
        type: 'database', enabled: true,
        connection_string: s.database.connection_string,
        log_table: s.database.log_table,
        timestamp_column: s.database.timestamp_column,
        message_column: s.database.message_column,
      });

    const cs = cfg.filters.content_search;
    return {
      name: cfg.name || 'Untitled Scan',
      sources,
      filters: {
        date_from: cfg.filters.date_from || null,
        date_to: cfg.filters.date_to || null,
        filename_pattern: cfg.filters.filename_pattern || '*',
        content_search: {
          enabled: cs.enabled,
          strings: cs.strings_text.split('\n').map(s => s.trim()).filter(Boolean),
          case_sensitive: cs.case_sensitive,
          match_mode: cs.match_mode,
        },
      },
      performance: {
        max_threads: Number(cfg.performance.max_threads),
        max_file_size_mb: Number(cfg.performance.max_file_size_mb),
        skip_binary: cfg.performance.skip_binary,
      },
    };
  };

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      const payload = buildPayload();
      const job = await API.post('/api/v1/scans', payload);
      onScanStarted(job);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleSaveYaml = () => {
    const payload = buildPayload();
    const yamlStr = jsyaml.dump(payload, { indent: 2 });
    const blob = new Blob([yamlStr], { type: 'text/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'scan_config.yaml'; a.click();
    URL.revokeObjectURL(url);
  };

  const src = cfg.sources;
  const cs = cfg.filters.content_search;

  return (
    <div style={{ maxWidth: 760 }}>
      {/* Job Name */}
      <div className="card mb-4">
        <p className="section-title">Job Name</p>
        <input
          className="form-input"
          placeholder="My Scan Job"
          value={cfg.name}
          onChange={e => setField('name', e.target.value)}
        />
      </div>

      {/* Sources */}
      <div className="card mb-4">
        <p className="section-title">Sources</p>

        {/* File Share */}
        <div className="mb-4">
          <Toggle
            value={src.file_share.enabled}
            onChange={v => setField('sources.file_share.enabled', v)}
            label="File Share / Network Drive"
          />
          {src.file_share.enabled && (
            <div className="mt-2 pl-10">
              <label className="form-label">Path (local or UNC)</label>
              <input className="form-input" placeholder="C:\Logs or \\server\share"
                value={src.file_share.path}
                onChange={e => setField('sources.file_share.path', e.target.value)} />
            </div>
          )}
        </div>

        {/* System Log */}
        <div className="mb-4">
          <Toggle
            value={src.system_log.enabled}
            onChange={v => setField('sources.system_log.enabled', v)}
            label="System Log Directory"
          />
          {src.system_log.enabled && (
            <div className="mt-2 pl-10">
              <label className="form-label">Log Directory Path</label>
              <input className="form-input" placeholder="/var/log"
                value={src.system_log.path}
                onChange={e => setField('sources.system_log.path', e.target.value)} />
            </div>
          )}
        </div>

        {/* Windows Event Log */}
        <div className="mb-4">
          <Toggle
            value={src.windows_event.enabled}
            onChange={v => setField('sources.windows_event.enabled', v)}
            label="Windows Event Log"
          />
          {src.windows_event.enabled && (
            <div className="mt-2 pl-10">
              <label className="form-label">Event Channels</label>
              <div className="flex flex-wrap gap-2">
                {EVENT_CHANNELS.map(ch => (
                  <label key={ch} className="flex items-center gap-1 text-sm text-slate-300 cursor-pointer">
                    <input type="checkbox"
                      checked={src.windows_event.channels.includes(ch)}
                      onChange={e => {
                        const chs = src.windows_event.channels;
                        setField('sources.windows_event.channels',
                          e.target.checked ? [...chs, ch] : chs.filter(c => c !== ch));
                      }} />
                    {ch}
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Database */}
        <div className="mb-0">
          <Toggle
            value={src.database.enabled}
            onChange={v => setField('sources.database.enabled', v)}
            label="Database Log Table"
          />
          {src.database.enabled && (
            <div className="mt-2 pl-10 grid grid-cols-2 gap-2">
              <div className="col-span-2">
                <label className="form-label">ODBC Connection String</label>
                <input className="form-input" placeholder="DRIVER=...;SERVER=...;DATABASE=..."
                  value={src.database.connection_string}
                  onChange={e => setField('sources.database.connection_string', e.target.value)} />
              </div>
              <div>
                <label className="form-label">Log Table</label>
                <input className="form-input" placeholder="ApplicationLogs"
                  value={src.database.log_table}
                  onChange={e => setField('sources.database.log_table', e.target.value)} />
              </div>
              <div>
                <label className="form-label">Timestamp Column</label>
                <input className="form-input" placeholder="timestamp"
                  value={src.database.timestamp_column}
                  onChange={e => setField('sources.database.timestamp_column', e.target.value)} />
              </div>
              <div>
                <label className="form-label">Message Column</label>
                <input className="form-input" placeholder="message"
                  value={src.database.message_column}
                  onChange={e => setField('sources.database.message_column', e.target.value)} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-4">
        <p className="section-title">Filters</p>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="form-label">Date From</label>
            <input type="datetime-local" className="form-input"
              value={cfg.filters.date_from}
              onChange={e => setField('filters.date_from', e.target.value)} />
          </div>
          <div>
            <label className="form-label">Date To</label>
            <input type="datetime-local" className="form-input"
              value={cfg.filters.date_to}
              onChange={e => setField('filters.date_to', e.target.value)} />
          </div>
        </div>

        <div className="mb-3">
          <label className="form-label">Filename Pattern</label>
          <input className="form-input" placeholder="*.log"
            value={cfg.filters.filename_pattern}
            onChange={e => setField('filters.filename_pattern', e.target.value)} />
        </div>

        <Toggle
          value={cs.enabled}
          onChange={v => setField('filters.content_search.enabled', v)}
          label="Content Search"
        />

        {cs.enabled && (
          <div className="mt-3 pl-10">
            <label className="form-label">Search Strings (one per line)</label>
            <textarea className="form-textarea" placeholder={"ERROR\nCRITICAL\nException"}
              value={cs.strings_text}
              onChange={e => setField('filters.content_search.strings_text', e.target.value)} />

            <div className="flex items-center gap-6 mt-2">
              <Toggle
                value={cs.case_sensitive}
                onChange={v => setField('filters.content_search.case_sensitive', v)}
                label="Case Sensitive"
              />
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-400">Match Mode:</span>
                {['any', 'all'].map(m => (
                  <label key={m} className="flex items-center gap-1 text-sm text-slate-300 cursor-pointer">
                    <input type="radio" name="match_mode" value={m}
                      checked={cs.match_mode === m}
                      onChange={() => setField('filters.content_search.match_mode', m)} />
                    {m.charAt(0).toUpperCase() + m.slice(1)}
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Performance */}
      <div className="card mb-4">
        <p className="section-title">Performance</p>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="form-label">Max Threads (1–64)</label>
            <input type="number" min="1" max="64" className="form-input"
              value={cfg.performance.max_threads}
              onChange={e => setField('performance.max_threads', e.target.value)} />
          </div>
          <div>
            <label className="form-label">Max File Size (MB)</label>
            <input type="number" min="1" className="form-input"
              value={cfg.performance.max_file_size_mb}
              onChange={e => setField('performance.max_file_size_mb', e.target.value)} />
          </div>
          <div className="flex items-end pb-1">
            <Toggle
              value={cfg.performance.skip_binary}
              onChange={v => setField('performance.skip_binary', v)}
              label="Skip Binary Files"
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="text-red-400 text-sm mb-3 p-3 bg-red-900 bg-opacity-20 rounded">{error}</div>
      )}

      <div className="flex gap-3">
        <button className="btn btn-primary" onClick={handleStart} disabled={loading}>
          {loading ? 'Starting…' : '▶ Start Scan'}
        </button>
        <button className="btn btn-secondary" onClick={handleSaveYaml}>
          ↓ Save Config as YAML
        </button>
      </div>
    </div>
  );
}

// ── Results Tab ────────────────────────────────────────────────────────────

function ResultsTab({ job, liveRows, wsState }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('');
  const [expandedRow, setExpandedRow] = useState(null);
  const [loading, setLoading] = useState(false);

  const allRows = useMemo(() => {
    const live = liveRows || [];
    const liveIds = new Set(live.map(r => r.id));
    const merged = [...live, ...rows.filter(r => !liveIds.has(r.id))];
    if (!filter) return merged;
    const f = filter.toLowerCase();
    return merged.filter(r =>
      (r.path && r.path.toLowerCase().includes(f)) ||
      (r.match_line && r.match_line.toLowerCase().includes(f)) ||
      (r.filename && r.filename.toLowerCase().includes(f))
    );
  }, [rows, liveRows, filter]);

  const loadResults = useCallback(async (pg = 1) => {
    if (!job) return;
    setLoading(true);
    try {
      const qs = `page=${pg}&page_size=200${filter ? `&filter=${encodeURIComponent(filter)}` : ''}`;
      const data = await API.get(`/api/v1/scans/${job.id}/results?${qs}`);
      setRows(data.items || []);
      setTotal(data.total || 0);
      setPage(pg);
    } catch {}
    setLoading(false);
  }, [job, filter]);

  useEffect(() => {
    if (job && job.status !== 'running') {
      loadResults(1);
    }
  }, [job?.id, job?.status]);

  const exportCsv = () => {
    if (!allRows.length) return;
    const cols = ['source', 'filename', 'path', 'modified_ts', 'size_bytes', 'match_line', 'match_line_number', 'match_strings'];
    const header = cols.join(',');
    const escape = v => {
      if (v == null) return '';
      const s = Array.isArray(v) ? v.join('; ') : String(v);
      return `"${s.replace(/"/g, '""')}"`;
    };
    const lines = allRows.map(r => cols.map(c => escape(r[c])).join(','));
    const blob = new Blob([header + '\n' + lines.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scan_${job?.id?.slice(0, 8) || 'results'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isRunning = job?.status === 'running';
  const progress = job ? (job.matches_found > 0 ? Math.min(99, job.files_scanned / Math.max(job.files_scanned, 1) * 100) : 0) : 0;

  if (!job) {
    return (
      <div className="text-slate-500 text-sm mt-8 text-center">
        No scan selected. Configure and start a scan, or click a job in the sidebar.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
      {/* Header */}
      <div className="mb-3">
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-lg font-semibold text-slate-100">{job.name}</h2>
          <StatusBadge status={job.status} />
          {wsState && <span className="text-xs text-blue-400">{wsState}</span>}
        </div>

        <div className="stats-row mb-3">
          {[
            { label: 'Files Scanned', value: job.files_scanned ?? 0 },
            { label: 'Matches Found', value: job.matches_found ?? 0 },
            { label: 'Errors',        value: job.errors_count ?? 0  },
            { label: 'Duration',      value: fmtDuration(job.duration_seconds) },
          ].map(s => (
            <div key={s.label} className="stat-chip">
              <span className="stat-value">{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          ))}
        </div>

        {isRunning && (
          <div className="progress-bar mb-3">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        )}

        <div className="flex items-center gap-2">
          <input
            className="form-input"
            style={{ maxWidth: 320 }}
            placeholder="Filter by path or match text…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
          <button className="btn btn-secondary btn-sm" onClick={() => loadResults(1)}>
            ↻ Refresh
          </button>
          <button className="btn btn-secondary btn-sm" onClick={exportCsv}>
            ↓ Export CSV
          </button>
          <span className="text-slate-500 text-xs ml-2">{allRows.length} rows shown</span>
        </div>
      </div>

      {/* Table */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {loading ? (
          <div className="text-slate-500 text-sm mt-6 text-center">Loading…</div>
        ) : allRows.length === 0 ? (
          <div className="text-slate-500 text-sm mt-6 text-center">
            {isRunning ? 'Waiting for matches…' : 'No results found.'}
          </div>
        ) : (
          <VirtualTable
            rows={allRows}
            expandedRow={expandedRow}
            onRowClick={id => setExpandedRow(id)}
          />
        )}
      </div>
    </div>
  );
}

// ── Logs Tab ───────────────────────────────────────────────────────────────

function LogsTab() {
  const [logFiles, setLogFiles] = useState([]);
  const [selectedLog, setSelectedLog] = useState(null);
  const [logContent, setLogContent] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const viewerRef = useRef(null);

  useEffect(() => {
    API.get('/api/v1/logs').then(setLogFiles).catch(() => {});
  }, []);

  useEffect(() => {
    if (autoScroll && viewerRef.current) {
      viewerRef.current.scrollTop = viewerRef.current.scrollHeight;
    }
  }, [logContent, autoScroll]);

  const loadLog = async (filename) => {
    setSelectedLog(filename);
    try {
      const r = await fetch(`/api/v1/logs/${encodeURIComponent(filename)}`);
      setLogContent(await r.text());
    } catch { setLogContent('Error loading log file.'); }
  };

  const renderLogLines = () => {
    return logContent.split('\n').map((line, i) => {
      let cls = 'log-line-info';
      try {
        const obj = JSON.parse(line);
        if (obj.level === 'ERROR') cls = 'log-line-error';
        else if (obj.level === 'WARN') cls = 'log-line-warn';
      } catch {}
      return <div key={i} className={cls}>{line}</div>;
    });
  };

  return (
    <div className="flex gap-4" style={{ height: 'calc(100vh - 160px)' }}>
      {/* File list */}
      <div className="card" style={{ width: 280, overflowY: 'auto', flexShrink: 0 }}>
        <p className="section-title mb-2">Scan Log Files</p>
        {logFiles.length === 0 ? (
          <p className="text-slate-500 text-xs">No log files yet.</p>
        ) : logFiles.map(f => (
          <div
            key={f.name}
            className={`job-item ${selectedLog === f.name ? 'active' : ''}`}
            onClick={() => loadLog(f.name)}
          >
            <div className="text-xs text-slate-200 font-mono truncate">{f.name}</div>
            <div className="text-xs text-slate-500 mt-0.5">
              {fmtBytes(f.size)} · {fmtShortDate(f.modified)}
            </div>
          </div>
        ))}
      </div>

      {/* Log viewer */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="flex items-center gap-3 mb-2">
          <span className="text-sm text-slate-300 font-mono">{selectedLog || 'Select a log file'}</span>
          <Toggle value={autoScroll} onChange={setAutoScroll} label="Auto-scroll" />
          {selectedLog && (
            <button className="btn btn-secondary btn-sm"
              onClick={() => loadLog(selectedLog)}>
              ↻ Reload
            </button>
          )}
        </div>
        <div ref={viewerRef} className="log-viewer" style={{ flex: 1 }}>
          {logContent ? renderLogLines() : (
            <span className="text-slate-600">Select a log file to view its contents.</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────

function Sidebar({ jobs, activeJobId, onSelectJob, collapsed }) {
  return (
    <div className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div style={{ padding: '0.75rem' }}>
        <p className="section-title">Recent Jobs</p>
      </div>
      {jobs.length === 0 && (
        <p className="text-slate-600 text-xs px-3 pb-3">No jobs yet.</p>
      )}
      {jobs.map(job => (
        <div
          key={job.id}
          className={`job-item ${activeJobId === job.id ? 'active' : ''}`}
          onClick={() => onSelectJob(job)}
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-200 truncate" style={{ maxWidth: 160 }}>
              {job.name || 'Untitled'}
            </span>
            <StatusBadge status={job.status} />
          </div>
          <div className="text-xs text-slate-500">{fmtShortDate(job.created_at)}</div>
        </div>
      ))}
    </div>
  );
}

// ── App Root ───────────────────────────────────────────────────────────────

function App() {
  const [tab, setTab] = useState('configure');
  const [jobs, setJobs] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [backendOk, setBackendOk] = useState(null);
  const [toast, setToast] = useState(null);
  const [liveRows, setLiveRows] = useState([]);
  const [wsState, setWsState] = useState('');
  const wsRef = useRef(null);

  // Health check
  useEffect(() => {
    const check = async () => {
      try {
        await API.get('/health');
        setBackendOk(true);
      } catch { setBackendOk(false); }
    };
    check();
    const t = setInterval(check, 30000);
    return () => clearInterval(t);
  }, []);

  // Load job list
  const refreshJobs = useCallback(async () => {
    try {
      const list = await API.get('/api/v1/scans');
      setJobs(list);
      // Update activeJob stats from list
      if (activeJob) {
        const updated = list.find(j => j.id === activeJob.id);
        if (updated) setActiveJob(prev => ({ ...prev, ...updated }));
      }
    } catch {}
  }, [activeJob?.id]);

  useEffect(() => {
    refreshJobs();
    const t = setInterval(refreshJobs, 5000);
    return () => clearInterval(t);
  }, [refreshJobs]);

  const openWebSocket = useCallback((jobId) => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setLiveRows([]);

    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/scans/${jobId}`);
    wsRef.current = ws;
    setWsState('● Live');

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);

      if (msg.type === 'match') {
        const row = {
          id: `live-${Date.now()}-${Math.random()}`,
          path: msg.path,
          filename: msg.filename,
          match_line: msg.match_line,
          match_line_number: msg.match_line_number,
          match_strings: msg.match_strings || [],
          source: 'live',
          modified_ts: null,
          size_bytes: null,
        };
        setLiveRows(prev => [row, ...prev].slice(0, 500));
      }

      if (msg.type === 'progress') {
        setActiveJob(prev => prev ? {
          ...prev,
          files_scanned: msg.files_scanned,
          matches_found: msg.matches_found,
          errors_count: msg.errors_count,
        } : prev);
      }

      if (msg.type === 'complete') {
        setWsState('');
        setToast(`Scan complete — ${msg.matches_found} matches in ${fmtDuration(msg.duration_seconds)}`);
        setActiveJob(prev => prev ? { ...prev, status: msg.status, ...msg } : prev);
        ws.close();
        refreshJobs();
      }
    };

    ws.onerror = () => setWsState('');
    ws.onclose = () => setWsState('');
  }, [refreshJobs]);

  const handleScanStarted = useCallback((job) => {
    setActiveJob({ ...job, files_scanned: 0, matches_found: 0, errors_count: 0 });
    setLiveRows([]);
    setTab('results');
    openWebSocket(job.id);
    refreshJobs();
  }, [openWebSocket, refreshJobs]);

  const handleSelectJob = useCallback(async (job) => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setWsState('');
    setLiveRows([]);

    try {
      const detail = await API.get(`/api/v1/scans/${job.id}`);
      setActiveJob(detail);
    } catch {
      setActiveJob(job);
    }

    if (job.status === 'running') {
      openWebSocket(job.id);
    }
    setTab('results');
  }, [openWebSocket]);

  const handleCancelJob = useCallback(async () => {
    if (!activeJob) return;
    try {
      await API.del(`/api/v1/scans/${activeJob.id}`);
    } catch {}
  }, [activeJob]);

  const handleExit = useCallback(async () => {
    if (!confirm('Shut down FileScanr and close the browser tab?')) return;
    try {
      await fetch('/api/v1/shutdown', { method: 'POST' });
    } catch {}
    window.close();
  }, []);

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <button
          className="text-slate-400 hover:text-slate-200 mr-1"
          onClick={() => setSidebarCollapsed(c => !c)}
          title="Toggle sidebar"
        >☰</button>

        <span className="text-white font-bold text-lg">FileScanr</span>
        <span className="badge badge-running" style={{ background: '#0f3460', color: '#60a5fa' }}>v1.0</span>

        <div className="ml-auto flex items-center gap-3">
          {activeJob?.status === 'running' && (
            <button className="btn btn-danger btn-sm" onClick={handleCancelJob}>
              ■ Cancel Job
            </button>
          )}
          <div className="flex items-center gap-1.5">
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: backendOk === null ? '#64748b' : backendOk ? '#22c55e' : '#ef4444',
              display: 'inline-block'
            }} />
            <span className="text-xs text-slate-400">
              {backendOk === null ? 'Checking…' : backendOk ? 'Backend online' : 'Backend offline'}
            </span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={handleExit} title="Shut down server and close tab">
            ⏻ Exit
          </button>
        </div>
      </nav>

      {/* Sidebar */}
      <Sidebar
        jobs={jobs}
        activeJobId={activeJob?.id}
        onSelectJob={handleSelectJob}
        collapsed={sidebarCollapsed}
      />

      {/* Main */}
      <main className={`main-content ${sidebarCollapsed ? 'expanded' : ''}`}>
        <div className="tab-bar">
          {[
            { id: 'configure', label: '⚙ Configure' },
            { id: 'results',   label: '📋 Results'  },
            { id: 'logs',      label: '📄 Logs'     },
          ].map(t => (
            <button
              key={t.id}
              className={`tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'configure' && <ConfigureTab onScanStarted={handleScanStarted} />}
        {tab === 'results'   && (
          <ResultsTab job={activeJob} liveRows={liveRows} wsState={wsState} />
        )}
        {tab === 'logs'      && <LogsTab />}
      </main>

      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
