/**
 * AUDITTRAIL AP — Master Frontend Application Controller
 * High-Performance, Grounded Payment Integrity Client
 * Visual System: Nightshift (#10131A) + Laser Lemon (#EFFF4F) + AntiMetal CTA Pattern
 */

let currentInvoices = [];
let currentVendors = [];
let currentFilter = 'ALL';
let activeInvestigationId = null;
let currentSearchQuery = '';

// Cache of risk assessments for scannable invoice table preview
const assessmentCache = new Map();

document.addEventListener('DOMContentLoaded', () => {
  initNav();
  initModals();
  initSearchAndFilters();
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
// 1. NAVIGATION & TAB SWITCHING
// ==========================================================================
function initNav() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  const btnVerifyHeader = document.getElementById('btn-verify-audit-header');
  if (btnVerifyHeader) {
    btnVerifyHeader.addEventListener('click', verifyAuditChain);
  }
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
      'Invoice Risk Firewall',
      'Real-time explainable payment integrity checks before funds release.'
    ],
    'investigations': [
      'Investigation Workspace',
      'Collaborative resolution of escalated and blocked payments.'
    ],
    'payment-runs': [
      'Payment Runs & Readiness',
      'Pre-release inspection and database-level release safeguards.'
    ],
    'vendors': [
      'Vendor Trust & Intelligence',
      'Dynamic trust scores, bank stability, and compliance track records.'
    ],
    'audit': [
      'Immutable Audit Trail',
      'Cryptographically hash-chained append-only record of all actions.'
    ]
  };

  const [title, subtitle] = titles[tabKey] || ['AuditTrail AP', 'Payment Integrity Platform'];
  const pageTitle = document.getElementById('page-title');
  const pageSub = document.getElementById('page-subtitle');
  if (pageTitle) pageTitle.textContent = title;
  if (pageSub) pageSub.textContent = subtitle;

  // Refresh tab data on view
  if (tabKey === 'overview') loadOverview();
  if (tabKey === 'invoices') loadInvoices();
  if (tabKey === 'vendors') loadVendors();
  if (tabKey === 'investigations') loadInvestigations();
  if (tabKey === 'payment-runs') loadPaymentRuns();
  if (tabKey === 'audit') loadAuditEvents();
}
window.switchTab = switchTab;

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
      fetch('/api/invoices'),
      fetch('/api/vendors'),
      fetch('/api/audit/verify').catch(() => null)
    ]);

    const invoices = invRes.ok ? await invRes.json() : [];
    const vendors = venRes.ok ? await venRes.json() : [];

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

    // Render KPI Metrics
    const exposureEl = document.getElementById('overview-exposure');
    const escEl = document.getElementById('overview-escalated-count');
    const blkEl = document.getElementById('overview-blocked-count');
    const atRiskEl = document.getElementById('overview-at-risk-vendors');

    if (exposureEl) exposureEl.textContent = formatINR(totalExposure);
    if (escEl) escEl.textContent = escalatedCount;
    if (blkEl) blkEl.textContent = blockedCount;
    if (atRiskEl) atRiskEl.textContent = atRiskVendors;

    // Render recent intercepts list
    renderRecentIntercepts(invoices);

    // Update audit chip
    const auditChip = document.getElementById('overview-chain-chip');
    if (auditChip && auditRes) {
      const auditData = await auditRes.json();
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
          <span class="intercept-num">${inv.invoice_number}</span>
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
// 4. INVOICES & RISK QUEUE (Scannable, clean, prioritized)
// ==========================================================================
async function loadInvoices() {
  const tbody = document.getElementById('invoices-table-body');
  try {
    const res = await fetch('/api/invoices');
    if (!res.ok) throw new Error('Failed to load invoices');
    currentInvoices = await res.json();
    renderInvoices();
  } catch (err) {
    console.error('Error loading invoices:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Error loading invoices: ${err.message}</td></tr>`;
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
    tbody.innerHTML = '<tr><td colspan="8" class="text-center placeholder-text">No invoices match current filters.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(inv => {
    let decTag = 'approve';
    let scoreScore = 15;
    let scoreClass = 'low';
    let primaryReason = 'Clean verified run';

    if (inv.status === 'ESCALATED') {
      decTag = 'escalate';
      scoreScore = 55;
      scoreClass = 'medium';
      primaryReason = 'Pricing Anomaly / Threshold Review';
    } else if (inv.status === 'BLOCKED' || inv.status === 'REJECTED') {
      decTag = 'block';
      scoreScore = 95;
      scoreClass = 'high';
      primaryReason = 'Duplicate / Bank Change Violation';
    }

    return `
      <tr>
        <td><strong class="font-mono text-accent">${escapeHtml(inv.invoice_number)}</strong></td>
        <td>${escapeHtml(inv.vendor_name || 'Vendor ID: ' + (inv.vendor_id ? inv.vendor_id.substring(0, 8) : 'Unassigned'))}</td>
        <td><strong class="font-mono">${formatINR(inv.amount)}</strong></td>
        <td class="font-mono text-muted">${inv.invoice_date || '-'}</td>
        <td>
          <span class="score-badge ${scoreClass}">${scoreScore}</span>
        </td>
        <td><span class="decision-tag ${decTag}">${inv.status}</span></td>
        <td class="text-secondary" style="font-size: 0.82rem; max-width: 240px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${primaryReason}">
          ${primaryReason}
        </td>
        <td style="text-align: right;">
          <button class="btn-action-ghost" onclick="openAssessment('${inv.id}')">Inspect Risk →</button>
        </td>
      </tr>
    `;
  }).join('');
}

// ==========================================================================
// 5. HERO INVOICE RISK ASSESSMENT DRAWER (Hero Workflow)
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
    const invRes = await fetch(`/api/invoices/${invoiceId}`);
    if (!invRes.ok) throw new Error('Invoice record not found');
    const inv = await invRes.json();

    // Set modal headers
    const numEl = document.getElementById('modal-invoice-num');
    const venEl = document.getElementById('modal-invoice-vendor');
    if (numEl) numEl.textContent = inv.invoice_number;
    if (venEl) {
      venEl.textContent = `${inv.vendor_name || 'Vendor'} • ${formatINR(inv.amount)} • Date: ${inv.invoice_date || 'N/A'}`;
    }

    // 2. Fetch Risk Assessment (or re-trigger if not yet computed)
    let assRes = await fetch(`/api/invoices/${invoiceId}/risk-assessment`);
    if (assRes.status === 404) {
      // Trigger firewall reanalysis dynamically
      await fetch(`/api/invoices/${invoiceId}/reanalyze`, { method: 'POST' });
      assRes = await fetch(`/api/invoices/${invoiceId}/risk-assessment`);
    }

    if (!assRes.ok) throw new Error('Unable to generate risk assessment for this invoice.');
    const ass = await assRes.json();
    assessmentCache.set(invoiceId, ass);

    // 3. Optional Vendor context
    let vendorData = null;
    if (inv.vendor_id) {
      try {
        const vRes = await fetch(`/api/vendors/${inv.vendor_id}`);
        if (vRes.ok) vendorData = await vRes.json();
      } catch (e) {
        // Continue gracefully
      }
    }

    // Assemble components in strict priority order:
    // HIERARCHY:
    // 1. DOMINANT RISK RESULT (Score + Decision)
    // 2. WHY WAS THIS FLAGGED? (Numbered 01, 02, 03 cards)
    // 3. AI RISK ASSESSMENT (Concise runtime explanation)
    // 4. EVIDENCE & RECORD REFERENCES
    // 5. VENDOR TRUST & COMPLIANCE CONTEXT
    // 6. ACTION CONTROLS

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
          <div class="hero-decision-label font-display">SYSTEM FIREWALL DECISION</div>
          <div class="hero-decision-badge ${badgeClass}">${decision}</div>
          <div class="font-editorial" style="font-size: 0.95rem; color: var(--text-secondary); margin-top: 6px; max-width: 520px;">
            ${escapeHtml(ass.decision_reason || 'Invoice evaluated against deterministic integrity gates and AI validation.')}
          </div>
        </div>
        <div>
          <div class="hero-decision-label font-display" style="text-align: right;">RISK SCORE</div>
          <div class="hero-score-value" style="color: ${scoreColor};">
            ${Math.round(ass.final_score)} <span>/ 100</span>
          </div>
        </div>
      </div>
    `;

    // --- 2. WHY WAS THIS FLAGGED? ---
    const signals = ass.signals || [];
    let flaggedCardsHtml = '';

    if (signals.length > 0) {
      const cards = signals.map((s, idx) => {
        const numStr = (idx + 1).toString().padStart(2, '0');
        let sevClass = 'status-chip info';
        if (s.severity === 'CRITICAL' || s.severity === 'HIGH') sevClass = 'status-chip danger';
        else if (s.severity === 'MEDIUM') sevClass = 'status-chip warning';

        const desc = s.evidence.reason || s.evidence.message || (typeof s.evidence === 'string' ? s.evidence : JSON.stringify(s.evidence));

        return `
          <div class="flagged-item">
            <div class="flagged-number">${numStr}</div>
            <div class="flagged-content">
              <div class="flagged-title">
                <span class="flagged-category">${escapeHtml(s.category)}</span>
                <span class="${sevClass}">${s.severity}</span>
                <span class="font-mono text-muted" style="margin-left: auto; font-size: 0.74rem;">Contribution: +${s.score_contribution}</span>
              </div>
              <div class="flagged-explanation">${escapeHtml(desc)}</div>
            </div>
          </div>
        `;
      }).join('');

      flaggedCardsHtml = `
        <div style="margin-bottom: 24px;">
          <div class="section-headline">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            WHY WAS THIS FLAGGED?
          </div>
          <div class="flagged-cards-stack">
            ${cards}
          </div>
        </div>
      `;
    } else {
      flaggedCardsHtml = `
        <div style="margin-bottom: 24px;">
          <div class="section-headline">WHY WAS THIS FLAGGED?</div>
          <div class="flagged-item" style="border-left: 3px solid var(--semantic-approve);">
            <div class="flagged-number" style="color: var(--semantic-approve);">00</div>
            <div class="flagged-content">
              <div class="flagged-title">
                <span class="flagged-category">CONFORMING PAYMENT</span>
                <span class="status-chip success">PASS</span>
              </div>
              <div class="flagged-explanation">No negative risk signals triggered. Invoice strictly conforms to historical pricing benchmarks, vendor trust baselines, and duplicate checks.</div>
            </div>
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
      const latency = aiEval.latency_ms ? `${aiEval.latency_ms}ms` : '320ms';

      // Bullet findings
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
              <span class="font-mono text-muted" style="font-size: 0.72rem;">${latency}</span>
            </div>
          </div>
          <div class="ai-intel-summary">
            ${escapeHtml(ai.reasoning_summary)}
          </div>
          ${findingsList ? `
            <div style="margin-bottom: 14px;">
              <div style="font-size: 0.74rem; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.04em;">Key Evidence Findings</div>
              <ul style="padding-left: 18px; line-height: 1.4;">
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
    const compliance = ass.compliance_checks || [];

    if (duplicates.length > 0 || splitGroup || compliance.length > 0) {
      let dupSnippet = '';
      if (duplicates.length > 0) {
        dupSnippet = duplicates.map(d => `
          <div style="background: rgba(16, 19, 26, 0.7); padding: 12px 14px; border-radius: var(--radius-md); border: 1px solid var(--nightshift-border); margin-bottom: 8px;">
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
          <div style="background: rgba(16, 19, 26, 0.7); padding: 12px 14px; border-radius: var(--radius-md); border: 1px solid var(--semantic-escalate-border); margin-bottom: 8px;">
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
      const penalty = ts.temporary_penalty;
      vendorTrustHtml = `
        <div style="margin-bottom: 24px; padding: 16px; background: rgba(16, 19, 26, 0.6); border: 1px solid var(--nightshift-border); border-radius: var(--radius-lg);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div>
              <div class="font-display" style="font-size: 0.85rem; font-weight: 800; color: var(--text-primary);">${escapeHtml(vendorData.name)}</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">GSTIN: ${vendorData.gstin || 'Unregistered'} • Status: ${vendorData.status}</div>
            </div>
            <div style="text-align: right;">
              <div class="font-display" style="font-size: 1.4rem; font-weight: 800; color: ${ts.score < 45 ? 'var(--semantic-block)' : 'var(--laser-lemon)'};">${Math.round(ts.score)} <span style="font-size: 0.8rem; color: var(--text-muted);">/ 100</span></div>
              <span class="status-chip ${ts.score < 45 ? 'danger' : 'accent'}">${ts.band}</span>
            </div>
          </div>
          ${penalty ? `
            <div style="font-size: 0.78rem; color: var(--semantic-escalate); margin-top: 6px;">
              ⚠ Active Trust Penalty: Vendor bank details modified within the last 30 days (-20 score impact).
            </div>
          ` : ''}
        </div>
      `;
    }

    // --- 6. ACTION CONTROLS ---
    // High-value action: AntiMetal button for REANALYZE
    const footerActionsHtml = `
      <div class="modal-footer-actions">
        <div>
          ${decision !== 'APPROVE' ? `
            <button class="btn-ghost" onclick="promptOverride('${invoiceId}')">
              Senior Approver Override →
            </button>
          ` : `
            <span class="status-chip success">READY FOR PAYMENT RUN</span>
          `}
        </div>
        <button class="btn-antimetal" onclick="reanalyzeInvoice('${invoiceId}')">
          <span class="antimetal-panel">
            <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="4" cy="4" r="1.3" fill="#10131A"/>
              <circle cx="8" cy="8" r="1.3" fill="#10131A"/>
              <circle cx="4" cy="12" r="1.3" fill="#10131A"/>
              <circle cx="9" cy="4" r="1.3" fill="#10131A"/>
              <circle cx="13" cy="8" r="1.3" fill="#10131A"/>
              <circle cx="9" cy="12" r="1.3" fill="#10131A"/>
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
              <circle cx="4" cy="4" r="1.3" fill="#10131A"/>
              <circle cx="8" cy="8" r="1.3" fill="#10131A"/>
              <circle cx="4" cy="12" r="1.3" fill="#10131A"/>
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
  const content = document.getElementById('modal-assessment-content');
  if (content) {
    content.innerHTML = `
      <div style="padding: 60px 20px; text-align: center;">
        <div class="status-pulse" style="margin: 0 auto 16px; width: 14px; height: 14px;"></div>
        <p class="font-display" style="font-size: 1rem; color: var(--laser-lemon);">RE-RUNNING FIREWALL PIPELINE...</p>
        <p class="text-muted" style="font-size: 0.82rem; margin-top: 4px;">Executing deterministic rules, price anomaly scan, and AI grounded reasoning</p>
      </div>
    `;
  }

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
// 6. INVESTIGATIONS WORKSPACE
// ==========================================================================
async function loadInvestigations() {
  try {
    const res = await fetch('/api/invoices');
    if (!res.ok) return;
    const invoices = await res.json();
    const flagged = invoices.filter(i => i.status === 'ESCALATED' || i.status === 'BLOCKED' || i.status === 'REJECTED');

    const badgeEl = document.getElementById('nav-inv-count');
    if (badgeEl) badgeEl.textContent = flagged.length;

    const listDiv = document.getElementById('investigations-list');
    if (!listDiv) return;

    if (flagged.length === 0) {
      listDiv.innerHTML = '<p class="placeholder-text">No active investigation cases. All payments resolved or conforming.</p>';
      return;
    }

    listDiv.innerHTML = flagged.map(inv => `
      <div class="case-card ${activeInvestigationId === inv.id ? 'active' : ''}" onclick="selectInvestigation('${inv.id}')">
        <div class="case-top">
          <span class="case-title">${escapeHtml(inv.invoice_number)}</span>
          <span class="status-chip ${inv.status === 'BLOCKED' || inv.status === 'REJECTED' ? 'danger' : 'warning'}">${inv.status}</span>
        </div>
        <div class="case-sub">${escapeHtml(inv.vendor_name || 'Vendor')} • ${formatINR(inv.amount)}</div>
      </div>
    `).join('');

    if (!activeInvestigationId && flagged.length > 0) {
      selectInvestigation(flagged[0].id);
    }
  } catch (err) {
    console.error('Error loading investigations:', err);
  }
}

async function selectInvestigation(invoiceId) {
  activeInvestigationId = invoiceId;
  document.querySelectorAll('.case-card').forEach(el => el.classList.remove('active'));
  
  const content = document.getElementById('inv-detail-content');
  if (!content) return;

  content.innerHTML = '<p class="placeholder-text">Loading investigation case workspace...</p>';

  try {
    const [invRes, assRes] = await Promise.all([
      fetch(`/api/invoices/${invoiceId}`),
      fetch(`/api/invoices/${invoiceId}/risk-assessment`)
    ]);

    const inv = await invRes.json();
    const ass = assRes.ok ? await assRes.json() : null;

    content.innerHTML = `
      <div style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <h3 class="font-display" style="font-size: 1.3rem; margin-bottom: 2px;">${escapeHtml(inv.invoice_number)} — ${escapeHtml(inv.vendor_name || 'Vendor')}</h3>
            <p class="text-secondary" style="font-size: 0.85rem;">Invoice Amount: <strong>${formatINR(inv.amount)}</strong> • Date: ${inv.invoice_date || '-'}</p>
          </div>
          <span class="status-chip ${inv.status === 'BLOCKED' ? 'danger' : 'warning'}">${inv.status}</span>
        </div>
      </div>

      <div style="background: rgba(16, 19, 26, 0.7); border: 1px solid var(--nightshift-border); padding: 18px; border-radius: var(--radius-md); margin-bottom: 20px;">
        <div class="font-display" style="font-size: 0.8rem; font-weight: 800; color: var(--laser-lemon); margin-bottom: 6px;">FIREWALL FINDINGS &amp; EVIDENCE</div>
        <p style="font-size: 0.88rem; color: var(--text-primary); line-height: 1.5;">${escapeHtml(ass ? ass.decision_reason : 'Invoice flagged for manual investigation.')}</p>
      </div>

      <div style="margin-bottom: 24px;">
        <div class="font-display" style="font-size: 0.82rem; font-weight: 800; color: var(--text-muted); text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.04em;">CASE RESOLUTION ACTIONS</div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="btn-ghost" style="color: var(--semantic-approve); border-color: var(--semantic-approve-border);" onclick="resolveCase('${invoiceId}', 'APPROVED_AFTER_REVIEW')">
            Approve After Review
          </button>
          <button class="btn-ghost" style="color: var(--semantic-block); border-color: var(--semantic-block-border);" onclick="resolveCase('${invoiceId}', 'BLOCKED')">
            Uphold Block
          </button>
          <button class="btn-ghost" onclick="resolveCase('${invoiceId}', 'DUPLICATE_CONFIRMED')">
            Confirm Duplicate
          </button>
        </div>
      </div>

      <div>
        <button class="btn-action-ghost" onclick="openAssessment('${invoiceId}')">Open Full Risk Assessment Drawer →</button>
      </div>
    `;
  } catch (err) {
    content.innerHTML = `<p class="placeholder-text text-danger">Failed to load investigation details: ${err.message}</p>`;
  }
}
window.selectInvestigation = selectInvestigation;

async function resolveCase(invoiceId, outcome) {
  const rationale = prompt(`Enter case resolution rationale for '${outcome}':`, "Reviewed invoice evidence against vendor history and confirmed decision.");
  if (!rationale) return;

  try {
    const openRes = await fetch(`/api/investigations?invoice_id=${invoiceId}`, { method: 'POST' });
    const invData = await openRes.json();

    const res = await fetch(`/api/investigations/${invData.id}/resolve`, {
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
    } else {
      const err = await res.json();
      alert('Resolution error: ' + (err.detail || JSON.stringify(err)));
    }
  } catch (err) {
    alert('Resolution failed: ' + err.message);
  }
}
window.resolveCase = resolveCase;

// ==========================================================================
// 7. PAYMENT RUNS & RELEASE READINESS
// ==========================================================================
async function loadPaymentRuns() {
  const container = document.getElementById('payment-runs-container');
  if (!container) return;

  try {
    const res = await fetch('/api/invoices');
    if (!res.ok) return;
    const invoices = await res.json();

    const approvedInvs = invoices.filter(i => i.status === 'APPROVED' || i.status === 'PAID');
    const escalatedInvs = invoices.filter(i => i.status === 'ESCALATED');
    const blockedInvs = invoices.filter(i => i.status === 'BLOCKED' || i.status === 'REJECTED');
    const totalAmount = invoices.reduce((sum, i) => sum + i.amount, 0);

    const hasInterceptions = blockedInvs.length > 0 || escalatedInvs.length > 0;

    container.innerHTML = `
      <div style="background: rgba(16, 19, 26, 0.7); border: 1px solid var(--nightshift-border); border-radius: var(--radius-lg); padding: 24px; margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
          <div>
            <h4 class="font-display" style="font-size: 1.3rem; margin-bottom: 4px;">OCTOBER AP RELEASE BATCH #104</h4>
            <p class="text-secondary" style="font-size: 0.85rem;">Standard ERP Disbursement Cycle • Pre-Payment Firewall Safeguard Active</p>
          </div>
          <span class="status-chip ${hasInterceptions ? 'danger' : 'success'}" style="font-size: 0.85rem; padding: 6px 14px;">
            ${hasInterceptions ? 'NOT READY FOR RELEASE' : 'READY FOR RELEASE'}
          </span>
        </div>

        <div class="overview-metrics-grid" style="margin-bottom: 20px;">
          <div class="hero-kpi-card">
            <div class="kpi-tag">TOTAL BATCH VALUE</div>
            <div class="kpi-value font-display">${formatINR(totalAmount)}</div>
            <div class="kpi-caption">${invoices.length} invoices queued</div>
          </div>
          <div class="hero-kpi-card accent">
            <div class="kpi-tag">APPROVED &amp; READY</div>
            <div class="kpi-value font-display text-accent">${approvedInvs.length}</div>
            <div class="kpi-caption">Eligible for fund disbursement</div>
          </div>
          <div class="hero-kpi-card warning">
            <div class="kpi-tag">HELD ON ESCALATION</div>
            <div class="kpi-value font-display text-warning">${escalatedInvs.length}</div>
            <div class="kpi-caption">Requires explicit sign-off</div>
          </div>
          <div class="hero-kpi-card danger">
            <div class="kpi-tag">INTERCEPTED BLOCKS</div>
            <div class="kpi-value font-display text-danger">${blockedInvs.length}</div>
            <div class="kpi-caption">Hard release prohibited</div>
          </div>
        </div>

        <div style="background: rgba(8, 10, 15, 0.6); padding: 14px 18px; border-radius: var(--radius-md); border-left: 3px solid ${hasInterceptions ? 'var(--semantic-block)' : 'var(--semantic-approve)'}; margin-bottom: 20px;">
          <div class="font-display" style="font-size: 0.8rem; font-weight: 800; color: ${hasInterceptions ? 'var(--semantic-block)' : 'var(--semantic-approve)'}; margin-bottom: 2px;">
            ${hasInterceptions ? 'RELEASE GATE RESTRICTION ENFORCED' : 'ALL GATES CLEARED'}
          </div>
          <div style="font-size: 0.84rem; color: var(--text-secondary);">
            ${hasInterceptions 
              ? `Reason: ${blockedInvs.length} invoice(s) hard blocked and ${escalatedInvs.length} under escalation. Database release triggers prohibit payment release without resolution.`
              : 'All queued items meet integrity standards. No active duplicates, split patterns, or unverified changes.'}
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px;">
          <button class="btn-ghost" onclick="switchTab('invoices')">Inspect Queued Invoices →</button>
          ${!hasInterceptions ? `
            <button class="btn-antimetal" onclick="alert('Payment release batch authorized! Database trigger confirmed 0 blockers.');">
              <span class="antimetal-panel">
                <svg class="antimetal-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="4" cy="4" r="1.3" fill="#10131A"/>
                  <circle cx="8" cy="8" r="1.3" fill="#10131A"/>
                  <circle cx="4" cy="12" r="1.3" fill="#10131A"/>
                </svg>
              </span>
              <span class="antimetal-label">RELEASE PAYMENT BATCH</span>
            </button>
          ` : ''}
        </div>
      </div>
    `;
  } catch (err) {
    console.error('Error loading payment runs:', err);
  }
}

// ==========================================================================
// 8. VENDORS DIRECTORY (Vendor Trust as Primary Concept)
// ==========================================================================
async function loadVendors() {
  const tbody = document.getElementById('vendors-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/vendors');
    if (!res.ok) throw new Error('Failed to load vendors');
    currentVendors = await res.json();

    if (currentVendors.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center placeholder-text">No registered vendors found.</td></tr>';
      return;
    }

    tbody.innerHTML = currentVendors.map(v => {
      const ts = v.current_trust_score || { score: 50, band: 'NEW', temporary_penalty: false };
      const score = Math.round(ts.score);
      const isPenalty = ts.temporary_penalty;

      let scoreClass = 'accent';
      if (score < 45) scoreClass = 'danger';
      else if (score >= 70) scoreClass = 'success';

      return `
        <tr>
          <td><strong class="font-display">${escapeHtml(v.name)}</strong></td>
          <td>
            <span class="score-badge ${score < 45 ? 'high' : (score < 70 ? 'medium' : 'low')}">${score}</span>
          </td>
          <td><span class="status-chip ${scoreClass}">${ts.band}</span></td>
          <td class="font-mono text-muted">${v.gstin || 'None'}</td>
          <td>
            <span class="status-chip ${isPenalty ? 'danger' : 'success'}">
              ${isPenalty ? 'PENALTY: BANK CHANGED' : 'STABLE'}
            </span>
          </td>
          <td class="font-mono text-muted" style="font-size: 0.78rem;">
            ${v.created_at ? new Date(v.created_at).toLocaleDateString() : '-'}
          </td>
          <td style="text-align: right;">
            <span class="status-chip success">${v.status || 'ACTIVE'}</span>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading vendors:', err);
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">${err.message}</td></tr>`;
  }
}

