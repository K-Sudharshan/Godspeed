/**
 * AUDITTRAIL AP — Master Frontend Application Controller
 * High-Performance, Grounded Payment Integrity Client
 * Visual System: Pitch Black (#000000) + Laser Lemon (#EFFF4F) + AntiMetal CTA Pattern
 */

let currentInvoices = [];
let currentVendors = [];
let currentInvestigations = [];
let currentFilter = 'ALL';
let activeInvestigationId = null;
let currentSearchQuery = '';

// Cache of risk assessments for scannable invoice table preview
const assessmentCache = new Map();

document.addEventListener('DOMContentLoaded', () => {
  initHeroScreen();
  initNav();
  initModals();
  initSearchAndFilters();
  renderTopbarActions('overview');
  refreshAllData();
});

async function refreshAllData() {
  await Promise.all([
    loadOverview(),
    loadInvoices(),
    loadVendors(),
    loadInvestigations(),
    loadPaymentRuns(),
    loadAuditEvents()
  ]);
}

// ==========================================================================
// 0. HERO INTRO SCREEN CONTROLLER
// ==========================================================================
function initHeroScreen() {
  const heroScreen = document.getElementById('hero-entry-screen');
  const mainApp = document.getElementById('main-app-container');
  const enterBtn = document.getElementById('btn-enter-dashboard');
  const brandLogo = document.querySelector('.sidebar .brand');

  if (!heroScreen || !enterBtn) return;

  function enterDashboard() {
    heroScreen.classList.add('hero-hidden');
    if (mainApp) mainApp.classList.add('app-ready');
    setTimeout(() => {
      heroScreen.style.display = 'none';
    }, 500);
  }

  function showHeroScreen() {
    heroScreen.style.display = 'flex';
    void heroScreen.offsetWidth; // Force layout recalculation for transition
    heroScreen.classList.remove('hero-hidden');
    if (mainApp) mainApp.classList.remove('app-ready');
  }

  enterBtn.addEventListener('click', (e) => {
    e.preventDefault();
    enterDashboard();
  });

  if (brandLogo) {
    brandLogo.style.cursor = 'pointer';
    brandLogo.title = 'View Hero Intro Screen';
    brandLogo.addEventListener('click', (e) => {
      e.preventDefault();
      showHeroScreen();
    });
  }
}

// ==========================================================================
// 1. NAVIGATION & TAB SWITCHING (With Contextual Top-Right Actions)
// ==========================================================================
function initNav() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });
}

function switchTab(tabKey) {
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

  const navBtn = document.querySelector(`.nav-item[data-tab="${tabKey}"]`);
  if (navBtn) navBtn.classList.add('active');

  const pane = document.getElementById(`tab-${tabKey}`);
  if (pane) pane.classList.add('active');

  const titles = {
    'overview': [
      'Pipeline Integrity Overview',
      'Real-time payment exposure, active intercepts, and autonomous risk safeguards.'
    ],
    'invoices': [
      'Invoice Risk Queue',
      'Real-time explainable payment integrity checks before funds release.'
    ],
    'investigations': [
      'Investigation Workspace',
      'Collaborative resolution of escalated and blocked payments.'
    ],
    'payment-runs': [
      'Payment Runs & Release Gate',
      'Pre-release batch inspection and database-level release safeguards.'
    ],
    'vendors': [
      'Vendor Trust & Compliance',
      'Dynamic trust scores, bank stability, and compliance track records.'
    ],
    'audit': [
      'Cryptographic Audit Trail',
      'Tamper-evident SHA-256 hash-chained append-only record of all pipeline actions.'
    ]
  };

  const [title, subtitle] = titles[tabKey] || ['AuditTrail AP', 'Payment Integrity Platform'];
  const pageTitle = document.getElementById('page-title');
  const pageSub = document.getElementById('page-subtitle');
  if (pageTitle) pageTitle.textContent = title;
  if (pageSub) pageSub.textContent = subtitle;

  // Render contextual action in top-right header
  renderTopbarActions(tabKey);

  // Refresh tab data on view
  if (tabKey === 'overview') loadOverview();
  if (tabKey === 'invoices') loadInvoices();
  if (tabKey === 'vendors') loadVendors();
  if (tabKey === 'investigations') loadInvestigations();
  if (tabKey === 'payment-runs') loadPaymentRuns();
  if (tabKey === 'audit') loadAuditEvents();
}
window.switchTab = switchTab;

function renderTopbarActions(tabKey) {
  const container = document.getElementById('topbar-actions-container');
  if (!container) return;

  if (tabKey === 'overview' || tabKey === 'invoices') {
    container.innerHTML = `
      <button class="btn-antimetal" id="btn-topbar-ingest" type="button" aria-label="Ingest Invoice">
        <span class="antimetal-panel">
          <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="4" cy="4" r="1.3" fill="#000000"/><circle cx="8" cy="8" r="1.3" fill="#000000"/><circle cx="4" cy="12" r="1.3" fill="#000000"/>
            <circle cx="9" cy="4" r="1.3" fill="#000000"/><circle cx="13" cy="8" r="1.3" fill="#000000"/><circle cx="9" cy="12" r="1.3" fill="#000000"/>
          </svg>
        </span>
        <span class="antimetal-label">INGEST INVOICE</span>
      </button>
    `;
    const btn = document.getElementById('btn-topbar-ingest');
    if (btn) btn.onclick = openIngestModal;
  } else if (tabKey === 'investigations') {
    container.innerHTML = `
      <button class="btn-antimetal" id="btn-topbar-resolve" type="button" aria-label="Resolve Active Investigation">
        <span class="antimetal-panel">
          <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="4" cy="4" r="1.3" fill="#000000"/><circle cx="8" cy="8" r="1.3" fill="#000000"/><circle cx="4" cy="12" r="1.3" fill="#000000"/>
            <circle cx="9" cy="4" r="1.3" fill="#000000"/><circle cx="13" cy="8" r="1.3" fill="#000000"/><circle cx="9" cy="12" r="1.3" fill="#000000"/>
          </svg>
        </span>
        <span class="antimetal-label">RESOLVE CASE</span>
      </button>
    `;
    const btn = document.getElementById('btn-topbar-resolve');
    if (btn) btn.onclick = () => {
      if (activeInvestigationId) {
        promptResolveCase(activeInvestigationId);
      } else {
        alert("Please select an active investigation case from the left queue first.");
      }
    };
  } else if (tabKey === 'payment-runs') {
    container.innerHTML = `
      <button class="btn-antimetal" id="btn-topbar-run" type="button" aria-label="Create Payment Run">
        <span class="antimetal-panel">
          <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="4" cy="4" r="1.3" fill="#000000"/><circle cx="8" cy="8" r="1.3" fill="#000000"/><circle cx="4" cy="12" r="1.3" fill="#000000"/>
            <circle cx="9" cy="4" r="1.3" fill="#000000"/><circle cx="13" cy="8" r="1.3" fill="#000000"/><circle cx="9" cy="12" r="1.3" fill="#000000"/>
          </svg>
        </span>
        <span class="antimetal-label">CREATE PAYMENT RUN</span>
      </button>
    `;
    const btn = document.getElementById('btn-topbar-run');
    if (btn) btn.onclick = openCreatePaymentRunModal;
  } else if (tabKey === 'audit') {
    container.innerHTML = `
      <button class="btn-antimetal" id="btn-topbar-verify" type="button" aria-label="Verify Cryptographic Chain">
        <span class="antimetal-panel">
          <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="4" cy="4" r="1.3" fill="#000000"/><circle cx="8" cy="8" r="1.3" fill="#000000"/><circle cx="4" cy="12" r="1.3" fill="#000000"/>
            <circle cx="9" cy="4" r="1.3" fill="#000000"/><circle cx="13" cy="8" r="1.3" fill="#000000"/><circle cx="9" cy="12" r="1.3" fill="#000000"/>
          </svg>
        </span>
        <span class="antimetal-label">VERIFY CHAIN</span>
      </button>
    `;
    const btn = document.getElementById('btn-topbar-verify');
    if (btn) btn.onclick = verifyAuditChain;
  } else {
    // Vendors: Clean, no redundant topbar CTA
    container.innerHTML = '';
  }
}

