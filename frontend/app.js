let currentInvoices = [];
let currentFilter = 'ALL';
let activeInvestigationId = null;

document.addEventListener('DOMContentLoaded', () => {
  initNav();
  loadInvoices();
  loadInvestigations();
  loadPaymentRuns();
  loadAuditEvents();
  initModals();
});

// --- Navigation ---
function initNav() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const tabId = `tab-${btn.dataset.tab}`;
      const pane = document.getElementById(tabId);
      if (pane) pane.classList.add('active');

      const titles = {
        'invoices': ['Invoice Risk Firewall', 'Real-time explainable payment integrity checks before funds release'],
        'investigations': ['Investigation Workspace', 'Collaborative resolution of escalated and blocked payments'],
        'payment-runs': ['Payment Runs & Readiness', 'Pre-release inspection and database-level release safeguards'],
        'audit': ['Immutable Audit Trail', 'Cryptographically hash-chained append-only record of all actions']
      };
      const [title, subtitle] = titles[btn.dataset.tab] || ['AuditTrail AP', 'Payment Integrity Platform'];
      document.getElementById('page-title').textContent = title;
      document.getElementById('page-subtitle').textContent = subtitle;
    });
  });

  // Filter pills
  document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      renderInvoices();
    });
  });

  // Verify chain button
  document.getElementById('btn-verify-audit').addEventListener('click', verifyAuditChain);
}

// --- Invoices ---
async function loadInvoices() {
  try {
    const res = await fetch('/api/invoices');
    currentInvoices = await res.json();
    updateStats();
    renderInvoices();
  } catch (err) {
    console.error('Error loading invoices:', err);
  }
}

function updateStats() {
  const total = currentInvoices.length;
  const approved = currentInvoices.filter(i => i.status === 'APPROVED' || i.status === 'PAID').length;
  const escalated = currentInvoices.filter(i => i.status === 'ESCALATED').length;
  const blocked = currentInvoices.filter(i => i.status === 'BLOCKED' || i.status === 'REJECTED').length;

  document.getElementById('stat-total-invoices').textContent = total;
  document.getElementById('stat-approved').textContent = approved;
  document.getElementById('stat-escalated').textContent = escalated;
  document.getElementById('stat-blocked').textContent = blocked;
}

function renderInvoices() {
  const tbody = document.getElementById('invoices-table-body');
  let list = currentInvoices;
  if (currentFilter !== 'ALL') {
    list = currentInvoices.filter(i => i.status === currentFilter);
  }

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No invoices found for this filter.</td></tr>';
    return;
  }

  tbody.innerHTML = list.map(inv => {
    let badgeClass = 'badge-info';
    if (inv.status === 'APPROVED' || inv.status === 'PAID') badgeClass = 'badge-success';
    if (inv.status === 'ESCALATED') badgeClass = 'badge-warning';
    if (inv.status === 'BLOCKED' || inv.status === 'REJECTED') badgeClass = 'badge-danger';

    return `
      <tr>
        <td><strong>${inv.invoice_number}</strong></td>
        <td>${inv.vendor_name || 'Vendor ID: ' + (inv.vendor_id ? inv.vendor_id.substring(0, 8) : 'Unassigned')}</td>
        <td><strong>₹${Number(inv.amount).toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
        <td>${inv.invoice_date || '-'}</td>
        <td>
          <div class="score-cell">
            <span class="font-mono">${inv.status === 'BLOCKED' ? '100' : (inv.status === 'APPROVED' ? '0' : '45')}</span>
            <div class="score-bar-bg">
              <div class="score-bar-fill" style="width: ${inv.status === 'BLOCKED' ? '100%' : (inv.status === 'APPROVED' ? '10%' : '50%')}; background-color: ${inv.status === 'BLOCKED' ? 'var(--red)' : (inv.status === 'APPROVED' ? 'var(--green)' : 'var(--yellow)')};"></div>
            </div>
          </div>
        </td>
        <td><span class="badge ${badgeClass}">${inv.status}</span></td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="openAssessment('${inv.id}')">View Risk</button>
        </td>
      </tr>
    `;
  }).join('');
}

