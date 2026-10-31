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
  documentSignoffs: document.querySelector('#document-signoffs'),
  documentDelivery: document.querySelector('#document-delivery'),
  stageSummary: document.querySelector('#stage-summary'),
  invitation: document.querySelector('#invitation'),
  copyInvitation: document.querySelector('#copy-invitation'),
  partySelector: document.querySelector('#party-selector'),
  accessRole: document.querySelector('#access-role'),
  confirmationHelp: document.querySelector('#confirmation-help'),
  declineButton: document.querySelector('#decline'),
  declinePanel: document.querySelector('#decline-panel'),
  declineForm: document.querySelector('#decline-form'),
  counterPanel: document.querySelector('#counter-panel'),
  counterForm: document.querySelector('#counter-form'),
  manualPanel: document.querySelector('#manual-panel'),
  manualForm: document.querySelector('#manual-form'),
  completionPanel: document.querySelector('#completion-panel'),
  completionContent: document.querySelector('#completion-content'),
  deliveryHelp: document.querySelector('#delivery-help')
};

const storageKey = 'samepage_local_demo';
const fieldNames = { price: 'Price', deadline: 'Deadline', scope: 'Scope of work' };
const eventNames = {
  case_created: 'Agreement created',
  initial_confirmed: 'Terms confirmed',
  change_proposed: 'Change suggested',
  proposal_approved_by_party: 'Change approved',
  proposal_rejected: 'Change declined',
  new_version_applied: 'Updated terms confirmed',
  offer_declined: 'Offer declined',
  counteroffer_sent: 'Counteroffer sent',
  delivery_submitted: 'Delivery submitted',
  delivery_accepted: 'Delivery accepted',
  delivery_disputed: 'Delivery disputed',
  delivery_resubmitted: 'Delivery resubmitted' 
};

let savedAccess = null;
let agreement = null;
let selectedParty = 'a';
let showAllHistory = false;
let invitationLink = null;

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

const statusLabels = {
  awaiting_recipient: 'Awaiting recipient',
  awaiting_initiator: 'Review counteroffer',
  declined: 'Declined',
  in_progress: 'In progress',
  awaiting_completion_review: 'Review delivery',
  completed: 'Completed',
  disputed: 'Delivery disputed'
};

function setFormTerms(form, values) {
  if (!form || !values) return;
  for (const name of ['price', 'deadline', 'scope']) {
    if (form.elements[name]) form.elements[name].value = values[name] || '';
  }
}

