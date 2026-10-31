const elements = {
  notice: document.querySelector('#notice'),
  createPanel: document.querySelector('#create-panel'),
  studio: document.querySelector('#studio'),
  createForm: document.querySelector('#create-form'),
  createButton: document.querySelector('#create-btn'),
  caseTitle: document.querySelector('#case-title'),
  caseDetail: document.querySelector('#case-detail'),
  version: document.querySelector('#version-text'),
  status: document.querySelector('#case-status'),
  terms: document.querySelector('#terms'),
  partySwitch: document.querySelector('#party-switch'),
  confirmations: document.querySelector('#approvals'),
  confirmButton: document.querySelector('#confirm'),
  messageForm: document.querySelector('#message-form'),
  analyzeButton: document.querySelector('#analyze-btn'),
  finding: document.querySelector('#finding'),
  proposals: document.querySelector('#proposals'),
  history: document.querySelector('#history'),
  historyToggle: document.querySelector('#history-toggle'),
  resetButton: document.querySelector('#reset'),
  analysisStatus: document.querySelector('#analysis-status'),
  previewDescription: document.querySelector('#preview-description'),
  viewDocument: document.querySelector('#view-document'),
  documentView: document.querySelector('#document-view'),
  documentBack: document.querySelector('#document-back'),
  documentVersion: document.querySelector('#document-version'),
  documentPrint: document.querySelector('#document-print'),
  documentState: document.querySelector('#document-state'),
  documentTitle: document.querySelector('#document-title'),
  documentSummary: document.querySelector('#document-summary'),
  documentMeta: document.querySelector('#document-meta'),
  documentTerms: document.querySelector('#document-terms'),
  documentSignoffs: document.querySelector('#document-signoffs')
};

const storageKey = 'samepage_local_demo';
const fieldNames = { price: 'Price', deadline: 'Deadline', scope: 'Scope of work' };
const eventNames = {
  case_created: 'Agreement created',
  initial_confirmed: 'Terms confirmed',
  change_proposed: 'Change suggested',
  proposal_approved_by_party: 'Change approved',
  proposal_rejected: 'Change declined',
  new_version_applied: 'Updated terms confirmed'
};

let savedAccess = null;
let agreement = null;
let selectedParty = 'a';
let showAllHistory = false;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function notify(message, isError = false) {
  elements.notice.textContent = message;
  elements.notice.className = `notice${isError ? ' error' : ''}`;
}

function clearNotice() {
  elements.notice.classList.add('hidden');
}

function readSavedAccess() {
  try { return JSON.parse(localStorage.getItem(storageKey) || 'null'); }
  catch { return null; }
}

function saveAccess() {
  localStorage.setItem(storageKey, JSON.stringify(savedAccess));
}

async function request(path, method = 'GET', payload) {
  const headers = { 'Content-Type': 'application/json' };
  const accessKey = savedAccess?.keys?.[selectedParty];
  if (accessKey) headers['X-Party-Key'] = accessKey;

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) })
  });
  let result;
  try { result = await response.json(); }
  catch { throw new Error('The server returned an unexpected response.'); }
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Something went wrong. Please try again.');
  return result;
}

function personName(party) {
  return party === 'a' ? agreement.party_a : agreement.party_b;
}

function approvalLabel(name, isConfirmed) {
  return `<span class="approval${isConfirmed ? ' confirmed' : ''}">${escapeHtml(name)}${isConfirmed ? ' confirmed' : ' pending'}</span>`;
}

function renderTerms() {
  const terms = agreement.terms;
  elements.terms.innerHTML = Object.entries(fieldNames).map(([key, label]) => `
    <div class="term">
      <span class="term-label">${label}</span>
      <div class="term-value">${escapeHtml(terms[key])}</div>
    </div>
  `).join('');

  elements.version.textContent = `Version ${agreement.version}`;
  elements.status.textContent = agreement.active ? 'Confirmed' : 'Awaiting confirmation';
  elements.status.className = `status-chip ${agreement.active ? 'status-confirmed' : 'status-pending'}`;
  elements.confirmations.innerHTML = approvalLabel(agreement.party_a, agreement.a_confirmed)
    + approvalLabel(agreement.party_b, agreement.b_confirmed);

  elements.partySwitch.innerHTML = `<option value="a">${escapeHtml(agreement.party_a)}</option><option value="b">${escapeHtml(agreement.party_b)}</option>`;
  elements.partySwitch.value = selectedParty;
  const hasConfirmed = selectedParty === 'a' ? agreement.a_confirmed : agreement.b_confirmed;
  elements.confirmButton.disabled = hasConfirmed;
  elements.confirmButton.textContent = hasConfirmed ? 'Already confirmed' : 'Confirm terms';
  elements.viewDocument.classList.toggle('hidden', !agreement.active);
  elements.analyzeButton.disabled = !agreement.active;
  elements.messageForm.elements.message.disabled = !agreement.active;
}