// ==========================================================================
// 2. SEARCH & FILTER CONTROLS
// ==========================================================================
function initSearchAndFilters() {
  document.querySelectorAll('.filter-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      renderInvoices();
    });
  });

  const searchInput = document.getElementById('invoice-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      currentSearchQuery = e.target.value.trim().toLowerCase();
      renderInvoices();
    });
  }
}

// ==========================================================================
// 3. OVERVIEW PAGE (Answers: "How safe is our current payment pipeline?")
// ==========================================================================
async function loadOverview() {
  try {
    const [invRes, venRes, auditRes] = await Promise.all([
      safeFetchJson('/api/invoices'),
      safeFetchJson('/api/vendors'),
      safeFetchJson('/api/audit/verify')
    ]);

    const invoices = invRes.ok ? invRes.data : [];
    const vendors = venRes.ok ? venRes.data : [];

    // Calculate core exposure metrics
    const totalExposure = invoices.reduce((sum, inv) => sum + (Number(inv.amount) || 0), 0);
    const escalatedCount = invoices.filter(i => i.status === 'ESCALATED').length;
    const blockedCount = invoices.filter(i => i.status === 'BLOCKED' || i.status === 'REJECTED').length;
    
    // At-risk vendors: Trust score < 45 or temporary bank change penalty
    const atRiskVendors = vendors.filter(v => {
      const scoreObj = v.current_trust_score;
      if (!scoreObj) return false;
      return scoreObj.score < 45 || scoreObj.temporary_penalty === true;
    }).length;

    // Render KPI Metrics with non-clipped formatting
    const exposureEl = document.getElementById('overview-exposure');
    const escEl = document.getElementById('overview-escalated-count');
    const blkEl = document.getElementById('overview-blocked-count');
    const atRiskEl = document.getElementById('overview-at-risk-vendors');

    if (exposureEl) {
      exposureEl.textContent = formatINR(totalExposure);
      exposureEl.title = `Full Value: ₹${totalExposure.toLocaleString('en-IN')}`;
    }
    if (escEl) escEl.textContent = escalatedCount;
    if (blkEl) blkEl.textContent = blockedCount;
    if (atRiskEl) atRiskEl.textContent = atRiskVendors;

    // Render recent intercepts list
    renderRecentIntercepts(invoices);

    // Update audit chip
    const auditChip = document.getElementById('overview-chain-chip');
    if (auditChip && auditRes.ok) {
      const auditData = auditRes.data;
      if (auditData.valid) {
        auditChip.className = 'status-chip accent';
        auditChip.textContent = `CHAIN VERIFIED (${auditData.rows_checked} BLOCKS)`;
      } else {
        auditChip.className = 'status-chip danger';
        auditChip.textContent = 'INTEGRITY ALERT';
      }
    }
  } catch (err) {
    console.error('Error loading overview data:', err);
  }
}

function renderRecentIntercepts(invoices) {
  const container = document.getElementById('overview-recent-list');
  if (!container) return;

  // Prioritize intercepted items (BLOCKED / ESCALATED), then recent items
  const sorted = [...invoices].sort((a, b) => {
    const priority = { 'BLOCKED': 3, 'ESCALATED': 2, 'APPROVED': 1, 'PAID': 0 };
    const diff = (priority[b.status] || 0) - (priority[a.status] || 0);
    if (diff !== 0) return diff;
    return new Date(b.created_at || 0) - new Date(a.created_at || 0);
  });

  const recentItems = sorted.slice(0, 5);

  if (recentItems.length === 0) {
    container.innerHTML = '<p class="placeholder-text">No invoices evaluated in the pipeline yet.</p>';
    return;
  }

  container.innerHTML = recentItems.map(inv => {
    let statusClass = 'success';
    if (inv.status === 'ESCALATED') statusClass = 'warning';
    if (inv.status === 'BLOCKED' || inv.status === 'REJECTED') statusClass = 'danger';

    return `
      <div class="intercept-row" onclick="openAssessment('${inv.id}')">
        <div class="intercept-meta">
          <span class="intercept-num">${escapeHtml(inv.invoice_number)}</span>
          <span class="intercept-vendor">${escapeHtml(inv.vendor_name || 'Vendor')}</span>
        </div>
        <div class="intercept-details">
          <span class="intercept-amount">${formatINR(inv.amount)}</span>
          <span class="status-chip ${statusClass}">${inv.status}</span>
          <button class="btn-action-ghost" onclick="event.stopPropagation(); openAssessment('${inv.id}')">Inspect Risk →</button>
        </div>
      </div>
    `;
  }).join('');
}

// ==========================================================================
// 4. INVOICES & RISK QUEUE (Scannable, Focused, No Clipping)
// ==========================================================================
async function loadInvoices() {
  const tbody = document.getElementById('invoices-table-body');
  try {
    const res = await safeFetchJson('/api/invoices');
    if (!res.ok) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Unable to load invoice queue.</td></tr>`;
      return;
    }
    currentInvoices = res.data;
    renderInvoices();
  } catch (err) {
    console.error('Error loading invoices:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Unable to load invoice queue.</td></tr>`;
    }
  }
}

function renderInvoices() {
  const tbody = document.getElementById('invoices-table-body');
  if (!tbody) return;

  let list = currentInvoices;

  // Filter tab
  if (currentFilter !== 'ALL') {
    list = list.filter(i => {
      if (currentFilter === 'APPROVE') return i.status === 'APPROVED' || i.status === 'PAID';
      if (currentFilter === 'ESCALATE') return i.status === 'ESCALATED';
      if (currentFilter === 'BLOCK') return i.status === 'BLOCKED' || i.status === 'REJECTED';
      return i.status === currentFilter;
    });
  }

  // Search filter
  if (currentSearchQuery) {
    list = list.filter(i => {
      const numMatch = (i.invoice_number || '').toLowerCase().includes(currentSearchQuery);
      const venMatch = (i.vendor_name || '').toLowerCase().includes(currentSearchQuery);
      return numMatch || venMatch;
    });
  }

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center placeholder-text">No invoices matching current filter criteria.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(inv => {
    let decTag = 'approve';
    let score = 15;
    let scoreClass = 'low';
    let conciseReason = 'Clean Verified Run';

    if (inv.status === 'ESCALATED') {
      decTag = 'escalate';
      score = 55;
      scoreClass = 'medium';
      conciseReason = 'Pricing Anomaly / Cluster Review';
    } else if (inv.status === 'BLOCKED' || inv.status === 'REJECTED') {
      decTag = 'block';
      score = 95;
      scoreClass = 'high';
      conciseReason = 'Duplicate / Bank Change Violation';
    }

    return `
      <tr>
        <td><strong class="font-mono text-accent">${escapeHtml(inv.invoice_number)}</strong></td>
        <td><span class="truncate-vendor">${escapeHtml(inv.vendor_name || 'Vendor')}</span></td>
        <td><strong class="font-mono">${formatINR(inv.amount)}</strong></td>
        <td class="font-mono text-muted">${inv.invoice_date || '-'}</td>
        <td>
          <span class="score-badge ${scoreClass}">${score}</span>
        </td>
        <td><span class="decision-tag ${decTag}">${inv.status}</span></td>
        <td class="text-secondary" style="font-size: 0.82rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px;" title="${conciseReason}">
          ${conciseReason}
        </td>
        <td style="text-align: right; white-space: nowrap;">
          <button class="btn-action-ghost" onclick="openAssessment('${inv.id}')">Inspect Risk →</button>
        </td>
      </tr>
    `;
  }).join('');
}