function renderTerms() {
  const terms = agreement.terms;
  elements.terms.innerHTML = Object.entries(fieldNames).map(([key, label]) => `
    <div class="term"><span class="term-label">${label}</span><div class="term-value">${escapeHtml(terms[key])}</div></div>
  `).join('');

  elements.version.textContent = agreement.version === 1 ? 'Original agreement' : `Revised ${agreement.version - 1} time${agreement.version > 2 ? 's' : ''}`;
  elements.status.textContent = statusLabels[agreement.status] || 'Pending';
  elements.status.className = `status-chip ${agreement.active && agreement.status !== 'disputed' ? 'status-confirmed' : 'status-pending'}`;
  elements.confirmations.innerHTML = approvalLabel(`${agreement.party_a} · Initiator`, agreement.a_confirmed)
    + approvalLabel(`${agreement.party_b} · Recipient`, agreement.b_confirmed);
  elements.partySwitch.innerHTML = `<option value="a">${escapeHtml(agreement.party_a)}</option><option value="b">${escapeHtml(agreement.party_b)}</option>`;
  elements.partySwitch.value = selectedParty;
  const localSwitcher = Boolean(savedAccess?.keys?.a && savedAccess?.keys?.b);
  elements.partySelector.classList.toggle('hidden', !localSwitcher);
  elements.accessRole.classList.toggle('hidden', localSwitcher);
  elements.accessRole.textContent = `Accessing as ${personName(selectedParty)} · ${selectedParty === 'a' ? 'Initiator' : 'Recipient'}`;
  elements.invitation.classList.toggle('hidden', !invitationLink || agreement.status !== 'awaiting_recipient');

  const needsConfirmation = !agreement.active && agreement.status !== 'declined';
  const hasApproved = selectedParty === 'a' ? agreement.a_confirmed : agreement.b_confirmed;
  elements.confirmButton.classList.toggle('hidden', !needsConfirmation);
  elements.confirmButton.disabled = hasApproved || !needsConfirmation;
  elements.confirmButton.textContent = selectedParty === 'a' ? 'Accept counteroffer' : 'Accept agreement';
  elements.declineButton.classList.toggle('hidden', !(agreement.status === 'awaiting_recipient' && selectedParty === 'b'));
  if (agreement.status !== 'awaiting_recipient') elements.declinePanel.classList.add('hidden');
  elements.counterPanel.classList.toggle('hidden', !(agreement.status === 'awaiting_recipient' && selectedParty === 'b'));
  if (!elements.counterPanel.open) setFormTerms(elements.counterForm, terms);
  setFormTerms(elements.manualForm, terms);
  elements.viewDocument.classList.toggle('hidden', !agreement.active);

  const editable = agreement.status === 'in_progress';
  elements.analyzeButton.disabled = !editable;
  elements.messageForm.elements.message.disabled = !editable;
  elements.manualPanel.classList.toggle('hidden', !editable);
  elements.confirmationHelp.textContent = agreement.status === 'awaiting_recipient'
    ? `${agreement.party_a} initiated this agreement. ${agreement.party_b} can accept, decline, or suggest different terms.`
    : agreement.status === 'awaiting_initiator'
      ? `${agreement.party_b} proposed different terms. ${agreement.party_a} must review and approve before the agreement takes effect.`
      : agreement.status === 'declined'
        ? 'The recipient declined this offer. The terms were never activated.'
        : 'Both participants accepted the terms. Proposed amendments require fresh approval.';

  const stageText = {
    awaiting_recipient: `<strong>Waiting for ${escapeHtml(agreement.party_b)}</strong><span>The initial offer was made by ${escapeHtml(agreement.party_a)}. It is not yet binding within SamePage.</span>`,
    awaiting_initiator: `<strong>Counteroffer awaiting ${escapeHtml(agreement.party_a)}</strong><span>The recipient suggested different terms. Nothing is active until the initiator accepts.</span>`,
    declined: '<strong>Offer declined</strong><span>No active agreement was created.</span>',
    in_progress: '<strong>Agreement accepted</strong><span>Track delivery, review changes and keep a record of decisions.</span>',
    awaiting_completion_review: '<strong>Delivery awaiting review</strong><span>The other participant needs to confirm whether the promised work was delivered.</span>',
    completed: '<strong>Completed</strong><span>Delivery was accepted. The agreement and its history remain available.</span>',
    disputed: '<strong>Delivery disputed</strong><span>The recorded completion has been challenged. The dispute remains unresolved.</span>'
  };
  elements.stageSummary.innerHTML = stageText[agreement.status] || '';
  elements.caseDetail.textContent = `Initiated by ${agreement.party_a} · Sent to ${agreement.party_b}`;
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
    const actions = proposal.status === 'pending' && agreement.status === 'in_progress' ? `
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

function renderCompletion() {
  const delivery = agreement.completion;
  const responsible = agreement.responsible_party;
  const provider = personName(responsible);
  const reviewer = personName(responsible === 'a' ? 'b' : 'a');
  elements.completionPanel.classList.toggle('hidden', !agreement.active);
  elements.deliveryHelp.textContent = `${provider} is responsible for delivery. ${reviewer} reviews the result.`;
  if (!agreement.active) return;
  if (!delivery && agreement.status === 'in_progress') {
    elements.completionContent.innerHTML = selectedParty === responsible ? `
      <form id="delivery-form" class="nested-form">
        <label for="delivery-statement">What was delivered?</label>
        <textarea id="delivery-statement" name="statement" rows="3" required minlength="6" maxlength="1500" placeholder="Describe the work or items delivered"></textarea>
        <label for="delivery-reference">Evidence reference (optional)</label>
        <input id="delivery-reference" name="reference" maxlength="300" placeholder="Receipt number, photo reference or document name">
        <div class="form-actions"><button class="button button-primary" type="submit">Submit for acceptance</button></div>
      </form>` : `<p class="muted-copy">Waiting for ${escapeHtml(provider)} to submit the work for your review.</p>`;
    return;
  }
  if (!delivery) {
    elements.completionContent.innerHTML = '<p class="muted-copy">Resolve pending changes before submitting delivery.</p>';
    return;
  }
  const evidence = delivery.reference ? `<p class="muted-copy">Reference: ${escapeHtml(delivery.reference)}</p>` : '';
  const detail = `<div class="delivery-record"><strong>Reported by ${escapeHtml(provider)}</strong><p>${escapeHtml(delivery.statement)}</p>${evidence}</div>`;
  if (delivery.status === 'submitted') {
    elements.completionContent.innerHTML = detail + (selectedParty !== responsible ? `
      <div class="change-actions"><button class="button button-primary" data-delivery="accept">Accept delivery</button><button class="button button-secondary" data-delivery="dispute">Report a problem</button></div>
      <form id="dispute-form" class="nested-form hidden"><label for="dispute-reason">What needs attention?</label><textarea id="dispute-reason" name="note" rows="3" required maxlength="1000"></textarea><div class="form-actions"><button class="button button-secondary" type="submit">Send dispute</button></div></form>`
      : `<p class="muted-copy">Waiting for ${escapeHtml(reviewer)} to review the delivery.</p>`);
  } else {
    const canResubmit = delivery.status === 'disputed' && selectedParty === responsible;
    const newSubmission = canResubmit ? `<form id="resubmit-form" class="nested-form">
      <label for="resubmit-statement">How was the issue addressed?</label><textarea id="resubmit-statement" name="statement" rows="3" minlength="6" maxlength="1500" required></textarea>
      <label for="resubmit-reference">New evidence reference (optional)</label><input id="resubmit-reference" name="reference" maxlength="300">
      <div class="form-actions"><button class="button button-primary" type="submit">Resubmit for review</button></div>
    </form>` : '';
    elements.completionContent.innerHTML = detail + `<p class="delivery-outcome">${delivery.status === 'accepted' ? 'Delivery accepted' : 'Delivery disputed'} by ${escapeHtml(reviewer)}</p>${delivery.review_note ? `<p class="muted-copy">${escapeHtml(delivery.review_note)}</p>` : ''}${newSubmission}`;
  }
}

function renderAgreement() {
  elements.createPanel.classList.add('hidden');
  elements.studio.classList.remove('hidden');
  elements.caseTitle.textContent = agreement.title;
  elements.caseDetail.textContent = `${agreement.party_a} and ${agreement.party_b}`;
  renderTerms();
  renderChanges();
  renderHistory();
  renderCompletion();
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
    savedAccess = { id: result.case_id, keys: { a: result.party_a_key } };
    selectedParty = 'a';
    const params = new URLSearchParams({ case: result.case_id, key: result.party_b_key, role: 'b' });
    invitationLink = `${window.location.origin}${window.location.pathname}#${params.toString()}`;
    saveAccess();
    await refreshAgreement();
  } catch (error) {
    notify(error.message, true);
  } finally {
    elements.createButton.disabled = false;
  }
});