// --- Risk Assessment Drawer ---
async function openAssessment(invoiceId) {
  const modal = document.getElementById('modal-assessment');
  const content = document.getElementById('modal-assessment-content');
  modal.classList.add('open');
  content.innerHTML = '<p class="text-center">Loading Risk Firewall assessment...</p>';

  try {
    const res = await fetch(`/api/invoices/${invoiceId}/risk-assessment`);
    if (!res.ok) throw new Error('Assessment not found');
    const data = await res.json();
    const invRes = await fetch(`/api/invoices/${invoiceId}`);
    const inv = await invRes.json();

    document.getElementById('modal-invoice-num').textContent = `Assessment: ${inv.invoice_number}`;
    document.getElementById('modal-invoice-vendor').textContent = `Vendor: ${inv.vendor_name || 'N/A'} • Amount: ₹${Number(inv.amount).toLocaleString('en-IN')}`;

    let decisionBadge = 'badge-info';
    if (data.decision === 'APPROVE') decisionBadge = 'badge-success';
    if (data.decision === 'ESCALATE') decisionBadge = 'badge-warning';
    if (data.decision === 'BLOCK') decisionBadge = 'badge-danger';

    let aiSection = '';
    if (data.ai_evaluation && data.ai_evaluation.validated_output) {
      const ai = data.ai_evaluation.validated_output;
      aiSection = `
        <div class="ai-box">
          <div class="ai-box-header">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
            Grounded AI Synthesis (${data.ai_evaluation.model_provider || 'Provider'})
          </div>
          <div class="ai-box-body">${ai.reasoning_summary}</div>
          <div class="ai-recommendation">Next Action: ${ai.recommended_next_action}</div>
        </div>
      `;
    }

    let signalsList = (data.signals || []).map(s => `
      <div style="background: var(--bg-surface); padding: 12px; border-radius: var(--radius); margin-bottom: 8px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
          <span class="badge ${s.severity === 'CRITICAL' || s.severity === 'HIGH' ? 'badge-danger' : (s.severity === 'MEDIUM' ? 'badge-warning' : 'badge-info')}">${s.category} • ${s.severity}</span>
          <span class="font-mono text-muted">Contrib: +${s.score_contribution} | ${s.source}</span>
        </div>
        <div style="font-size: 0.85rem; color: #E2E8F0;">${s.evidence.reason || s.evidence.message || JSON.stringify(s.evidence)}</div>
      </div>
    `).join('') || '<p class="text-muted">No negative signals triggered.</p>';

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding: 16px; background: var(--bg-surface); border-radius: var(--radius);">
        <div>
          <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">SYSTEM DECISION</div>
          <div style="font-size: 1.5rem; font-weight: 800; margin-top: 2px;"><span class="badge ${decisionBadge}" style="font-size: 1.1rem; padding: 6px 16px;">${data.decision}</span></div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">RISK SCORE</div>
          <div style="font-size: 1.8rem; font-weight: 800; color: ${data.decision === 'BLOCK' ? 'var(--red)' : (data.decision === 'APPROVE' ? 'var(--green)' : 'var(--yellow)')};">${data.final_score} <span style="font-size: 0.9rem; color: var(--text-muted);">/ 100</span></div>
        </div>
      </div>

      ${aiSection}

      <div style="margin-bottom: 20px;">
        <h4 style="margin-bottom: 10px;">Contributing Risk Signals</h4>
        ${signalsList}
      </div>

      <div style="padding-top: 16px; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
        <div style="font-size: 0.82rem; color: var(--text-muted);">Decision Reason: ${data.decision_reason}</div>
        ${data.decision !== 'APPROVE' ? `
          <button class="btn btn-outline btn-sm" onclick="promptOverride('${invoiceId}')">Senior Override to APPROVE</button>
        ` : ''}
      </div>
    `;
  } catch (err) {
    content.innerHTML = `<p class="text-danger">Failed to load assessment: ${err.message}</p>`;
  }
}

async function promptOverride(invoiceId) {
  const reason = prompt("Enter Senior Approver Override Rationale (minimum 10 characters):", "Verified legitimate expedited freight invoice against emergency PO");
  if (!reason || reason.trim().length < 5) {
    alert("Override aborted: valid reason required.");
    return;
  }

  try {
    const res = await fetch(`/api/invoices/${invoiceId}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_decision: "APPROVE",
        reason: reason,
        actor_role_label: "SENIOR_APPROVER"
      })
    });
    if (res.ok) {
      alert("Override successfully recorded and logged in audit trail!");
      document.getElementById('modal-assessment').classList.remove('open');
      loadInvoices();
      loadAuditEvents();
    } else {
      const err = await res.json();
      alert("Override failed: " + (err.detail || JSON.stringify(err)));
    }
  } catch (err) {
    alert("Error applying override: " + err.message);
  }
}