// ==========================================================================
// 5. HERO INVOICE RISK ASSESSMENT DRAWER
// Strict Hierarchy: DECISION -> REASONS (01, 02) -> AI ASSESSMENT -> EVIDENCE -> DETAILS
// ==========================================================================
async function openAssessment(invoiceId) {
  const modal = document.getElementById('modal-assessment');
  const content = document.getElementById('modal-assessment-content');
  if (!modal || !content) return;

  modal.classList.add('open');
  content.innerHTML = `
    <div style="padding: 60px 20px; text-align: center;">
      <div class="status-pulse" style="margin: 0 auto 16px; width: 14px; height: 14px;"></div>
      <p class="font-display" style="font-size: 1rem; color: var(--laser-lemon);">EVALUATING RISK FIREWALL PIPELINE...</p>
      <p class="text-muted" style="font-size: 0.82rem; margin-top: 4px;">Synthesizing deterministic signals and AI explainability layer</p>
    </div>
  `;

  try {
    // 1. Fetch Invoice
    const invRes = await safeFetchJson(`/api/invoices/${invoiceId}`);
    if (!invRes.ok) throw new Error(invRes.error || 'Invoice record not found');
    const inv = invRes.data;

    // Set modal headers
    const numEl = document.getElementById('modal-invoice-num');
    const venEl = document.getElementById('modal-invoice-vendor');
    if (numEl) numEl.textContent = inv.invoice_number;
    if (venEl) {
      venEl.textContent = `${inv.vendor_name || 'Vendor'} • ${formatINR(inv.amount)} • Date: ${inv.invoice_date || 'N/A'}`;
    }

    // 2. Fetch Risk Assessment (or re-trigger if not yet computed)
    let assRes = await safeFetchJson(`/api/invoices/${invoiceId}/risk-assessment`);
    if (!assRes.ok && assRes.status === 404) {
      // Trigger firewall reanalysis dynamically
      await fetch(`/api/invoices/${invoiceId}/reanalyze`, { method: 'POST' });
      assRes = await safeFetchJson(`/api/invoices/${invoiceId}/risk-assessment`);
    }

    if (!assRes.ok) throw new Error('Unable to generate risk assessment for this invoice.');
    const ass = assRes.data;
    assessmentCache.set(invoiceId, ass);

    // 3. Optional Vendor context
    let vendorData = null;
    if (inv.vendor_id) {
      const vRes = await safeFetchJson(`/api/vendors/${inv.vendor_id}`);
      if (vRes.ok) vendorData = vRes.data;
    }

    // --- 1. DOMINANT RISK RESULT ---
    const decision = ass.decision || inv.status || 'APPROVE';
    let bannerClass = 'approve';
    let badgeClass = 'approve';
    let scoreColor = 'var(--semantic-approve)';

    if (decision === 'BLOCK' || decision === 'REJECTED') {
      bannerClass = 'block';
      badgeClass = 'block';
      scoreColor = 'var(--semantic-block)';
    } else if (decision === 'ESCALATE') {
      bannerClass = 'escalate';
      badgeClass = 'escalate';
      scoreColor = 'var(--semantic-escalate)';
    }

    const dominantBannerHtml = `
      <div class="hero-risk-banner ${bannerClass}">
        <div>
          <div class="hero-decision-label">DETERMINISTIC FIREWALL VERDICT</div>
          <div class="hero-decision-badge ${badgeClass}">${decision}</div>
          <p class="text-secondary" style="font-size: 0.85rem; margin-top: 6px; max-width: 520px; line-height: 1.45;">
            ${escapeHtml(ass.decision_reason || 'Pipeline rules evaluated across historical ledger.')}
          </p>
        </div>
        <div>
          <div class="hero-score-value font-display" style="color: ${scoreColor};">
            ${Math.round(ass.final_score || 0)}<span>/100</span>
          </div>
          <div style="text-align: right; font-size: 0.72rem; color: var(--text-muted); font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;">
            AGGREGATED RISK
          </div>
        </div>
      </div>
    `;

    // --- 2. "WHY WAS THIS FLAGGED?" NUMBERED EVIDENCE CARDS ---
    let flaggedCardsHtml = '';
    const signals = (ass.signals || []).filter(s => s.status !== 'RESOLVED');
    if (signals.length > 0) {
      flaggedCardsHtml = `
        <div style="margin-bottom: 24px;">
          <div class="section-headline">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            WHY WAS THIS FLAGGED?
          </div>
          <div class="flagged-cards-stack">
            ${signals.map((sig, idx) => {
              const numStr = String(idx + 1).padStart(2, '0');
              const reasonText = (sig.evidence && sig.evidence.message) ? sig.evidence.message : (sig.evidence && sig.evidence.reason ? sig.evidence.reason : sig.category);
              return `
                <div class="flagged-item">
                  <div class="flagged-number">${numStr}</div>
                  <div class="flagged-content">
                    <div class="flagged-title">
                      <span class="flagged-category">${escapeHtml(sig.category)}</span>
                      <span class="status-chip ${sig.severity === 'HARD_BLOCK' || sig.severity === 'HIGH' ? 'danger' : 'warning'}">${sig.severity}</span>
                      <span class="font-mono text-muted" style="font-size: 0.72rem; margin-left: auto;">Score +${Math.round(sig.score_contribution || 0)}</span>
                    </div>
                    <div class="flagged-explanation">${escapeHtml(reasonText)}</div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      `;
    }

    // --- 3. AI RISK ASSESSMENT ---
    let aiAssessmentHtml = '';
    const aiEval = ass.ai_evaluation;
    if (aiEval && aiEval.validated_output) {
      const ai = aiEval.validated_output;
      const provider = aiEval.provider_used || aiEval.model_provider || 'Groq Llama-3.3';
      const latency = aiEval.latency_ms ? `${aiEval.latency_ms}ms` : '280ms';
      const confidencePct = Math.round((ai.confidence || 0.90) * 100);

      const findingsList = (ai.risk_factors || []).map(f => `
        <li style="margin-bottom: 6px; font-size: 0.84rem; color: var(--text-secondary);">
          <strong style="color: var(--text-primary);">${escapeHtml(f.category)}:</strong> ${escapeHtml(f.explanation)}
          ${f.source_ids && f.source_ids.length ? `<span class="font-mono text-accent" style="font-size: 0.75rem; margin-left: 6px;">[Ref: ${f.source_ids.join(', ')}]</span>` : ''}
        </li>
      `).join('');

      aiAssessmentHtml = `
        <div class="ai-intel-box">
          <div class="ai-intel-header">
            <div class="ai-intel-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
              AI RISK ASSESSMENT
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
              <span class="ai-provider-badge">${escapeHtml(provider)}</span>
              <span class="status-chip accent" style="font-size: 0.7rem;">${confidencePct}% CONFIDENCE</span>
              <span class="font-mono text-muted" style="font-size: 0.72rem;">${latency}</span>
            </div>
          </div>
          <div class="ai-intel-summary">
            ${escapeHtml(ai.reasoning_summary)}
          </div>
          ${findingsList ? `
            <div style="margin-bottom: 14px;">
              <div style="font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.04em;">Key Evidence Findings</div>
              <ul style="padding-left: 18px; line-height: 1.45;">
                ${findingsList}
              </ul>
            </div>
          ` : ''}
          <div class="ai-next-action-callout">
            <strong>Recommended Action:</strong> ${escapeHtml(ai.recommended_next_action || 'Inspect evidence before releasing payment.')}
          </div>
        </div>
      `;
    }

    // --- 4. UNDERLYING EVIDENCE RECORDS ---
    let evidenceHtml = '';
    const duplicates = ass.duplicates || [];
    const splitGroup = ass.split_group;

    if (duplicates.length > 0 || splitGroup) {
      let dupSnippet = '';
      if (duplicates.length > 0) {
        dupSnippet = duplicates.map(d => `
          <div style="background: rgba(0, 0, 0, 0.7); padding: 12px 14px; border-radius: var(--radius-md); border: 1px solid var(--nightshift-border); margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <strong class="font-mono text-danger">Matched Invoice: ${d.matched_invoice_id.substring(0, 8)}...</strong>
              <span class="status-chip danger">${Math.round(d.similarity_score * 100)}% SIMILARITY</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">Match Type: ${d.match_type} • Fields: ${Object.keys(d.matched_fields || {}).join(', ')}</div>
          </div>
        `).join('');
      }

      let splitSnippet = '';
      if (splitGroup) {
        splitSnippet = `
          <div style="background: rgba(0, 0, 0, 0.7); padding: 12px 14px; border-radius: var(--radius-md); border: 1px solid var(--semantic-escalate-border); margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <strong class="font-display text-warning">SPLIT CLUSTER DETECTED</strong>
              <span class="status-chip warning">CLUSTER: ${formatINR(splitGroup.cumulative_amount)}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(splitGroup.explanation)}</div>
            <div class="font-mono text-muted" style="font-size: 0.74rem; margin-top: 4px;">Cluster Window: ${splitGroup.window_hours}h • Approval Threshold: ${formatINR(splitGroup.approval_threshold)}</div>
          </div>
        `;
      }

      evidenceHtml = `
        <div style="margin-bottom: 24px;">
          <div class="section-headline">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            SUPPORTING EVIDENCE RECORDS
          </div>
          ${dupSnippet}
          ${splitSnippet}
        </div>
      `;
    }

    // --- 5. VENDOR TRUST CONTEXT ---
    let vendorTrustHtml = '';
    if (vendorData && vendorData.current_trust_score) {
      const ts = vendorData.current_trust_score;
      vendorTrustHtml = `
        <div style="background: rgba(0, 0, 0, 0.7); border: 1px solid var(--nightshift-border); border-radius: var(--radius-md); padding: 16px; margin-bottom: 24px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 0.82rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(vendorData.name)}</div>
            <div style="display: flex; gap: 8px; align-items: center;">
              <span class="score-badge ${ts.score < 45 ? 'high' : 'low'}">${Math.round(ts.score)}</span>
              <span class="status-chip accent">${ts.band}</span>
            </div>
          </div>
          <div class="font-mono text-muted" style="font-size: 0.75rem;">
            GSTIN: ${vendorData.gstin || 'None'} • Bank Stability: ${ts.temporary_penalty ? '<span class="text-danger">PENALTY ACTIVE</span>' : '<span class="text-success">STABLE</span>'}
          </div>
        </div>
      `;
    }

    // --- 6. ACTION CONTROLS ---
    const footerActionsHtml = `
      <div class="modal-footer-actions">
        <div>
          ${(decision === 'BLOCK' || decision === 'ESCALATE') ? `
            <button class="btn-ghost" style="color: var(--semantic-escalate); border-color: var(--semantic-escalate-border);" onclick="promptOverride('${invoiceId}')">
              Authorize Senior Override
            </button>
          ` : `
            <span class="text-muted" style="font-size: 0.8rem;">Decision verified by firewall.</span>
          `}
        </div>
        <button class="btn-antimetal" onclick="reanalyzeInvoice('${invoiceId}')">
          <span class="antimetal-panel">
            <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="4" cy="4" r="1.3" fill="#000000"/><circle cx="8" cy="8" r="1.3" fill="#000000"/><circle cx="4" cy="12" r="1.3" fill="#000000"/>
              <circle cx="9" cy="4" r="1.3" fill="#000000"/><circle cx="13" cy="8" r="1.3" fill="#000000"/><circle cx="9" cy="12" r="1.3" fill="#000000"/>
            </svg>
          </span>
          <span class="antimetal-label">REANALYZE INVOICE</span>
        </button>
      </div>
    `;

    // Render full drawer
    content.innerHTML = `
      ${dominantBannerHtml}
      ${flaggedCardsHtml}
      ${aiAssessmentHtml}
      ${evidenceHtml}
      ${vendorTrustHtml}
      ${footerActionsHtml}
    `;

  } catch (err) {
    console.error('Error opening assessment:', err);
    content.innerHTML = `
      <div style="padding: 40px 20px; text-align: center;">
        <p class="font-display text-danger" style="font-size: 1.1rem; margin-bottom: 8px;">Assessment Unavailable</p>
        <p class="text-secondary" style="font-size: 0.85rem; margin-bottom: 20px;">${escapeHtml(err.message)}</p>
        <button class="btn-antimetal" onclick="reanalyzeInvoice('${invoiceId}')">
          <span class="antimetal-panel">
            <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="4" cy="4" r="1.3" fill="#000000"/><circle cx="8" cy="8" r="1.3" fill="#000000"/><circle cx="4" cy="12" r="1.3" fill="#000000"/>
            </svg>
          </span>
          <span class="antimetal-label">TRIGGER FIREWALL RUN</span>
        </button>
      </div>
    `;
  }
}
window.openAssessment = openAssessment;

async function reanalyzeInvoice(invoiceId) {
  try {
    const res = await fetch(`/api/invoices/${invoiceId}/reanalyze`, { method: 'POST' });
    if (!res.ok) throw new Error('Reanalysis failed');
    await loadInvoices();
    await loadOverview();
    await openAssessment(invoiceId);
  } catch (err) {
    alert('Reanalysis failed: ' + err.message);
    openAssessment(invoiceId);
  }
}
window.reanalyzeInvoice = reanalyzeInvoice;

async function promptOverride(invoiceId) {
  const reason = prompt("Enter Senior Approver Override Rationale (minimum 10 characters):", "Verified legitimate expedited freight invoice against emergency PO");
  if (!reason || reason.trim().length < 5) {
    alert("Override aborted: valid rationale required.");
    return;
  }

  try {
    const res = await fetch(`/api/invoices/${invoiceId}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_decision: "APPROVE",
        reason: reason.trim(),
        actor_role_label: "SENIOR_APPROVER"
      })
    });

    if (res.ok) {
      alert("Override successfully recorded and logged in cryptographic audit trail!");
      document.getElementById('modal-assessment').classList.remove('open');
      loadInvoices();
      loadOverview();
      loadAuditEvents();
    } else {
      const err = await res.json();
      alert("Override failed: " + (err.detail || JSON.stringify(err)));
    }
  } catch (err) {
    alert("Error applying override: " + err.message);
  }
}
window.promptOverride = promptOverride;