elements.copyInvitation.addEventListener('click', async () => {
  if (!invitationLink) return;
  try {
    await navigator.clipboard.writeText(invitationLink);
    notify('Invitation link copied. Share it privately with the recipient.');
  } catch {
    window.prompt('Copy the private invitation URL:', invitationLink);
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

elements.declineButton.addEventListener('click', async () => {
  elements.declinePanel.classList.toggle('hidden');
});

elements.declineForm.addEventListener('submit', async event => {
  event.preventDefault();
  const message = elements.declineForm.elements.message.value.trim();
  try {
    agreement = await request(`/cases/${savedAccess.id}/decline`, 'POST', {message});
    renderAgreement();
  } catch (error) { notify(error.message, true); }
});

elements.counterForm.addEventListener('submit', async event => {
  event.preventDefault();
  clearNotice();
  const payload = Object.fromEntries(new FormData(elements.counterForm).entries());
  try {
    agreement = await request(`/cases/${savedAccess.id}/counter`, 'POST', payload);
    elements.counterPanel.open = false;
    renderAgreement();
  } catch (error) { notify(error.message, true); }
});

elements.manualForm.addEventListener('submit', async event => {
  event.preventDefault();
  clearNotice();
  const payload = Object.fromEntries(new FormData(elements.manualForm).entries());
  if (!window.confirm('Send these proposed terms to the other participant for approval?')) return;
  try {
    agreement = await request(`/cases/${savedAccess.id}/manual-proposals`, 'POST', payload);
    elements.manualPanel.open = false;
    renderAgreement();
    notify('Proposed terms sent. The current agreement stays unchanged until accepted.');
  } catch (error) { notify(error.message, true); }
});

elements.completionContent.addEventListener('submit', async event => {
  if (event.target.id === 'dispute-form') {
    event.preventDefault();
    try {
      agreement = await request(`/cases/${savedAccess.id}/completion/review`, 'POST', {accepted: false, note: event.target.elements.note.value.trim()});
      renderAgreement();
    } catch (error) { notify(error.message, true); }
    return;
  }
  if (!['delivery-form','resubmit-form'].includes(event.target.id)) return;
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.target).entries());
  const endpoint = event.target.id === 'resubmit-form' ? '/completion/resubmit' : '/completion';
  try {
    agreement = await request(`/cases/${savedAccess.id}${endpoint}`, 'POST', payload);
    renderAgreement();
    notify('Delivery sent for the other participant to review.');
  } catch (error) { notify(error.message, true); }
});

elements.completionContent.addEventListener('click', async event => {
  const action = event.target.closest('button[data-delivery]')?.dataset.delivery;
  if (!action) return;
  if (action === 'dispute') {
    elements.completionContent.querySelector('#dispute-form')?.classList.toggle('hidden');
    return;
  }
  if (!window.confirm('Confirm that the agreed work has been delivered?')) return;
  try {
    agreement = await request(`/cases/${savedAccess.id}/completion/review`, 'POST', {accepted: true, note: ''});
    renderAgreement();
  } catch (error) { notify(error.message, true); }
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
  elements.documentState.textContent = documentRecord.current ? 'Current agreement' : 'Earlier accepted terms';
  elements.documentSummary.textContent = `${documentRecord.party_a} and ${documentRecord.party_b}`;
  const items = [
    ['Agreement reference', documentRecord.case_id],
    ['Record', documentRecord.version === 1 ? 'Original agreement' : `Revision ${documentRecord.version - 1}`],
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
    const role = party === 'a' ? 'Initiator' : 'Recipient';
    return `<div class="paper-signoff"><strong>${escapeHtml(name)}</strong><span>${role} · Accepted ${escapeHtml(formatDate(approved))}</span></div>`;
  }).join('');
  const delivery = agreement?.completion;
  elements.documentDelivery.innerHTML = documentRecord.current && delivery
    ? `<h2>Delivery record</h2><p>${escapeHtml(delivery.statement)}</p><p class="muted-copy">Status: ${escapeHtml(delivery.status)}${delivery.review_note ? ` · ${escapeHtml(delivery.review_note)}` : ''}</p>` : '';
  elements.documentVersion.value = String(documentRecord.version);
}

async function openDocument() {
  try {
    clearNotice();
    const versions = await request(`/cases/${savedAccess.id}/documents`);
    elements.documentVersion.innerHTML = versions.map(entry => `
      <option value="${entry.version}">${entry.version === 1 ? 'Original agreement' : `Revised agreement ${entry.version - 1}`}${entry.current ? ' · Current' : ''}</option>
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
  invitationLink = null;
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
    elements.analysisStatus.textContent = 'About';
    elements.previewDescription.textContent = usingMeta
      ? 'This workspace uses Meta Muse Spark to review new messages. Model output is checked before any proposed changes are saved. API usage may incur charges.'
      : 'Local development preview. Message analysis runs in offline demonstration mode, and invitation links work only on this running server.';
    const params = new URLSearchParams(window.location.hash.slice(1));
    if (params.get('case') && params.get('key') && ['a', 'b'].includes(params.get('role'))) {
      const role = params.get('role');
      savedAccess = { id: params.get('case'), keys: { [role]: params.get('key') } };
      selectedParty = role;
      saveAccess();
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    } else {
      savedAccess = readSavedAccess();
      selectedParty = savedAccess?.keys?.a ? 'a' : 'b';
    }
    if (savedAccess) {
      try { await refreshAgreement(); }
      catch { localStorage.removeItem(storageKey); savedAccess = null; }
    }
  } catch (error) {
    notify(`Unable to connect to the local server: ${error.message}`, true);
  }
}

initialize();
