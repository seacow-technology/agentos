/* global window */
(function () {
  const $ = (sel) => document.querySelector(sel);
  const app = $('#app');

  const state = {
    route: (location.hash || '#/home').replace('#', ''),
    tasks: [],
    modal: { open: false, kind: null, taskId: null, repoPath: null, status: '' },
    savings: { tokens: null, usd: null, minutes: null, explain: 'We only show numbers backed by evidence. Notes may apply.' },
    savingsNotes: [],
    savingsConfidence: { tokens: 'none', cost: 'none', time: 'none' },
    savingsWindow: null,
  };

  async function copyText(txt) {
    const text = String(txt || '');
    if (!text) return false;
    try {
      if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch {
      // ignore
    }
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return !!ok;
    } catch {
      return false;
    }
  }

  function navTo(route) {
    location.hash = `#${route}`;
  }

  function formatStatus(s) {
    const raw = String(s || '').toLowerCase();
    if (raw === 'succeeded' || raw === 'success') return 'Succeeded';
    if (raw === 'failed') return 'Failed';
    if (raw === 'awaiting_approval') return 'Needs approval';
    if (raw === 'planning') return 'Planning';
    if (raw === 'executing') return 'Running';
    return raw ? raw.replace(/_/g, ' ') : 'Unknown';
  }

  function adminToken() {
    try {
      // Electron preload sets this for Console. Product can reuse it.
      return window.localStorage.getItem('octopusos_admin_token') || (window.octo && window.octo.getAdminTokenSync && window.octo.getAdminTokenSync()) || '';
    } catch {
      return '';
    }
  }

  async function api(method, url, body) {
    const headers = { 'Content-Type': 'application/json' };
    const t = adminToken();
    if (t) headers['x-admin-token'] = t;
    const resp = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const data = await resp.json().catch(() => null);
    if (!resp.ok) {
      const msg = (data && (data.error || data.detail)) || `HTTP ${resp.status}`;
      throw new Error(msg);
    }
    return data;
  }

  async function refreshTasks() {
    try {
      const res = await api('GET', '/api/product/tasks?limit=20');
      state.tasks = (res && res.tasks) || [];
    } catch {
      // backend might not have product endpoints yet; keep UI usable.
      state.tasks = [];
    }
    render();
  }

  async function refreshInsights() {
    try {
      const tz = (Intl && Intl.DateTimeFormat && Intl.DateTimeFormat().resolvedOptions && Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC';
      const res = await api('GET', `/api/product/insights/week?tz=${encodeURIComponent(tz)}`);
      const ok = res && res.ok;
      if (!ok) throw new Error('bad insights response');
      const tokens = (typeof res.tokens_used === 'number') ? res.tokens_used : null;
      const usd = res.cost_estimated && typeof res.cost_estimated.amount === 'number' ? res.cost_estimated.amount : null;
      const mins = res.time_saved_minutes && typeof res.time_saved_minutes.amount === 'number' ? res.time_saved_minutes.amount : null;
      state.savings.tokens = tokens;
      state.savings.usd = usd;
      state.savings.minutes = mins;
      state.savingsNotes = (res.notes && Array.isArray(res.notes)) ? res.notes : [];
      state.savingsConfidence = {
        tokens: res.tokens_used_confidence || 'none',
        cost: (res.cost_estimated && res.cost_estimated.confidence) || 'none',
        time: (res.time_saved_minutes && res.time_saved_minutes.confidence) || 'none',
      };
      state.savingsWindow = { start: res.week_start, end: res.week_end, tz: res.tz };
    } catch {
      // Keep placeholders if backend doesn't have endpoint yet.
      state.savingsNotes = [];
    }
    render();
  }

  function openModal(kind, payload) {
    state.modal.open = true;
    state.modal.kind = kind;
    state.modal.taskId = (payload && payload.taskId) || null;
    state.modal.repoPath = (payload && payload.repoPath) || null;
    state.modal.status = '';
    state.modal.data = null;
    state.modal.tab = 'summary';
    state.modal.copyFallbackText = '';
    render();
    if (kind === 'plan' && state.modal.taskId) void loadPlan(state.modal.taskId);
    if (kind === 'evidence' && state.modal.taskId) void loadEvidence(state.modal.taskId);
    if (kind === 'replay' && state.modal.taskId) void loadReplay(state.modal.taskId);
  }

  function closeModal() {
    state.modal.open = false;
    state.modal.kind = null;
    state.modal.taskId = null;
    state.modal.repoPath = null;
    state.modal.status = '';
    state.modal.data = null;
    state.modal.copyFallbackText = '';
    render();
  }

  async function chooseRepo() {
    if (!window.octo || !window.octo.pickRepoDirectory) {
      state.modal.status = 'Folder picker not available (missing preload bridge).';
      render();
      return;
    }
    const p = await window.octo.pickRepoDirectory();
    if (p) state.modal.repoPath = p;
    render();
  }

  async function runAnalyze() {
    const repoPath = (state.modal.repoPath || '').trim();
    if (!repoPath) {
      state.modal.status = 'Pick a repository folder first.';
      render();
      return;
    }
    state.modal.status = 'Starting...';
    render();
    try {
      const res = await api('POST', '/api/product/actions/run', { action_id: 'analyze_repo', payload: { repo_path: repoPath } });
      state.modal.taskId = res && (res.ui_task_ref || res.task_id) || null;
      state.modal.status = 'Running. You will see results under Recent tasks.';
      render();
      await refreshTasks();
    } catch (e) {
      state.modal.status = `Failed: ${String(e && e.message ? e.message : e)}`;
      render();
    }
  }

  async function loadPlan(taskId) {
    state.modal.status = 'Loading plan...';
    render();
    try {
      const res = await api('GET', `/api/product/tasks/${encodeURIComponent(taskId)}/plan`);
      state.modal.data = res && res.plan ? res.plan : null;
      state.modal.status = '';
      render();
    } catch (e) {
      state.modal.status = `Failed: ${String(e && e.message ? e.message : e)}`;
      render();
    }
  }

  async function loadEvidence(taskId) {
    state.modal.status = 'Loading evidence...';
    render();
    try {
      const tz = (Intl && Intl.DateTimeFormat && Intl.DateTimeFormat().resolvedOptions && Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC';
      const res = await api('GET', `/api/product/tasks/${encodeURIComponent(taskId)}/evidence?tz=${encodeURIComponent(tz)}`);
      state.modal.data = res && res.evidence ? res.evidence : null;
      state.modal.status = '';
      render();
    } catch (e) {
      state.modal.status = `Failed: ${String(e && e.message ? e.message : e)}`;
      render();
    }
  }

  async function loadReplay(taskId) {
    // v1: product replay pack (summary + timeline + evidence)
    state.modal.status = 'Loading replay...';
    render();
    try {
      const tz = (Intl && Intl.DateTimeFormat && Intl.DateTimeFormat().resolvedOptions && Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC';
      const res = await api('GET', `/api/product/tasks/${encodeURIComponent(taskId)}/replay?tz=${encodeURIComponent(tz)}`);
      state.modal.data = res && res.replay ? res.replay : null;
      state.modal.status = '';
      render();
    } catch (e) {
      state.modal.status = `Failed: ${String(e && e.message ? e.message : e)}`;
      render();
    }
  }

  async function openConsole() {
    if (window.octo && window.octo.openSystemConsole) await window.octo.openSystemConsole();
  }

  function renderHome() {
    const tasksHtml = state.tasks.slice(0, 6).map((t) => {
      const title = t.title || 'Task';
      const status = formatStatus(t.status);
      const preview = t.result_preview || '';
      return `
        <div class="task">
          <div>
            <div class="title">${escapeHtml(title)}</div>
            <div class="meta">${escapeHtml(status)}${preview ? ' · ' + escapeHtml(preview) : ''}</div>
          </div>
          <div class="actions">
            <button class="chip" data-act="plan" data-id="${escapeAttr(t.ui_task_ref || t.task_id || '')}">Plan</button>
            <button class="chip" data-act="evidence" data-id="${escapeAttr(t.ui_task_ref || t.task_id || '')}">Evidence</button>
            <button class="chip" data-act="replay" data-id="${escapeAttr(t.ui_task_ref || t.task_id || '')}">Replay</button>
          </div>
        </div>`;
    }).join('');

    return `
      <div class="topbar">
        <div class="promise">
          <div>Default read-only. Any write action must show a plan and wait for your approval.</div>
          <div>Every task emits a replayable evidence chain: inputs, decisions, outputs, and links.</div>
        </div>
        <button class="gear" data-act="console">System Console</button>
      </div>
      <div class="grid">
        <div class="card">
          <div class="hd">
            <h2>Today, what do you want to finish?</h2>
            <p>One-click actions. Advanced setup stays in System Console.</p>
          </div>
          <div class="bd">
            <div class="btns">
              <button class="btn primary" data-act="hero-analyze">
                Analyze a repo
                <small>Structure, TODO/FIXME, deps risk, git hotspots, secret risks. Evidence in 10s.</small>
              </button>
              <button class="btn" data-act="hero-soon">
                Clean up my machine
                <small>Coming soon (opens Console for advanced setup)</small>
              </button>
              <button class="btn" data-act="hero-soon">
                Draft content (cost controlled)
                <small>Coming soon (opens Console for advanced setup)</small>
              </button>
              <button class="btn" data-act="hero-soon">
                Debug a build failure
                <small>Coming soon (opens Console for advanced setup)</small>
              </button>
              <button class="btn" data-act="hero-soon">
                Ship a release safely
                <small>Coming soon (opens Console for advanced setup)</small>
              </button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="hd">
            <div class="kpiTitleRow">
              <h2 style="margin:0">This week saved</h2>
              <div class="infoDot" title="${escapeAttr(buildSavingsTooltip())}">i</div>
            </div>
            <p>Transparent numbers with confidence + notes.</p>
          </div>
          <div class="bd">
            <div class="kpi">
              <div class="kpiRow">
                <div>
                  <div class="label">Tokens</div>
                  <div class="hint">Prompt + completion, per provider accounting.</div>
                </div>
                <div class="value">${state.savings.tokens === null ? '—' : escapeHtml(String(state.savings.tokens))}</div>
              </div>
              <div class="kpiRow">
                <div>
                  <div class="label">Cost</div>
                  <div class="hint">${escapeHtml(state.savingsNotes.join(' ') || state.savings.explain)}</div>
                </div>
                <div class="value">${state.savings.usd === null ? '—' : ('$' + escapeHtml(String(state.savings.usd.toFixed(2))))}</div>
              </div>
              <div class="kpiRow">
                <div>
                  <div class="label">Time</div>
                  <div class="hint">Based on replay steps + tool runtimes.</div>
                </div>
                <div class="value">${state.savings.minutes === null ? '—' : (escapeHtml(String(state.savings.minutes)) + 'm')}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="hd">
            <h2>Recent tasks</h2>
            <p>Plan → Approve → Result → Evidence → Replay (timeline).</p>
          </div>
          <div class="bd">
            <div class="tasks">${tasksHtml || '<div style="color: rgba(255,255,255,0.55)">No tasks yet.</div>'}</div>
          </div>
        </div>
      </div>
    `;
  }

  function renderTasks() {
    return `
      <div class="topbar">
        <div class="promise">Task stream. Each card is replayable; approvals are explicit.</div>
        <button class="gear" data-act="console">System Console</button>
      </div>
      <div class="card">
        <div class="hd"><h2>Tasks</h2><p>Tasks created from Hero actions live here.</p></div>
        <div class="bd">
          <div class="tasks">${state.tasks.map((t) => `
            <div class="task">
              <div>
                <div class="title">${escapeHtml(t.title || 'Task')}</div>
                <div class="meta">${escapeHtml(formatStatus(t.status))}${t.result_preview ? ' · ' + escapeHtml(t.result_preview) : ''}</div>
              </div>
              <div class="actions">
                <button class="chip" data-act="plan" data-id="${escapeAttr(t.ui_task_ref || t.task_id || '')}">Plan</button>
                <button class="chip" data-act="evidence" data-id="${escapeAttr(t.ui_task_ref || t.task_id || '')}">Evidence</button>
                <button class="chip" data-act="replay" data-id="${escapeAttr(t.ui_task_ref || t.task_id || '')}">Replay</button>
              </div>
            </div>`).join('') || '<div style="color: rgba(255,255,255,0.55)">No tasks yet.</div>'}</div>
        </div>
      </div>
    `;
  }

  function renderEmbed(title, consolePath) {
    const safeTitle = escapeHtml(String(title || ''));
    const p = String(consolePath || '').trim() || '/';
    const src = `/console${p}${p.includes('?') ? '&' : '?'}embed=1`;
    return `
      <div class="embed">
        <div class="topbar">
          <div class="promise">${safeTitle} · Powered by OctopusOS Console (embedded)</div>
          <button class="gear" data-act="console">System Console</button>
        </div>
        <div class="card embedCard">
          <div class="bd embedBody">
            <iframe class="embedFrame" title="${escapeAttr(safeTitle)}" src="${escapeAttr(src)}"></iframe>
          </div>
        </div>
      </div>
    `;
  }

  function renderPlaceholder(title, subtitle) {
    return `
      <div class="topbar">
        <div class="promise">${escapeHtml(subtitle || '')}</div>
        <button class="gear" data-act="console">System Console</button>
      </div>
      <div class="card">
        <div class="hd"><h2>${escapeHtml(title)}</h2><p>v1 ships with Home + Work + Analyze repo first.</p></div>
        <div class="bd" style="color: rgba(255,255,255,0.60)">
          This tab is intentionally minimal in v1. Configuration and deep system views stay in the System Console.
        </div>
      </div>
    `;
  }

  function renderModal() {
    const open = state.modal.open;
    if (!open) return '';

    if (state.modal.kind === 'analyze') {
      const p = state.modal.repoPath || '';
      return `
        <div class="modal open" data-act="modal-bg">
          <div class="dialog" role="dialog" aria-modal="true">
            <div class="dh">
              <strong>Analyze a repo</strong>
              <div class="close" data-act="modal-close">Close</div>
            </div>
            <div class="db">
              <div class="drop">
                <div class="row">
                  <div style="max-width: 72%">
                    <div style="font-size: 13px; color: rgba(255,255,255,0.84)">Repository folder</div>
                    <div class="mono" title="${escapeAttr(p)}">${escapeHtml(p || 'Choose a folder. (Drag support lands later; v1 is explicit.)')}</div>
                  </div>
                  <div style="display:flex; gap: 8px;">
                    <button class="chip" data-act="pick-repo">Choose folder</button>
                    <button class="chip" data-act="run-analyze">Run</button>
                  </div>
                </div>
              </div>
              <div class="statusLine ${state.modal.status.startsWith('Failed') ? 'bad' : (state.modal.status.startsWith('Running') ? 'good' : '')}">
                ${escapeHtml(state.modal.status || 'Default read-only. This action only reads the repo and writes evidence into outputs/.')}
              </div>
            </div>
          </div>
        </div>
      `;
    }

    if (state.modal.kind === 'plan') {
      const plan = state.modal.data;
      const summary = plan && plan.summary ? plan.summary : [];
      const writes = plan && plan.writes ? plan.writes : [];
      return `
        <div class="modal open" data-act="modal-bg">
          <div class="dialog" role="dialog" aria-modal="true">
            <div class="dh">
              <strong>Plan</strong>
              <div class="close" data-act="modal-close">Close</div>
            </div>
            <div class="db">
              ${state.modal.status ? `<div class="statusLine">${escapeHtml(state.modal.status)}</div>` : ''}
              ${plan ? `
                <div style="margin-bottom: 12px; color: rgba(255,255,255,0.86); font-weight: 650">${escapeHtml(plan.title || 'Plan')}</div>
                <div style="color: rgba(255,255,255,0.65); font-size: 13px; margin-bottom: 10px">What it will do:</div>
                <ul style="margin: 0 0 14px 16px; color: rgba(255,255,255,0.82); font-size: 13px; line-height: 1.55">
                  ${summary.map((x) => `<li>${escapeHtml(x)}</li>`).join('') || '<li>(empty)</li>'}
                </ul>
                <div style="color: rgba(255,255,255,0.65); font-size: 13px; margin-bottom: 10px">Evidence outputs:</div>
                <ul style="margin: 0 0 0 16px; color: rgba(255,255,255,0.82); font-size: 13px; line-height: 1.55">
                  ${writes.map((x) => `<li><span class="mono">${escapeHtml(x)}</span></li>`).join('') || '<li>(none)</li>'}
                </ul>
              ` : ''}
            </div>
          </div>
        </div>
      `;
    }

    if (state.modal.kind === 'evidence') {
      const ev = state.modal.data;
      const files = ev && ev.files ? ev.files : {};
      const base = ev && ev.download_base ? ev.download_base : '';
      const bmeta = ev && ev.bundle_meta ? ev.bundle_meta : null;
      const shareReady = ev && ev.copy_text;
      const link = (name) => (name ? `<a class="chip" style="text-decoration:none" href="${base}/${encodeURIComponent(name)}" target="_blank" rel="noreferrer">Download ${escapeHtml(name)}</a>` : '');
      const exportBtn = (files.bundle && base)
        ? `<a class="btn primary" style="display:inline-block; text-decoration:none" href="${base}/${encodeURIComponent(files.bundle)}" target="_blank" rel="noreferrer">
             Export evidence bundle (.zip)
             <small>${bmeta && bmeta.bytes ? escapeHtml(String(Math.round((bmeta.bytes / (1024 * 1024)) * 10) / 10)) + ' MB' : 'downloadable'} · sha256 visible</small>
           </a>`
        : `<div style="color: rgba(255,255,255,0.55); font-size: 13px">Bundle not ready yet.</div>`;
      return `
        <div class="modal open" data-act="modal-bg">
          <div class="dialog" role="dialog" aria-modal="true">
            <div class="dh">
              <strong>Evidence</strong>
              <div class="close" data-act="modal-close">Close</div>
            </div>
            <div class="db">
              ${state.modal.status ? `<div class="statusLine">${escapeHtml(state.modal.status)}</div>` : ''}
              ${state.modal.copyFallbackText ? `<textarea class="mono" style="width:100%; height: 140px; margin: 10px 0; padding: 10px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.10); background: rgba(0,0,0,0.25); color: rgba(255,255,255,0.86)">${escapeHtml(state.modal.copyFallbackText)}</textarea>` : ''}
              ${ev ? `
                <div style="margin-bottom: 12px; color: rgba(255,255,255,0.70); font-size: 13px">
                  Evidence lives on disk: <span class="mono">${escapeHtml(ev.out_dir || '')}</span>
                </div>
                <div style="display:flex; gap: 10px; align-items:center; flex-wrap: wrap; margin-bottom: 12px">
                  <button class="copyBtn" data-act="share" ${shareReady ? '' : 'disabled'} title="${shareReady ? 'Copy share text' : 'Share text not ready yet'}">Share</button>
                  ${exportBtn}
                </div>
                ${bmeta && bmeta.sha256 ? `
                  <div style="margin-bottom: 12px; color: rgba(255,255,255,0.70); font-size: 13px">
                    Bundle sha256: <span class="mono" title="${escapeAttr(bmeta.sha256)}">${escapeHtml(bmeta.sha256)}</span>
                  </div>
                ` : ''}
                <div style="display:flex; flex-wrap: wrap; gap: 10px; align-items:center">
                  ${link(files.report)}
                  ${link(files.timeline)}
                  ${files.bundle ? link(files.bundle) : ''}
                </div>
              ` : ''}
            </div>
          </div>
        </div>
      `;
    }

    if (state.modal.kind === 'replay') {
      const rp = state.modal.data || null;
      const taskRef = rp && rp.task_ref ? rp.task_ref : '';
      const actionId = rp && rp.action_id ? rp.action_id : '';
      const genAt = rp && rp.generated_at ? rp.generated_at : '';
      const summary = rp && rp.summary ? rp.summary : {};
      const headline = summary && summary.headline ? summary.headline : '';
      const metricsLine = summary && summary.metrics_line ? summary.metrics_line : '';
      const notes = summary && summary.notes ? summary.notes : [];
      const inputs = summary && summary.inputs ? summary.inputs : {};
      const timeline = rp && rp.timeline ? rp.timeline : [];
      const ev = rp && rp.evidence ? rp.evidence : {};
      const bundle = ev && ev.bundle ? ev.bundle : {};
      const files = ev && ev.files ? ev.files : [];
      const copyTxt = (rp && rp.copy_text) || '';

      const header = `
        <div class="row2">
          <div>
            <div style="font-size:14px; font-weight:750; color: rgba(255,255,255,0.92)">Replay · ${escapeHtml(taskRef)} · ${escapeHtml(actionId || 'action')}</div>
            <div style="margin-top:6px; color: rgba(255,255,255,0.62); font-size:12px">
              <span class="pill">Read-only</span>
              <span class="pill">Generated ${escapeHtml(genAt || '—')}</span>
              <span class="pill">Policy: applied</span>
            </div>
          </div>
          <div style="display:flex; gap: 8px; justify-content:flex-end; flex-wrap: wrap">
            <button class="copyBtn" data-act="share">Share</button>
            ${bundle && bundle.download_url ? `<a class="copyBtn" style="text-decoration:none" href="${escapeAttr(bundle.download_url)}" target="_blank" rel="noreferrer">Export bundle (.zip)</a>` : ''}
            <button class="copyBtn" data-act="modal-close">Close</button>
          </div>
        </div>
      `;

      const tabs = `
        <div class="tabs">
          <button class="tab ${state.modal.tab === 'summary' ? 'active' : ''}" data-act="replay-tab-summary">Summary</button>
          <button class="tab ${state.modal.tab === 'timeline' ? 'active' : ''}" data-act="replay-tab-timeline">Timeline</button>
          <button class="tab ${state.modal.tab === 'evidence' ? 'active' : ''}" data-act="replay-tab-evidence">Evidence</button>
        </div>
      `;

      const renderSummary = () => `
        <div>
          <div style="font-size:16px; font-weight:800; margin-bottom: 8px">${escapeHtml(headline || 'Task replay')}</div>
          <div style="color: rgba(255,255,255,0.82); font-size: 13px; margin-bottom: 10px">${escapeHtml(metricsLine || '(no metrics yet)')}</div>
          <div class="hr"></div>
          <div style="color: rgba(255,255,255,0.65); font-size: 13px; margin-bottom: 8px">Notes (transparent):</div>
          <ul style="margin: 0 0 0 16px; color: rgba(255,255,255,0.82); font-size: 13px; line-height: 1.55">
            ${(notes || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('') || '<li>(none)</li>'}
          </ul>
          <div class="hr"></div>
          <details>
            <summary style="cursor:pointer; color: rgba(255,255,255,0.70); font-size: 13px">Inputs</summary>
            <div style="margin-top: 10px" class="kv">
              <div class="k">Repo path</div><div class="mono" title="${escapeAttr(inputs.repo_path || '')}">${escapeHtml(inputs.repo_path || '—')}</div>
              <div class="k">Audit depth</div><div>${escapeHtml(inputs.audit_depth || '—')}</div>
              <div class="k">Read-only</div><div>${escapeHtml(String(inputs.read_only !== false))}</div>
            </div>
          </details>
        </div>
      `;

      const renderTimeline = () => `
        <div>
          ${(timeline && timeline.length) ? `
            <div style="display:flex; flex-direction:column; gap: 10px">
              ${timeline.map((t) => `
                <div class="task">
                  <div>
                    <div class="title">${escapeHtml(t.label || t.stage || 'step')}</div>
                    <div class="meta">
                      <span class="pill ${t.ok ? 'ok' : 'bad'}">${escapeHtml(t.stage || 'stage')}</span>
                      ${escapeHtml(String(t.duration_ms || 0))}ms
                      ${t.detail ? ' · ' + escapeHtml(t.detail) : ''}
                    </div>
                  </div>
                  <div></div>
                </div>
              `).join('')}
            </div>
          ` : `<div style="color: rgba(255,255,255,0.55)">No timeline available yet.</div>`}
        </div>
      `;

      const renderEvidence = () => {
        const bsha = (bundle && bundle.sha256) ? bundle.sha256 : '';
        const bbytes = (bundle && bundle.bytes) ? bundle.bytes : null;
        const bfile = (bundle && bundle.filename) ? bundle.filename : 'evidence_bundle.zip';
        const bdl = (bundle && bundle.download_url) ? bundle.download_url : '';
        const bsize = (bbytes !== null && bbytes !== undefined) ? `${Math.round((bbytes / (1024 * 1024)) * 10) / 10} MB` : '—';

        const fileRows = (files || []).map((f) => `
          <div class="fileItem">
            <div>
              <div class="mono" title="${escapeAttr(f.path || '')}">${escapeHtml(f.path || '')}</div>
              <div class="meta">${escapeHtml(String(f.bytes || 0))} bytes</div>
            </div>
            <div style="display:flex; gap: 8px; align-items:center; justify-content:flex-end; flex-wrap:wrap">
              ${f.sha256 ? `<span class="mono" title="${escapeAttr(f.sha256)}">${escapeHtml(f.sha256)}</span>` : ''}
              ${f.sha256 ? `<button class="copyBtn" data-act="copy-sha" data-sha="${escapeAttr(f.sha256)}">Copy</button>` : ''}
            </div>
          </div>
        `).join('');

        return `
          <div>
            <div style="font-size: 13px; color: rgba(255,255,255,0.70); margin-bottom: 10px">Bundle</div>
            <div class="fileItem">
              <div>
                <div class="mono">${escapeHtml(bfile)}</div>
                <div class="meta">${escapeHtml(bsize)} · sha256 for delivery integrity</div>
              </div>
              <div style="display:flex; gap: 8px; align-items:center; justify-content:flex-end; flex-wrap:wrap">
                ${bsha ? `<span class="mono" title="${escapeAttr(bsha)}">${escapeHtml(bsha)}</span>` : '<span style="color: rgba(255,255,255,0.55)">—</span>'}
                ${bsha ? `<button class="copyBtn" data-act="copy-sha" data-sha="${escapeAttr(bsha)}">Copy</button>` : ''}
                ${bdl ? `<a class="copyBtn" style="text-decoration:none" href="${escapeAttr(bdl)}" target="_blank" rel="noreferrer">Download</a>` : ''}
              </div>
            </div>
            <div class="hr"></div>
            <div style="font-size: 13px; color: rgba(255,255,255,0.70); margin-bottom: 10px">Files included (verify with checksums.json)</div>
            <div class="fileList">${fileRows || '<div style="color: rgba(255,255,255,0.55)">No files listed.</div>'}</div>
            <div class="hr"></div>
            <details>
              <summary style="cursor:pointer; color: rgba(255,255,255,0.70); font-size: 13px">Manifest preview</summary>
              <pre class="mono" style="white-space: pre-wrap; margin-top: 10px; color: rgba(255,255,255,0.75)">${escapeHtml(JSON.stringify({ task_ref: taskRef, action_id: actionId, generated_at: genAt }, null, 2))}</pre>
            </details>
          </div>
        `;
      };

      const body = (function () {
        if (state.modal.tab === 'timeline') return renderTimeline();
        if (state.modal.tab === 'evidence') return renderEvidence();
        return renderSummary();
      })();

      return `
        <div class="modal open" data-act="modal-bg">
          <div class="dialog" role="dialog" aria-modal="true">
            <div class="dh">
              <strong>Replay</strong>
              <div class="close" data-act="modal-close">Close</div>
            </div>
            <div class="db">
              ${state.modal.status ? `<div class="statusLine">${escapeHtml(state.modal.status)}</div>` : ''}
              ${state.modal.copyFallbackText ? `<textarea class="mono" style="width:100%; height: 140px; margin: 10px 0; padding: 10px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.10); background: rgba(0,0,0,0.25); color: rgba(255,255,255,0.86)">${escapeHtml(state.modal.copyFallbackText)}</textarea>` : ''}
              ${rp ? header : `<div style="color: rgba(255,255,255,0.55)">No replay available yet.</div>`}
            </div>
            ${rp ? tabs : ''}
            ${rp ? `<div class="db">${body}</div>` : ''}
          </div>
        </div>
      `;
    }

    return '';
  }

  function render() {
    const route = state.route;
    const nav = (href, label, badge) => `
      <a href="#${href}" class="${route === href ? 'active' : ''}">
        <span>${escapeHtml(label)}</span>
        ${badge ? `<span class="badge">${escapeHtml(badge)}</span>` : ''}
      </a>`;

    const main = (function () {
      if (route === '/home') return renderHome();
      if (route === '/chat') return renderEmbed('Chat', '/chat');
      if (route === '/work') return renderEmbed('Work', '/chat/work');
      if (route === '/coding') return renderEmbed('Coding', '/coding');
      if (route === '/projects') return renderEmbed('Projects', '/projects');
      if (route === '/aws') return renderEmbed('AWS Ops', '/aws');
      if (route === '/tasks') return renderTasks();
      if (route === '/knowledge') return renderPlaceholder('Knowledge', 'Search your own KB and see which tasks used it.');
      if (route === '/activity') return renderPlaceholder('Activity', 'Timeline view with filters (risk tier / app / skill).');
      return renderHome();
    })();

    app.innerHTML = `
      <div class="shell">
        <div class="nav">
          <div class="brand">
            <div class="logo"></div>
            <div>
              <h1>OctopusOS</h1>
              <div class="sub">Product Shell · Console stays separate</div>
            </div>
          </div>
          ${nav('/home', 'Home')}
          ${nav('/chat', 'Chat')}
          ${nav('/work', 'Work')}
          ${nav('/coding', 'Coding')}
          <div class="sep"></div>
          ${nav('/projects', 'Projects')}
          ${nav('/aws', 'AWS Ops')}
          ${nav('/tasks', 'Tasks')}
          ${nav('/knowledge', 'Knowledge', 'v1')}
          ${nav('/activity', 'Activity', 'v1')}
          <div class="foot">No providers. No policies. No task ids.</div>
        </div>
        <div class="main">${main}</div>
      </div>
      ${renderModal()}
    `;

    // One click handler to keep DOM simple.
    app.querySelectorAll('[data-act]').forEach((el) => {
      el.addEventListener('click', async (ev) => {
        ev.preventDefault();
        const act = el.getAttribute('data-act');
        const id = el.getAttribute('data-id') || '';
        const sha = el.getAttribute('data-sha') || '';
        if (act === 'console') return openConsole();
        if (act === 'hero-analyze') return openModal('analyze', {});
        if (act === 'hero-soon') return openConsole();
        if (act === 'modal-close') return closeModal();
        if (act === 'modal-bg' && ev.target === el) return closeModal();
        if (act === 'pick-repo') return chooseRepo();
        if (act === 'run-analyze') return runAnalyze();
        if (act === 'plan') return openModal('plan', { taskId: id });
        if (act === 'evidence') return openModal('evidence', { taskId: id });
        if (act === 'replay') return openModal('replay', { taskId: id });
        if (act === 'replay-tab-summary') { state.modal.tab = 'summary'; return render(); }
        if (act === 'replay-tab-timeline') { state.modal.tab = 'timeline'; return render(); }
        if (act === 'replay-tab-evidence') { state.modal.tab = 'evidence'; return render(); }
        if (act === 'share') {
          const txt = (state.modal.data && state.modal.data.copy_text) || '';
          const ok = await copyText(txt);
          state.modal.copyFallbackText = ok ? '' : txt;
          state.modal.status = ok ? 'Copied to clipboard.' : 'Copy failed. You can manually copy the text below.';
          return render();
        }
        if (act === 'copy-sha') {
          const ok = await copyText(sha);
          state.modal.status = ok ? 'SHA256 copied.' : 'Copy failed.';
          return render();
        }
      });
    });
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
  function escapeAttr(s) { return escapeHtml(s).replace(/`/g, '&#096;'); }

  function buildSavingsTooltip() {
    const w = state.savingsWindow;
    const conf = state.savingsConfidence || {};
    const lines = [];
    if (w && w.start && w.end) lines.push(`Window: ${w.start}..${w.end} (${w.tz || 'UTC'})`);
    lines.push(`Confidence: tokens=${conf.tokens || 'none'} cost=${conf.cost || 'none'} time=${conf.time || 'none'}`);
    const notes = state.savingsNotes || [];
    if (notes.length) {
      lines.push('Notes:');
      for (const n of notes) lines.push(`- ${n}`);
    } else {
      lines.push('Notes: (none)');
    }
    return lines.join('\n');
  }

  function onRouteChange() {
    state.route = (location.hash || '#/home').replace('#', '');
    render();
    // Only pull product endpoints when the user is explicitly on the Tasks tab.
    // This avoids background 4xx/5xx noise on navigation smoke tests for other tabs.
    if (state.route === '/tasks') void refreshTasks();
  }

  window.addEventListener('hashchange', onRouteChange);

  // First paint: optimistic UI (no background calls until explicitly needed).
  onRouteChange();
})();