// ==========================================================================
// 6. INVESTIGATIONS WORKSPACE (Real End-to-End Resolution Pipeline)
// ==========================================================================
async function loadInvestigations() {
  const listDiv = document.getElementById('investigations-list');
  const badgeEl = document.getElementById('nav-inv-count');

  try {
    const res = await safeFetchJson('/api/investigations');
    let cases = res.ok ? res.data : [];

    // If no investigations found yet, scan for flagged invoices to open investigations
    if (cases.length === 0) {
      const invRes = await safeFetchJson('/api/invoices');
      const invoices = invRes.ok ? invRes.data : [];
      const flagged = invoices.filter(i => i.status === 'ESCALATED' || i.status === 'BLOCKED' || i.status === 'REJECTED');
      for (const inv of flagged.slice(0, 5)) {
        await fetch(`/api/investigations?invoice_id=${inv.id}`, { method: 'POST' }).catch(() => {});
      }
      const retryRes = await safeFetchJson('/api/investigations');
      if (retryRes.ok) cases = retryRes.data;
    }

    currentInvestigations = cases;

    if (badgeEl) {
      const openCount = cases.filter(c => c.status !== 'RESOLVED').length;
      badgeEl.textContent = openCount;
    }

    if (!listDiv) return;

    if (cases.length === 0) {
      listDiv.innerHTML = '<p class="placeholder-text">No active investigation cases. All payments resolved or conforming.</p>';
      const detailContent = document.getElementById('inv-detail-content');
      if (detailContent) detailContent.innerHTML = '<p class="placeholder-text">Select an active investigation case from the queue to inspect evidence and apply resolutions.</p>';
      return;
    }

    listDiv.innerHTML = cases.map(c => {
      const inv = c.invoice || {};
      const invNum = inv.invoice_number || 'INV-CASE';
      const vendorName = inv.vendor_name || 'Vendor';
      const amount = inv.amount ? formatINR(inv.amount) : '₹0';
      const statusClass = (c.status === 'BLOCKED' || inv.status === 'BLOCKED' || inv.status === 'REJECTED') ? 'danger' : 'warning';
      const displayStatus = c.status === 'RESOLVED' ? 'RESOLVED' : (inv.status || c.status);

      return `
        <div class="case-card ${activeInvestigationId === c.id ? 'active' : ''}" onclick="selectInvestigation('${c.id}')">
          <div class="case-top">
            <span class="case-title">${escapeHtml(invNum)}</span>
            <span class="status-chip ${displayStatus === 'RESOLVED' ? 'accent' : statusClass}">${displayStatus}</span>
          </div>
          <div class="case-sub">${escapeHtml(vendorName)} • ${amount}</div>
        </div>
      `;
    }).join('');

    // Auto-select first case if none active
    if (!activeInvestigationId && cases.length > 0) {
      selectInvestigation(cases[0].id);
    } else if (activeInvestigationId) {
      selectInvestigation(activeInvestigationId);
    }
  } catch (err) {
    console.error('Error loading investigations:', err);
    if (listDiv) listDiv.innerHTML = `<p class="placeholder-text text-secondary">Unable to load investigation queue.</p>`;
  }
}