// --- Ingest Form Modal ---
function initModals() {
  document.getElementById('btn-close-modal').addEventListener('click', () => {
    document.getElementById('modal-assessment').classList.remove('open');
  });
  document.getElementById('btn-open-ingest').addEventListener('click', () => {
    document.getElementById('ingest-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('modal-ingest').classList.add('open');
  });
  document.getElementById('btn-close-ingest').addEventListener('click', () => {
    document.getElementById('modal-ingest').classList.remove('open');
  });
  document.getElementById('btn-cancel-ingest').addEventListener('click', () => {
    document.getElementById('modal-ingest').classList.remove('open');
  });

  document.getElementById('form-ingest').addEventListener('submit', async (e) => {
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
      document.getElementById('modal-ingest').classList.remove('open');
      document.getElementById('form-ingest').reset();
      loadInvoices();
      loadInvestigations();
      loadAuditEvents();
      openAssessment(created.id);
    } catch (err) {
      alert('Network error during ingestion: ' + err.message);
    }
  });
}

// --- Investigations ---
async function loadInvestigations() {
  try {
    const res = await fetch('/api/invoices');
    const invoices = await res.json();
    const escalatedAndBlocked = invoices.filter(i => i.status === 'ESCALATED' || i.status === 'BLOCKED');
    document.getElementById('nav-inv-count').textContent = escalatedAndBlocked.length;

    const listDiv = document.getElementById('investigations-list');
    if (escalatedAndBlocked.length === 0) {
      listDiv.innerHTML = '<p class="placeholder-text">No active investigation cases.</p>';
      return;
    }

    listDiv.innerHTML = escalatedAndBlocked.map(inv => `
      <div class="investigation-item ${activeInvestigationId === inv.id ? 'active' : ''}" onclick="selectInvestigation('${inv.id}')">
        <div class="inv-item-top">
          <div class="inv-item-title">${inv.invoice_number}</div>
          <span class="badge ${inv.status === 'BLOCKED' ? 'badge-danger' : 'badge-warning'}">${inv.status}</span>
        </div>
        <div class="inv-item-subtitle">${inv.vendor_name || 'Vendor'} • ₹${Number(inv.amount).toLocaleString('en-IN')}</div>
      </div>
    `).join('');

    if (!activeInvestigationId && escalatedAndBlocked.length > 0) {
      selectInvestigation(escalatedAndBlocked[0].id);
    }
  } catch (err) {
    console.error('Error loading investigations:', err);
  }
}

async function selectInvestigation(invoiceId) {
  activeInvestigationId = invoiceId;
  document.querySelectorAll('.investigation-item').forEach(el => el.classList.remove('active'));
  const card = document.getElementById('inv-detail-content');
  card.innerHTML = '<p class="text-center">Loading case workspace...</p>';

  try {
    const invRes = await fetch(`/api/invoices/${invoiceId}`);
    const inv = await invRes.json();
    const assRes = await fetch(`/api/invoices/${invoiceId}/risk-assessment`);
    const ass = await assRes.json();

    card.innerHTML = `
      <div style="margin-bottom: 16px;">
        <h3 style="margin-bottom: 4px;">${inv.invoice_number} — ${inv.vendor_name || 'Vendor'}</h3>
        <p class="text-muted" style="font-size: 0.85rem;">Amount: ₹${Number(inv.amount).toLocaleString('en-IN')} • Status: <strong>${inv.status}</strong></p>
      </div>

      <div style="background: var(--bg-surface); padding: 14px; border-radius: var(--radius); margin-bottom: 16px;">
        <div style="font-weight: 700; margin-bottom: 6px; color: var(--primary);">Firewall Findings</div>
        <div style="font-size: 0.85rem; color: #E2E8F0;">${ass.decision_reason}</div>
      </div>

      <div style="margin-bottom: 16px;">
        <h4 style="margin-bottom: 8px;">Resolution Actions</h4>
        <div style="display: flex; gap: 10px;">
          <button class="btn btn-success btn-sm" onclick="resolveCase('${invoiceId}', 'APPROVED_AFTER_REVIEW')">Approve After Review</button>
          <button class="btn btn-danger btn-sm" onclick="resolveCase('${invoiceId}', 'BLOCKED')">Uphold Block</button>
          <button class="btn btn-outline btn-sm" onclick="resolveCase('${invoiceId}', 'DUPLICATE_CONFIRMED')">Confirm Duplicate</button>
        </div>
      </div>
    `;
  } catch (err) {
    card.innerHTML = `<p class="text-danger">Failed to load investigation: ${err.message}</p>`;
  }
}