function renderChanges() {
  if (!agreement.proposals.length) {
    elements.proposals.innerHTML = '<div class="empty-state"><strong>Nothing to review yet</strong><p>When someone suggests a change, it will appear here.</p></div>';
    return;
  }

  elements.proposals.innerHTML = agreement.proposals.map(proposal => {
    const status = { pending: 'Awaiting approval', applied: 'Accepted', rejected: 'Declined' }[proposal.status] || proposal.status;
    const rows = proposal.changes.map(change => `
      <div class="change-line">
        <div class="change-label">${escapeHtml(fieldNames[change.field] || change.field)}</div>
        <div class="change-values">
          <span>${escapeHtml(change.old_value)}</span>
          <span aria-hidden="true">→</span>
          <strong>${escapeHtml(change.new_value)}</strong>
        </div>
        ${change.evidence ? `<div class="change-evidence">From: “${escapeHtml(change.evidence)}”</div>` : ''}
      </div>
    `).join('');
    const isApproved = selectedParty === 'a' ? proposal.a_approved : proposal.b_approved;
    const actions = proposal.status === 'pending' ? `
      <div class="change-actions">
        <button class="button button-primary" data-action="approve" data-id="${escapeHtml(proposal.id)}" ${isApproved ? 'disabled' : ''}>${isApproved ? 'Approved by you' : 'Approve change'}</button>
        <button class="button button-secondary" data-action="reject" data-id="${escapeHtml(proposal.id)}">Decline</button>
      </div>` : '';
    return `
      <article class="change-card">
        <div class="change-head">
          <strong>Suggested by ${escapeHtml(personName(proposal.author))}</strong>
          <span class="change-status ${escapeHtml(proposal.status)}">${escapeHtml(status)}</span>
        </div>
        <blockquote class="source-message">${escapeHtml(proposal.source_text)}</blockquote>
        ${rows}
        <div class="change-approvals">
          ${approvalLabel(agreement.party_a, proposal.a_approved)}
          ${approvalLabel(agreement.party_b, proposal.b_approved)}
        </div>
        ${actions}
      </article>`;
  }).join('');
}

function renderHistory() {
  const history = [...agreement.history].reverse();
  const visible = showAllHistory ? history : history.slice(0, 4);
  elements.history.innerHTML = visible.map(entry => {
    const party = entry.payload?.party ? ` · ${escapeHtml(personName(entry.payload.party))}` : '';
    const label = eventNames[entry.event] || 'Agreement updated';
    const timestamp = new Date(entry.created_at);
    const dateText = Number.isNaN(timestamp.getTime()) ? '' : timestamp.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
    return `<div class="activity"><span class="activity-dot" aria-hidden="true"></span><div><strong>${escapeHtml(label)}${party}</strong><time>${escapeHtml(dateText)}</time></div></div>`;
  }).join('');
  elements.historyToggle.classList.toggle('hidden', history.length <= 4);
  elements.historyToggle.textContent = showAllHistory ? 'Show less' : 'Show all activity';
}

function renderAgreement() {
  elements.createPanel.classList.add('hidden');
  elements.studio.classList.remove('hidden');
  elements.caseTitle.textContent = agreement.title;
  elements.caseDetail.textContent = `${agreement.party_a} and ${agreement.party_b}`;
  renderTerms();
  renderChanges();
  renderHistory();
  if (!agreement.audit_valid) notify('This agreement’s history could not be verified. Please do not rely on it until the issue is resolved.', true);
}

async function refreshAgreement() {
  agreement = await request(`/cases/${savedAccess.id}`);
  renderAgreement();
}