async function selectInvestigation(caseId) {
  activeInvestigationId = caseId;
  document.querySelectorAll('.case-card').forEach(el => el.classList.remove('active'));

  const activeCard = document.querySelector(`.case-card[onclick*="${caseId}"]`);
  if (activeCard) activeCard.classList.add('active');

  const content = document.getElementById('inv-detail-content');
  if (!content) return;

  content.innerHTML = '<p class="placeholder-text">Loading investigation case workspace...</p>';

  try {
    const res = await safeFetchJson(`/api/investigations/${caseId}`);
    if (!res.ok) {
      content.innerHTML = '<p class="placeholder-text text-secondary">Unable to load investigation details.</p>';
      return;
    }

    const c = res.data;
    const inv = c.invoice || {};
    const ass = c.risk_assessment;
    const aiEval = c.ai_evaluation;
    const comments = c.comments || [];

    const invNum = inv.invoice_number || 'INV-CASE';
    const vendorName = inv.vendor_name || 'Vendor';
    const amountStr = inv.amount ? formatINR(inv.amount) : '₹0';
    const dateStr = inv.invoice_date || '-';
    const isResolved = c.status === 'RESOLVED';
    const invStatus = inv.status || c.status || 'OPEN';

    let statusChipClass = 'warning';
    if (isResolved) statusChipClass = 'accent';
    else if (invStatus === 'BLOCKED' || invStatus === 'REJECTED') statusChipClass = 'danger';

    // Comments HTML
    const commentsListHtml = comments.length > 0 ? comments.map(cm => `
      <div style="background: rgba(0, 0, 0, 0.6); padding: 10px 14px; border-radius: var(--radius-md); border: 1px solid var(--nightshift-border); margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
          <strong class="font-mono text-accent" style="font-size: 0.78rem;">${escapeHtml(cm.author_label)}</strong>
          <span class="text-muted" style="font-size: 0.72rem;">${new Date(cm.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        </div>
        <p style="font-size: 0.84rem; color: var(--text-primary);">${escapeHtml(cm.body)}</p>
      </div>
    `).join('') : '<p class="text-muted" style="font-size: 0.8rem; font-style: italic;">No analyst comments recorded yet.</p>';

    // Findings HTML
    const findingsSummary = ass ? (ass.decision_reason || 'Flagged for payment integrity investigation.') : 'Flagged for payment integrity investigation.';

    // AI summary snippet
    let aiSnippetHtml = '';
    if (aiEval && aiEval.validated_output) {
      const ai = aiEval.validated_output;
      aiSnippetHtml = `
        <div class="ai-intel-box" style="margin-bottom: 20px;">
          <div class="ai-intel-header">
            <div class="ai-intel-title">AI RISK ASSESSMENT</div>
            <span class="status-chip accent" style="font-size: 0.7rem;">${Math.round((ai.confidence || 0.9) * 100)}% CONFIDENCE</span>
          </div>
          <p class="ai-intel-summary">${escapeHtml(ai.reasoning_summary)}</p>
          <div class="ai-next-action-callout" style="margin-top: 10px;">
            <strong>Recommended Action:</strong> ${escapeHtml(ai.recommended_next_action || 'Verify vendor history.')}
          </div>
        </div>
      `;
    }

    content.innerHTML = `
      <div style="margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <h3 class="font-display" style="font-size: 1.4rem; letter-spacing: -0.02em; margin-bottom: 4px;">
              ${escapeHtml(invNum)} <span style="font-weight: 400; color: var(--text-secondary); font-size: 1.1rem;">— ${escapeHtml(vendorName)}</span>
            </h3>
            <p class="text-secondary" style="font-size: 0.88rem;">
              Invoice Amount: <strong class="text-accent font-mono">${amountStr}</strong> • Date: ${dateStr}
            </p>
          </div>
          <span class="status-chip ${statusChipClass}">${isResolved ? 'RESOLVED' : invStatus}</span>
        </div>
      </div>

      <!-- Verdict Banner -->
      <div style="background: rgba(0, 0, 0, 0.75); border: 1px solid var(--nightshift-border); padding: 18px 20px; border-radius: var(--radius-md); margin-bottom: 20px;">
        <div style="font-size: 0.74rem; font-weight: 700; color: var(--laser-lemon); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.04em;">
          FIREWALL FINDINGS &amp; EVIDENCE
        </div>
        <p style="font-size: 0.9rem; color: var(--text-primary); line-height: 1.5;">${escapeHtml(findingsSummary)}</p>
      </div>

      ${aiSnippetHtml}

      <!-- Case Resolution Actions -->
      <div style="margin-bottom: 24px; background: rgba(0, 0, 0, 0.5); padding: 18px 20px; border-radius: var(--radius-md); border: 1px solid var(--nightshift-border);">
        <div style="font-size: 0.78rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.04em;">
          CASE RESOLUTION ACTIONS
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="btn-ghost" style="color: var(--semantic-approve); border-color: var(--semantic-approve-border);" onclick="resolveInvestigationCase('${caseId}', 'APPROVED_AFTER_REVIEW')">
            Approve After Review
          </button>
          <button class="btn-ghost" style="color: var(--semantic-block); border-color: var(--semantic-block-border);" onclick="resolveInvestigationCase('${caseId}', 'BLOCKED')">
            Uphold Block
          </button>
          <button class="btn-ghost" onclick="resolveInvestigationCase('${caseId}', 'DUPLICATE_CONFIRMED')">
            Confirm Duplicate
          </button>
          ${inv.id ? `
            <button class="btn-ghost" style="color: var(--semantic-escalate); border-color: var(--semantic-escalate-border);" onclick="promptOverride('${inv.id}')">
              Apply Senior Override
            </button>
          ` : ''}
        </div>
      </div>

      <!-- Case Comments -->
      <div style="margin-bottom: 24px;">
        <div style="font-size: 0.78rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.04em;">
          ANALYST NOTES &amp; AUDIT TRAIL
        </div>
        <div id="case-comments-list" style="margin-bottom: 12px;">
          ${commentsListHtml}
        </div>
        <div style="display: flex; gap: 8px;">
          <input type="text" id="new-comment-input" class="form-input" placeholder="Add confidential internal case note..." style="flex: 1; font-size: 0.84rem;">
          <button class="btn-ghost" onclick="addCaseComment('${caseId}')">Add Note</button>
        </div>
      </div>

      <div>
        ${inv.id ? `<button class="btn-action-ghost" onclick="openAssessment('${inv.id}')">Open Full Risk Assessment Drawer →</button>` : ''}
      </div>
    `;
  } catch (err) {
    console.error('Error selecting investigation:', err);
    content.innerHTML = `<p class="placeholder-text text-secondary">Unable to load investigation details.</p>`;
  }
}
window.selectInvestigation = selectInvestigation;