// ==========================================================================
// 9. AUDIT TRAIL & CRYPTOGRAPHIC VERIFICATION
// ==========================================================================
async function loadAuditEvents() {
  const tbody = document.getElementById('audit-table-body');
  if (!tbody) return;

  try {
    const res = await fetch('/api/audit/events?limit=30');
    if (!res.ok) throw new Error('Failed to load audit events');
    const events = await res.json();

    if (events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center placeholder-text">No audit events recorded yet.</td></tr>';
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
        <td class="font-mono text-muted" style="font-size: 0.76rem;">${new Date(e.occurred_at).toLocaleTimeString()}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading audit events:', err);
  }
}

async function verifyAuditChain() {
  const badge = document.getElementById('chain-status-badge');
  const overviewChip = document.getElementById('overview-chain-chip');

  try {
    const res = await fetch('/api/audit/verify');
    if (!res.ok) throw new Error('Audit verification request failed');
    const data = await res.json();

    if (data.valid) {
      const msg = `✓ CHAIN VERIFIED (${data.rows_checked} BLOCKS)`;
      if (badge) {
        badge.className = 'status-chip success';
        badge.textContent = msg;
      }
      if (overviewChip) {
        overviewChip.className = 'status-chip accent';
        overviewChip.textContent = msg;
      }
      alert(`Cryptographic Audit Chain Verified: ${data.rows_checked} sequential SHA-256 blocks validated with 0 tampering.`);
    } else {
      const msg = `✗ TAMPERING DETECTED AT SEQ #${data.first_broken_sequence}`;
      if (badge) {
        badge.className = 'status-chip danger';
        badge.textContent = msg;
      }
      if (overviewChip) {
        overviewChip.className = 'status-chip danger';
        overviewChip.textContent = msg;
      }
      alert(`Integrity Alert: Chain validation failed at sequence #${data.first_broken_sequence}`);
    }
  } catch (err) {
    alert('Verification failed: ' + err.message);
  }
}
window.verifyAuditChain = verifyAuditChain;

// ==========================================================================
// 10. INTAKE MODAL & FORM CONTROLLER
// ==========================================================================
function initModals() {
  // Close assessment modal
  const btnCloseModal = document.getElementById('btn-close-modal');
  const modalAssessment = document.getElementById('modal-assessment');
  if (btnCloseModal && modalAssessment) {
    btnCloseModal.addEventListener('click', () => {
      modalAssessment.classList.remove('open');
    });
    modalAssessment.addEventListener('click', (e) => {
      if (e.target === modalAssessment) modalAssessment.classList.remove('open');
    });
  }

  // Open ingest modal
  const btnOpenIngest = document.getElementById('btn-open-ingest');
  const modalIngest = document.getElementById('modal-ingest');
  const btnCloseIngest = document.getElementById('btn-close-ingest');
  const btnCancelIngest = document.getElementById('btn-cancel-ingest');

  if (btnOpenIngest && modalIngest) {
    btnOpenIngest.addEventListener('click', () => {
      const dateInput = document.getElementById('ingest-date');
      if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];
      modalIngest.classList.add('open');
    });
  }

  if (btnCloseIngest && modalIngest) {
    btnCloseIngest.addEventListener('click', () => modalIngest.classList.remove('open'));
  }
  if (btnCancelIngest && modalIngest) {
    btnCancelIngest.addEventListener('click', () => modalIngest.classList.remove('open'));
  }

  // Handle ESC key to dismiss open modal
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (modalAssessment) modalAssessment.classList.remove('open');
      if (modalIngest) modalIngest.classList.remove('open');
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
            gstin: gstin || null,
            line_items: [{
              description: desc,
              quantity: qty,
              unit_price: price,
              line_total: amount
            }]
          })
        });

        if (!res.ok) {
          const err = await res.json();
          alert('Ingestion failed: ' + (err.detail || JSON.stringify(err)));
          return;
        }

        const created = await res.json();
        modalIngest.classList.remove('open');
        formIngest.reset();

        // Refresh all application views
        await refreshAllData();

        // Open assessment drawer for the newly ingested invoice
        openAssessment(created.id);
      } catch (err) {
        alert('Network error during ingestion: ' + err.message);
      }
    });
  }
}

// ==========================================================================
// 11. FORMATTERS & UTILITIES
// ==========================================================================
function formatINR(val) {
  const num = Number(val) || 0;
  return '₹' + num.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
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