function showFinding(finding, created) {
  const title = created ? 'Changes ready for review' : finding.intent === 'ambiguous' || finding.intent === 'question'
    ? 'This needs clarification' : 'No confirmed changes identified';
  const summary = created
    ? finding.explanation || 'Review the proposed terms before anyone approves them. The current agreement has not changed.'
    : finding.explanation;
  elements.finding.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(summary)}</p>`;
  elements.finding.classList.remove('hidden');
}

elements.createForm.addEventListener('submit', async event => {
  event.preventDefault();
  elements.createButton.disabled = true;
  clearNotice();
  try {
    const values = Object.fromEntries(new FormData(elements.createForm).entries());
    const result = await request('/cases', 'POST', values);
    savedAccess = { id: result.case_id, keys: { a: result.party_a_key, b: result.party_b_key } };
    selectedParty = 'a';
    saveAccess();
    await refreshAgreement();
  } catch (error) {
    notify(error.message, true);
  } finally {
    elements.createButton.disabled = false;
  }
});

elements.partySwitch.addEventListener('change', async event => {
  selectedParty = event.target.value;
  clearNotice();
  try { await refreshAgreement(); }
  catch (error) { notify(error.message, true); }
});

elements.confirmButton.addEventListener('click', async () => {
  elements.confirmButton.disabled = true;
  clearNotice();
  try {
    agreement = await request(`/cases/${savedAccess.id}/confirm`, 'POST');
    renderAgreement();
  } catch (error) {
    notify(error.message, true);
    renderAgreement();
  }
});

elements.messageForm.addEventListener('submit', async event => {
  event.preventDefault();
  elements.analyzeButton.disabled = true;
  elements.finding.classList.add('hidden');
  clearNotice();
  try {
    const message = elements.messageForm.elements.message.value;
    const result = await request(`/cases/${savedAccess.id}/proposals`, 'POST', { message });
    if (result.proposal_created) {
      agreement = result.case;
      renderAgreement();
    }
    showFinding(result.finding, result.proposal_created);
  } catch (error) {
    notify(error.message, true);
  } finally {
    elements.analyzeButton.disabled = !agreement?.active;
  }
});

elements.proposals.addEventListener('click', async event => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  button.disabled = true;
  clearNotice();
  try {
    agreement = await request(`/cases/${savedAccess.id}/proposals/${button.dataset.id}/${button.dataset.action}`, 'POST');
    renderAgreement();
    elements.finding.classList.add('hidden');
  } catch (error) {
    notify(error.message, true);
    button.disabled = false;
  }
});

elements.historyToggle.addEventListener('click', () => {
  showAllHistory = !showAllHistory;
  renderHistory();
});


function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

async function loadDocument(version) {
  const documentRecord = await request(`/cases/${savedAccess.id}/documents/${version}`);
  elements.documentTitle.textContent = documentRecord.title;
  elements.documentState.textContent = documentRecord.current ? 'Current agreement' : 'Previous version';
  elements.documentSummary.textContent = `${documentRecord.party_a} and ${documentRecord.party_b}`;
  const items = [
    ['Agreement reference', documentRecord.case_id],
    ['Version', documentRecord.version],
    ['Confirmed', formatDate(documentRecord.approved_at)]
  ];
  elements.documentMeta.innerHTML = items.map(([label, value]) => `
    <div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>
  `).join('');
  elements.documentTerms.innerHTML = Object.entries(fieldNames).map(([key, label]) => `
    <div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(documentRecord.terms[key] || '')}</dd></div>
  `).join('');
  elements.documentSignoffs.innerHTML = ['a', 'b'].map(party => {
    const name = party === 'a' ? documentRecord.party_a : documentRecord.party_b;
    const approved = documentRecord.approvals[party];
    return `<div class="paper-signoff"><strong>${escapeHtml(name)}</strong><span>Confirmed ${escapeHtml(formatDate(approved))}</span></div>`;
  }).join('');
  elements.documentVersion.value = String(documentRecord.version);
}

async function openDocument() {
  try {
    clearNotice();
    const versions = await request(`/cases/${savedAccess.id}/documents`);
    elements.documentVersion.innerHTML = versions.map(entry => `
      <option value="${entry.version}">Version ${entry.version}${entry.current ? ' · Current' : ''}</option>
    `).join('');
    await loadDocument(versions[versions.length - 1].version);
    elements.studio.classList.add('hidden');
    elements.documentView.classList.remove('hidden');
    window.scrollTo(0, 0);
  } catch (error) {
    notify(error.message, true);
  }
}

elements.viewDocument.addEventListener('click', openDocument);
elements.documentBack.addEventListener('click', () => {
  elements.documentView.classList.add('hidden');
  elements.studio.classList.remove('hidden');
  window.scrollTo(0, 0);
});
elements.documentVersion.addEventListener('change', async () => {
  try { await loadDocument(Number(elements.documentVersion.value)); }
  catch (error) { notify(error.message, true); }
});
elements.documentPrint.addEventListener('click', () => window.print());

elements.resetButton.addEventListener('click', () => {
  if (!window.confirm('Start a new agreement? This browser will stop showing the current one.')) return;
  localStorage.removeItem(storageKey);
  savedAccess = null;
  agreement = null;
  selectedParty = 'a';
  showAllHistory = false;
  elements.studio.classList.add('hidden');
  elements.createPanel.classList.remove('hidden');
  elements.finding.classList.add('hidden');
  clearNotice();
});

async function initialize() {
  try {
    const health = await request('/health');
    const usingMeta = health.mode === 'meta_muse_spark_1_3';
    elements.analysisStatus.textContent = usingMeta ? 'Meta AI enabled' : 'Local preview';
    elements.previewDescription.textContent = usingMeta
      ? 'This workspace uses Meta Muse Spark to review new messages. Model output is checked before any proposed changes are saved. API usage may incur charges.'
      : 'This is a local demonstration. Both participants are simulated in this browser. Message checking uses a limited pattern detector, not AI. Please use sample data.';
    savedAccess = readSavedAccess();
    if (savedAccess) {
      try { await refreshAgreement(); }
      catch { localStorage.removeItem(storageKey); savedAccess = null; }
    }
  } catch (error) {
    notify(`Unable to connect to the local server: ${error.message}`, true);
  }
}

initialize();