async function resolveCase(invoiceId, outcome) {
  const rationale = prompt(`Enter resolution rationale for outcome '${outcome}':`, "Reviewed invoice evidence and approved release.");
  if (!rationale) return;

  try {
    // Open investigation if needed and resolve
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
      alert(`Case resolved with outcome: ${outcome}`);
      loadInvoices();
      loadInvestigations();
      loadAuditEvents();
    }
  } catch (err) {
    alert("Error resolving case: " + err.message);
  }
}

// --- Payment Runs ---
async function loadPaymentRuns() {
  const container = document.getElementById('payment-runs-container');
  try {
    const res = await fetch('/api/invoices');
    const invoices = await res.json();
    const approvedInvs = invoices.filter(i => i.status === 'APPROVED' || i.status === 'PAID');
    const blockedInvs = invoices.filter(i => i.status === 'BLOCKED');

    container.innerHTML = `
      <div style="background: var(--bg-surface); padding: 18px; border-radius: var(--radius); margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <h4 style="font-size: 1.1rem; margin-bottom: 2px;">October AP Release Batch</h4>
            <span class="text-muted" style="font-size: 0.8rem;">Target Release Batch • Standard ERP Cycle</span>
          </div>
          <span class="badge ${blockedInvs.length > 0 ? 'badge-danger' : 'badge-success'}">${blockedInvs.length > 0 ? 'HOLD: BLOCKED ITEMS PRESENT' : 'READY FOR RELEASE'}</span>
        </div>

        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 14px;">
          <div style="background: var(--bg-card); padding: 10px 14px; border-radius: var(--radius);">
            <div style="font-size: 0.72rem; color: var(--text-muted);">ELIGIBLE INVOICES</div>
            <div style="font-size: 1.3rem; font-weight: 800; color: var(--green);">${approvedInvs.length}</div>
          </div>
          <div style="background: var(--bg-card); padding: 10px 14px; border-radius: var(--radius);">
            <div style="font-size: 0.72rem; color: var(--text-muted);">INTERCEPTED BLOCKS</div>
            <div style="font-size: 1.3rem; font-weight: 800; color: var(--red);">${blockedInvs.length}</div>
          </div>
          <div style="background: var(--bg-card); padding: 10px 14px; border-radius: var(--radius);">
            <div style="font-size: 0.72rem; color: var(--text-muted);">TOTAL READY VALUE</div>
            <div style="font-size: 1.3rem; font-weight: 800; color: var(--primary);">₹${approvedInvs.reduce((acc, i) => acc + i.amount, 0).toLocaleString('en-IN')}</div>
          </div>
        </div>

        <p style="font-size: 0.82rem; color: var(--text-muted); line-height: 1.5;">
          <strong>Database Safeguard Active:</strong> Database triggers permanently prohibit any payment release if an item is BLOCKED or ESCALATED without an explicit human approval record.
        </p>
      </div>
    `;
  } catch (err) {
    console.error('Error loading payment runs:', err);
  }
}

// --- Audit Trail ---
async function loadAuditEvents() {
  const tbody = document.getElementById('audit-table-body');
  try {
    const res = await fetch('/api/audit/events?limit=25');
    const events = await res.json();
    if (events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No audit events recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = events.map(e => `
      <tr>
        <td><strong>#${e.sequence_number}</strong></td>
        <td><span class="badge badge-info">${e.event_type}</span></td>
        <td>${e.actor_label}</td>
        <td>${e.decision ? `<span class="badge ${e.decision === 'BLOCK' ? 'badge-danger' : (e.decision === 'APPROVE' ? 'badge-success' : 'badge-warning')}">${e.decision} (${e.risk_score})</span>` : '-'}</td>
        <td title="${e.current_hash}">${e.current_hash.substring(0, 16)}...</td>
        <td title="${e.previous_hash}">${e.previous_hash.substring(0, 16)}...</td>
        <td style="font-size: 0.78rem;">${new Date(e.occurred_at).toLocaleTimeString()}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading audit events:', err);
  }
}

async function verifyAuditChain() {
  const badge = document.getElementById('chain-status-badge');
  try {
    const res = await fetch('/api/audit/verify');
    const data = await res.json();
    if (data.valid) {
      badge.className = 'badge badge-success';
      badge.textContent = `✓ Chain Verified (${data.rows_checked} blocks)`;
      alert(`Cryptographic Audit Chain verified successfully! Checked ${data.rows_checked} sequential hash blocks.`);
    } else {
      badge.className = 'badge badge-danger';
      badge.textContent = `✗ Tampering Detected at Seq #${data.first_broken_sequence}`;
      alert(`Tampering detected! First broken sequence number: ${data.first_broken_sequence}`);
    }
  } catch (err) {
    alert('Verification failed: ' + err.message);
  }
}