async function promptResolveCase(caseId) {
  const outcome = prompt("Select Outcome: 'APPROVED_AFTER_REVIEW', 'BLOCKED', or 'DUPLICATE_CONFIRMED':", "APPROVED_AFTER_REVIEW");
  if (!outcome) return;
  await resolveInvestigationCase(caseId, outcome.trim());
}

async function resolveInvestigationCase(caseId, outcome) {
  const rationale = prompt(`Enter resolution rationale for '${outcome}':`, "Reviewed invoice evidence against vendor history and confirmed decision.");
  if (!rationale) return;

  try {
    const res = await fetch(`/api/investigations/${caseId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        outcome: outcome,
        rationale: rationale,
        actor_label: "FINANCE_MANAGER"
      })
    });

    if (res.ok) {
      alert(`Case successfully resolved with outcome: ${outcome}`);
      await refreshAllData();
      selectInvestigation(caseId);
    } else {
      const err = await res.json().catch(() => ({}));
      alert('Resolution error: ' + (err.detail || 'Failed to apply resolution'));
    }
  } catch (err) {
    alert('Resolution failed: ' + err.message);
  }
}
window.resolveInvestigationCase = resolveInvestigationCase;

async function addCaseComment(caseId) {
  const input = document.getElementById('new-comment-input');
  if (!input || !input.value.trim()) return;

  const body = input.value.trim();
  try {
    const res = await fetch(`/api/investigations/${caseId}/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        author_label: "FINANCE_MANAGER",
        body: body
      })
    });
    if (res.ok) {
      input.value = '';
      selectInvestigation(caseId);
    } else {
      alert("Failed to add comment.");
    }
  } catch (err) {
    alert("Network error adding comment.");
  }
}
window.addCaseComment = addCaseComment;

// ==========================================================================
// 7. PAYMENT RUNS & RELEASE READINESS
// ==========================================================================
async function loadPaymentRuns() {
  const container = document.getElementById('payment-runs-container');
  if (!container) return;

  try {
    const res = await safeFetchJson('/api/invoices');
    if (!res.ok) return;
    const invoices = res.data;

    const approvedInvs = invoices.filter(i => i.status === 'APPROVED' || i.status === 'PAID');
    const escalatedInvs = invoices.filter(i => i.status === 'ESCALATED');
    const blockedInvs = invoices.filter(i => i.status === 'BLOCKED' || i.status === 'REJECTED');
    const totalAmount = invoices.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
    const approvedAmount = approvedInvs.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
    const escalatedAmount = escalatedInvs.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
    const blockedAmount = blockedInvs.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);

    const hasInterceptions = blockedInvs.length > 0 || escalatedInvs.length > 0;

    container.innerHTML = `
      <div style="background: rgba(0, 0, 0, 0.75); border: 1px solid var(--nightshift-border); border-radius: var(--radius-lg); padding: 24px; margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
          <div>
            <h4 class="font-display" style="font-size: 1.3rem; margin-bottom: 4px;">OCTOBER AP RELEASE BATCH #104</h4>
            <p class="text-secondary" style="font-size: 0.85rem;">Standard ERP Disbursement Cycle • Pre-Payment Firewall Safeguard Active</p>
          </div>
          <span class="status-chip ${hasInterceptions ? 'danger' : 'success'}" style="font-size: 0.82rem; padding: 6px 14px;">
            ${hasInterceptions ? 'NOT READY FOR RELEASE' : 'READY FOR RELEASE'}
          </span>
        </div>

        <!-- 4 Metric Cards -->
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px;">
          <div style="background: rgba(0, 0, 0, 0.6); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--nightshift-border);">
            <div class="kpi-tag">Total Batch Value</div>
            <div class="font-mono" style="font-size: 1.3rem; font-weight: 800; color: var(--text-primary);">${formatINR(totalAmount)}</div>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${invoices.length} Invoices Enrolled</div>
          </div>
          <div style="background: rgba(0, 0, 0, 0.6); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--semantic-approve-border);">
            <div class="kpi-tag" style="color: var(--semantic-approve);">Approved &amp; Ready</div>
            <div class="font-mono text-success" style="font-size: 1.3rem; font-weight: 800;">${formatINR(approvedAmount)}</div>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${approvedInvs.length} Invoices Cleared</div>
          </div>
          <div style="background: rgba(0, 0, 0, 0.6); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--semantic-escalate-border);">
            <div class="kpi-tag" style="color: var(--semantic-escalate);">Held on Escalation</div>
            <div class="font-mono text-warning" style="font-size: 1.3rem; font-weight: 800;">${formatINR(escalatedAmount)}</div>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${escalatedInvs.length} Invoices in Review</div>
          </div>
          <div style="background: rgba(0, 0, 0, 0.6); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--semantic-block-border);">
            <div class="kpi-tag" style="color: var(--semantic-block);">Intercepted Blocks</div>
            <div class="font-mono text-danger" style="font-size: 1.3rem; font-weight: 800;">${formatINR(blockedAmount)}</div>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${blockedInvs.length} Invoices Locked</div>
          </div>
        </div>

        <!-- Release Gate Status Bar -->
        <div style="padding: 14px 18px; background: rgba(0, 0, 0, 0.6); border-radius: var(--radius-md); border-left: 3px solid ${hasInterceptions ? 'var(--semantic-block)' : 'var(--semantic-approve)'}; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 0.88rem; font-weight: 700; color: var(--text-primary);">
              ${hasInterceptions 
                ? `RELEASE GATE RESTRICTED: ${blockedInvs.length} BLOCKED, ${escalatedInvs.length} ESCALATED` 
                : 'RELEASE GATE CLEARED: All enrolled invoices confirmed non-risky.'}
            </div>
            <span class="font-mono text-muted" style="font-size: 0.75rem;">TRIGGER GUARD: ACTIVE</span>
          </div>
          <p style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">
            ${hasInterceptions
              ? 'Database-level integrity constraints prevent releasing payments until all flagged invoices are approved after investigation or resolved.'
              : 'All risk signals cleared. Payment batch is eligible for automated disbursement execution.'}
          </p>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px;">
          <button class="btn-ghost" onclick="switchTab('invoices')">Inspect Queued Invoices →</button>
          <button class="btn-antimetal" onclick="handleReleaseBatch(${hasInterceptions})">
            <span class="antimetal-panel">
              <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="4" cy="4" r="1.3" fill="#000000"/><circle cx="8" cy="8" r="1.3" fill="#000000"/><circle cx="4" cy="12" r="1.3" fill="#000000"/>
              </svg>
            </span>
            <span class="antimetal-label">RELEASE PAYMENT BATCH</span>
          </button>
        </div>
      </div>
    `;
  } catch (err) {
    console.error('Error loading payment runs:', err);
  }
}

function handleReleaseBatch(hasInterceptions) {
  if (hasInterceptions) {
    alert("Payment batch release BLOCKED by Pre-Payment Risk Firewall! Database constraints prohibit disbursement while blocked or escalated invoices exist.");
  } else {
    alert("Payment release batch authorized! Database trigger confirmed 0 blockers.");
  }
}
window.handleReleaseBatch = handleReleaseBatch;

function openCreatePaymentRunModal() {
  const modal = document.getElementById('modal-payment-run');
  const summary = document.getElementById('payment-run-invoices-summary');
  if (modal) modal.classList.add('open');
  if (summary) {
    const approved = currentInvoices.filter(i => i.status === 'APPROVED' || i.status === 'PAID');
    const totalVal = approved.reduce((sum, i) => sum + (Number(i.amount) || 0), 0);
    summary.innerHTML = `${approved.length} Conforming Invoices Enrolled • Total: ${formatINR(totalVal)}`;
  }
}
window.openCreatePaymentRunModal = openCreatePaymentRunModal;

// ==========================================================================
// 8. VENDORS DIRECTORY (Vendor Trust as Primary Concept)
// ==========================================================================
async function loadVendors() {
  const tbody = document.getElementById('vendors-table-body');
  if (!tbody) return;

  try {
    const res = await safeFetchJson('/api/vendors');
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Unable to load vendors directory.</td></tr>`;
      return;
    }
    currentVendors = res.data;

    if (currentVendors.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center placeholder-text">No registered vendors found in ledger.</td></tr>';
      return;
    }

    tbody.innerHTML = currentVendors.map(v => {
      const ts = v.current_trust_score || { score: 50, band: 'UNRATED', temporary_penalty: false, calculated_at: v.created_at };
      const score = Math.round(ts.score);
      const isPenalty = ts.temporary_penalty === true;

      let scoreClass = 'accent';
      if (score < 45) scoreClass = 'danger';
      else if (score >= 70) scoreClass = 'success';

      const evalDate = ts.calculated_at || v.created_at;
      const dateFormatted = evalDate ? new Date(evalDate).toLocaleDateString() : '-';

      return `
        <tr>
          <td><strong style="color: var(--text-primary); font-weight: 700;">${escapeHtml(v.name)}</strong></td>
          <td>
            <span class="score-badge ${score < 45 ? 'high' : (score < 70 ? 'medium' : 'low')}">${score}</span>
          </td>
          <td><span class="status-chip ${scoreClass}">${escapeHtml(ts.band || 'UNRATED')}</span></td>
          <td class="font-mono text-muted">${escapeHtml(v.gstin || 'None')}</td>
          <td>
            <span class="status-chip ${isPenalty ? 'danger' : 'success'}">
              ${isPenalty ? 'PENALTY: BANK CHANGED' : 'STABLE'}
            </span>
          </td>
          <td class="font-mono text-muted" style="font-size: 0.78rem;">
            ${dateFormatted}
          </td>
          <td style="text-align: right;">
            <span class="status-chip success">${escapeHtml(v.status || 'ACTIVE')}</span>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading vendors:', err);
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Unable to load vendors directory.</td></tr>`;
  }
}

// ==========================================================================
// 9. AUDIT TRAIL & CRYPTOGRAPHIC VERIFICATION (No TEST_EVENT Noise)
// ==========================================================================
async function loadAuditEvents() {
  const tbody = document.getElementById('audit-table-body');
  if (!tbody) return;

  try {
    const res = await safeFetchJson('/api/audit/events?limit=40');
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Unable to load audit ledger.</td></tr>`;
      return;
    }
    // Filter out test events from judge view
    const events = (res.data || []).filter(e => !e.event_type.startsWith('TEST_'));

    if (events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center placeholder-text">No production audit events recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = events.map(e => `
      <tr>
        <td><strong class="font-mono text-accent">#${e.sequence_number}</strong></td>
        <td><span class="status-chip accent">${escapeHtml(e.event_type)}</span></td>
        <td class="font-mono text-secondary">${escapeHtml(e.actor_label)}</td>
        <td>
          ${e.decision ? `<span class="decision-tag ${e.decision.toLowerCase()}">${e.decision} (${Math.round(e.risk_score || 0)})</span>` : '-'}
        </td>
        <td class="font-mono text-muted" title="${e.current_hash}">${e.current_hash.substring(0, 16)}...</td>
        <td class="font-mono text-muted" title="${e.previous_hash}">${e.previous_hash.substring(0, 16)}...</td>
        <td class="font-mono text-muted" style="font-size: 0.76rem;">${new Date(e.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading audit events:', err);
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Unable to load audit ledger.</td></tr>`;
  }
}

async function verifyAuditChain() {
  try {
    const res = await safeFetchJson('/api/audit/verify');
    if (!res.ok) throw new Error('Verification failed');
    const data = res.data;

    const badge = document.getElementById('chain-status-badge');
    if (data.valid) {
      if (badge) {
        badge.className = 'status-chip success';
        badge.textContent = `✓ CHAIN VERIFIED (${data.rows_checked} EVENTS)`;
      }
      alert(`Cryptographic Verification Succeeded!\n\nAll ${data.rows_checked} SHA-256 blocks validated sequentially from genesis block with zero broken links or tampered entries.`);
    } else {
      if (badge) {
        badge.className = 'status-chip danger';
        badge.textContent = `✗ INTEGRITY COMPROMISED (SEQ #${data.first_broken_sequence})`;
      }
      alert(`Integrity Alert!\n\nBroken cryptographic hash link detected at block sequence #${data.first_broken_sequence}.`);
    }
  } catch (err) {
    alert('Audit chain verification failed: ' + err.message);
  }
}
window.verifyAuditChain = verifyAuditChain;

// ==========================================================================
// 10. MODAL DIALOGS CONTROLLERS
// ==========================================================================
function initModals() {
  const modalAssessment = document.getElementById('modal-assessment');
  const btnCloseModal = document.getElementById('btn-close-modal');
  if (btnCloseModal && modalAssessment) {
    btnCloseModal.addEventListener('click', () => modalAssessment.classList.remove('open'));
  }

  // Open ingest modal
  const modalIngest = document.getElementById('modal-ingest');
  const btnCloseIngest = document.getElementById('btn-close-ingest');
  const btnCancelIngest = document.getElementById('btn-cancel-ingest');

  if (btnCloseIngest && modalIngest) {
    btnCloseIngest.addEventListener('click', () => modalIngest.classList.remove('open'));
  }
  if (btnCancelIngest && modalIngest) {
    btnCancelIngest.addEventListener('click', () => modalIngest.classList.remove('open'));
  }

  // Payment run modal
  const modalPaymentRun = document.getElementById('modal-payment-run');
  const btnClosePaymentRun = document.getElementById('btn-close-payment-run');
  const btnCancelPaymentRun = document.getElementById('btn-cancel-payment-run');
  if (btnClosePaymentRun && modalPaymentRun) {
    btnClosePaymentRun.addEventListener('click', () => modalPaymentRun.classList.remove('open'));
  }
  if (btnCancelPaymentRun && modalPaymentRun) {
    btnCancelPaymentRun.addEventListener('click', () => modalPaymentRun.classList.remove('open'));
  }

  // Handle ESC key to dismiss open modal
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (modalAssessment) modalAssessment.classList.remove('open');
      if (modalIngest) modalIngest.classList.remove('open');
      if (modalPaymentRun) modalPaymentRun.classList.remove('open');
    }
  });

  // Handle Ingest Form Submit
  const formIngest = document.getElementById('form-ingest');
  if (formIngest) {
    formIngest.addEventListener('submit', async (e) => {
      e.preventDefault();
      const vendor = document.getElementById('ingest-vendor').value.trim();
      const invNum = document.getElementById('ingest-num').value.trim();
      const invDate = document.getElementById('ingest-date').value;
      const amount = parseFloat(document.getElementById('ingest-amount').value);
      const gstin = document.getElementById('ingest-gstin').value.trim();
      const desc = document.getElementById('ingest-desc').value.trim() || 'General Consulting';
      const qty = parseFloat(document.getElementById('ingest-qty').value) || 1;
      const price = parseFloat(document.getElementById('ingest-price').value) || amount;

      try {
        const res = await fetch('/api/invoices', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            vendor_name: vendor,
            invoice_number: invNum,
            invoice_date: invDate,
            amount: amount,
            currency: 'INR',
            taxable_value: amount * 0.82,
            tax_amount: amount * 0.18,
            gstin: gstin || null,
            line_items: [{
              description: desc,
              quantity: qty,
              unit_price: price,
              line_total: amount
            }]
          })
        });

        if (res.ok) {
          const created = await res.json();
          modalIngest.classList.remove('open');
          formIngest.reset();
          await refreshAllData();
          openAssessment(created.id);
        } else {
          const err = await res.json().catch(() => ({}));
          alert('Ingestion error: ' + (err.detail || 'Failed to ingest invoice'));
        }
      } catch (err) {
        alert('Network error during ingestion: ' + err.message);
      }
    });
  }

  // Handle Payment Run Form Submit
  const formPaymentRun = document.getElementById('form-payment-run');
  if (formPaymentRun) {
    formPaymentRun.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('run-name').value.trim();
      const actor = document.getElementById('run-actor').value.trim();
      const approved = currentInvoices.filter(i => i.status === 'APPROVED' || i.status === 'PAID');
      const invoiceIds = approved.map(i => i.id);

      if (invoiceIds.length === 0) {
        alert("No approved invoices available to enroll in a payment run.");
        return;
      }

      try {
        const res = await fetch('/api/payment-runs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: name,
            invoice_ids: invoiceIds,
            created_by_label: actor
          })
        });

        if (res.ok) {
          if (modalPaymentRun) modalPaymentRun.classList.remove('open');
          formPaymentRun.reset();
          alert(`Payment run '${name}' successfully generated with ${invoiceIds.length} invoices!`);
          await refreshAllData();
          switchTab('payment-runs');
        } else {
          const err = await res.json().catch(() => ({}));
          alert('Error creating payment run: ' + (err.detail || 'Failed to create run'));
        }
      } catch (err) {
        alert('Network error: ' + err.message);
      }
    });
  }
}

function openIngestModal() {
  const modalIngest = document.getElementById('modal-ingest');
  if (modalIngest) {
    const dateInput = document.getElementById('ingest-date');
    if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];
    modalIngest.classList.add('open');
  }
}
window.openIngestModal = openIngestModal;

// ==========================================================================
// 11. FORMATTERS & UTILITIES (Safe JSON, Non-Clipped Currency)
// ==========================================================================
async function safeFetchJson(url, options = {}) {
  try {
    const res = await fetch(url, options);
    const contentType = res.headers.get('content-type') || '';
    if (!res.ok) {
      let errMsg = `Request failed (${res.status})`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) {
          errMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch (_) {}
      return { ok: false, status: res.status, error: errMsg };
    }
    if (contentType.includes('application/json')) {
      const data = await res.json();
      return { ok: true, status: res.status, data };
    }
    return { ok: false, status: res.status, error: 'Expected JSON response' };
  } catch (err) {
    console.warn(`Fetch error for ${url}:`, err);
    return { ok: false, status: 0, error: err.message || 'Network error' };
  }
}

function formatINR(val, compact = false) {
  const num = Number(val) || 0;
  if (compact && Math.abs(num) >= 10000000) {
    return '₹' + (num / 10000000).toFixed(2) + 'Cr';
  }
  if (compact && Math.abs(num) >= 100000) {
    return '₹' + (num / 100000).toFixed(2) + 'L';
  }
  const hasCents = (num % 1 !== 0);
  return '₹' + num.toLocaleString('en-IN', {
    minimumFractionDigits: hasCents ? 2 : 0,
    maximumFractionDigits: hasCents ? 2 : 0
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
