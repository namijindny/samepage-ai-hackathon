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
  termsTitle: document.querySelector('#terms-title'),
  offerReview: document.querySelector('#offer-review'),
  understandingPanel: document.querySelector('#understanding-panel'),
  understandingRequest: document.querySelector('#understanding-request'),
  understandingForm: document.querySelector('#understanding-form'),
  understandingEdit: document.querySelector('#understanding-edit'),
  understandingUseOffer: document.querySelector('#understanding-use-offer'),
  understandingProgress: document.querySelector('#understanding-progress'),
  understandingResult: document.querySelector('#understanding-result'),
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
  deliveryHelp: document.querySelector('#delivery-help'),
  conversationMessages: document.querySelector('#conversation-messages'),
  conversationForm: document.querySelector('#conversation-form'),
  conversationReview: document.querySelector('#conversation-review-button'),
  conversationHint: document.querySelector('#conversation-review-hint'),
  conversationFeedback: document.querySelector('#conversation-review-feedback'),
  conversationResult: document.querySelector('#conversation-result')
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
  delivery_resubmitted: 'Delivery resubmitted',
  delivery_plan_proposed: 'Delivery checklist proposed',
  delivery_plan_approved: 'Delivery checklist approved',
  delivery_plan_rejected: 'Delivery checklist changes requested',
  deliverable_submitted: 'Deliverable submitted',
  deliverable_resubmitted: 'Deliverable resubmitted',
  deliverable_disputed: 'Deliverable correction requested',
  deliverable_accepted: 'Deliverable accepted',
  evidence_ai_reviewed: 'Evidence checked with AI',
  delivery_completed: 'All deliverables accepted',
  understanding_requested: 'Understanding check requested',
  understanding_submitted: 'Understanding shared',
  understanding_aligned: 'Terms understood by both' 
};

let savedAccess = null;
let agreement = null;
let selectedParty = 'a';
let showAllHistory = false;
let invitationLink = null;
let editUnderstanding = false;
let understandingRevision = null;
let conversationReviewPending = false;
let evidenceObjectUrls = [];
let evidenceReviewPendingId = null;

async function encodeScreenshot(file) {
  if (file.size > 2000000) throw new Error('Each screenshot must be smaller than 2 MB.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 32768) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
  }
  return {name: file.name, data: btoa(binary)};
}

async function displayEvidenceImages() {
  evidenceObjectUrls.forEach(url => URL.revokeObjectURL(url));
  evidenceObjectUrls = [];
  const accessKey = savedAccess?.keys?.[selectedParty];
  if (!accessKey) return;
  for (const img of elements.completionContent.querySelectorAll('img[data-evidence]')) {
    const response = await fetch(`/api/cases/${encodeURIComponent(savedAccess.id)}/evidence/${encodeURIComponent(img.dataset.evidence)}`, {
      headers: {'X-Party-Key': accessKey}, cache: 'no-store'
    }).catch(() => null);
    if (!response?.ok || !img.isConnected) continue;
    const url = URL.createObjectURL(await response.blob());
    evidenceObjectUrls.push(url);
    if (img.isConnected) img.src = url;
  }
}

function imageGallery(items, old = false) {
  if (!items?.length) return '';
  const images = items.map(image => `<img loading="lazy" data-evidence="${escapeHtml(image.id)}" alt="${escapeHtml(image.name)}">`).join('');
  const gallery = `<div class="evidence-gallery${old ? ' earlier' : ''}">${images}</div>`;
  return old ? `<details class="earlier-evidence"><summary>Previous screenshots</summary>${gallery}</details>` : gallery;
}


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
  try {
    return JSON.parse(sessionStorage.getItem(storageKey) || localStorage.getItem(storageKey) || 'null');
  } catch {
    return null;
  }
}

function saveAccess() {
  sessionStorage.setItem(storageKey, JSON.stringify(savedAccess));
  const previous = localStorage.getItem(storageKey);
  if (selectedParty === 'a' || !previous) localStorage.setItem(storageKey, JSON.stringify(savedAccess));
}

async function request(path, method = 'GET', payload, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  const accessKey = savedAccess?.keys?.[selectedParty];
  if (accessKey) headers['X-Party-Key'] = accessKey;

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    ...(options.signal ? {signal: options.signal} : {}),
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
  awaiting_initiator: 'Waiting for initiator',
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

function understandingStatus(check) {
  if (!check?.requested) return null;
  const other = selectedParty === 'a' ? 'b' : 'a';
  if (check.state === 'awaiting_you') {
    return `${personName(other)} has ${check.submitted[other] ? 'submitted a response' : 'not yet submitted'}. Your understanding is needed before approval.`;
  }
  if (check.state === 'awaiting_other') {
    return `Your response is saved. Waiting for ${personName(other)} to submit their understanding from their own invitation.`;
  }
  if (check.state === 'differences') {
    return 'Both responses are in, but some details differ from the proposed agreement. Review the differences below.';
  }
  return 'Both people understand the proposed terms. The person reviewing the offer may now accept it.';
}

function renderUnderstanding() {
  const pending = ['awaiting_recipient', 'awaiting_initiator'].includes(agreement.status);
  const check = agreement.understanding;
  elements.understandingPanel.classList.toggle('hidden', !pending);
  if (!pending || !check) return;
  if (understandingRevision !== check.revision) {
    understandingRevision = check.revision;
    editUnderstanding = false;
    delete elements.understandingForm.dataset.dirty;
  }
  const submitted = check.submitted[selectedParty];
  const editing = check.requested && !check.ready && (!submitted || check.state === 'differences' || editUnderstanding);
  elements.understandingRequest.classList.toggle('hidden', check.requested);
  elements.understandingProgress.classList.toggle('hidden', !check.requested);
  elements.understandingForm.classList.toggle('hidden', !editing);
  elements.understandingEdit.classList.toggle('hidden', !check.requested || !submitted || check.ready || editing);
  elements.understandingResult.classList.add('hidden');
  if (!check.requested) return;
  elements.understandingProgress.textContent = understandingStatus(check);
  if (!elements.understandingForm.dataset.dirty) {
    setFormTerms(elements.understandingForm, check.mine || {price: '', deadline: '', scope: ''});
  }
  if (check.state === 'aligned') {
    elements.understandingResult.classList.remove('hidden');
    elements.understandingResult.innerHTML = '<strong>Understanding confirmed</strong><p>You can now respond to the offer. Its terms will remain unchanged until you explicitly accept.</p>';
    return;
  }
  if (check.state !== 'differences') return;
  const differences = check.checks.filter(item => !item.matches);
  const differencesHtml = differences.map(item => `
    <div class="understanding-difference">
      <strong>${escapeHtml(fieldNames[item.field])}</strong>
      <p>Proposed terms: ${escapeHtml(item.agreed)}</p>
      <p>${escapeHtml(agreement.party_a)}: ${escapeHtml(item.a)}${item.a_matches_offer ? ' ✓' : ' — different'}</p>
      <p>${escapeHtml(agreement.party_b)}: ${escapeHtml(item.b)}${item.b_matches_offer ? ' ✓' : ' — different'}</p>
    </div>`).join('');
  elements.understandingResult.classList.remove('hidden');
  elements.understandingResult.innerHTML = `<strong>${differences.length} detail${differences.length === 1 ? '' : 's'} need clarification</strong>
    <p>The wording must match the offer for this preliminary check. If the intended scope is different, request a counteroffer that states the actual work clearly. Different paraphrases are not automatically considered equivalent.</p>${differencesHtml}`;
}

function renderTerms() {
  const terms = agreement.terms;
  const awaitingReview = ['awaiting_recipient', 'awaiting_initiator'].includes(agreement.status);
  const reviewer = agreement.offer_by === 'a' ? 'b' : 'a';
  const isReviewer = awaitingReview && selectedParty === reviewer;
  const offererName = personName(agreement.offer_by);
  const reviewerName = personName(reviewer);
  const canAct = isReviewer && !agreement[`${selectedParty}_confirmed`];

  elements.termsTitle.textContent = awaitingReview ? 'Proposed terms' : 'Agreed terms';
  elements.terms.innerHTML = Object.entries(fieldNames).map(([key, label]) => `
    <div class="term"><span class="term-label">${label}</span><div class="term-value">${escapeHtml(terms[key])}</div></div>
  `).join('');

  elements.version.textContent = awaitingReview
    ? (agreement.offer_revision ? `Counteroffer ${agreement.offer_revision}` : 'Initial offer')
    : (agreement.version === 1 ? 'Original agreement' : `Amendment ${agreement.version - 1}`);
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
  elements.invitation.classList.toggle('hidden', !invitationLink || !awaitingReview || agreement.offer_by !== 'a');

  elements.confirmButton.classList.toggle('hidden', !canAct);
  elements.confirmButton.disabled = !canAct || (agreement.understanding?.requested && !agreement.understanding.ready);
  elements.confirmButton.textContent = agreement.offer_revision ? 'Accept counteroffer' : 'Accept agreement';
  elements.declineButton.classList.toggle('hidden', !canAct);
  if (!canAct) elements.declinePanel.classList.add('hidden');
  elements.counterPanel.classList.toggle('hidden', !canAct);
  if (!elements.counterPanel.open) setFormTerms(elements.counterForm, terms);
  if (!elements.manualPanel.open) setFormTerms(elements.manualForm, terms);
  elements.viewDocument.classList.toggle('hidden', !agreement.active);

  const showChanges = awaitingReview && agreement.offer_revision > 0;
  elements.offerReview.classList.toggle('hidden', !showChanges);
  if (showChanges) {
    const changes = agreement.offer_changes.map(change => `
      <div class="offer-difference"><span>${escapeHtml(fieldNames[change.field] || change.field)}</span>
        <div><del>${escapeHtml(change.old_value)}</del><span aria-hidden="true">→</span><strong>${escapeHtml(change.new_value)}</strong></div>
      </div>`).join('');
    elements.offerReview.innerHTML = `<strong>Changes suggested by ${escapeHtml(offererName)}</strong>${changes}
      ${agreement.offer_note ? `<p>${escapeHtml(agreement.offer_note)}</p>` : ''}`;
  }

  const editable = agreement.status === 'in_progress' && !['pending','active'].includes(agreement.delivery_plan?.status);
  elements.analyzeButton.disabled = !editable;
  elements.messageForm.elements.message.disabled = !editable;
  elements.manualPanel.classList.toggle('hidden', !editable);
  elements.confirmationHelp.textContent = awaitingReview && agreement.understanding?.requested && !agreement.understanding.ready
    ? understandingStatus(agreement.understanding)
    : canAct
    ? `Review the latest terms from ${offererName}. You can accept, suggest another change, or decline.`
    : awaitingReview
      ? `Your offer has been sent to ${reviewerName}. You'll see their response here automatically.`
      : agreement.status === 'declined'
        ? 'This offer was declined. No agreement was activated.'
        : 'Both participants approved these terms. Later changes require fresh approval.';

  const person = personName(selectedParty);
  const responsible = personName(agreement.responsible_party);
  const other = personName(agreement.responsible_party === 'a' ? 'b' : 'a');
  const messages = {
    declined: ['Offer declined', 'No active agreement was created. You can start a new agreement whenever you need.'],
    in_progress: agreement.delivery_plan?.status === 'pending'
      ? ['Checklist awaiting approval', `Review the proposed delivery criteria before tracking completed work.`]
      : agreement.delivery_plan?.status === 'active'
        ? ['Delivery in progress', `Track each approved deliverable and its review in the Delivery section.`]
        : ['Agreement accepted', 'Agree on a delivery checklist so both participants know exactly what counts as complete.'],
    awaiting_completion_review: selectedParty === agreement.responsible_party
      ? ['Delivery submitted', `Waiting for ${other} to accept the work or report a problem.`]
      : ['Delivery ready for review', `Check the work submitted by ${responsible} and accept it or report an issue.`],
    completed: ['Agreement completed', 'The work was accepted. You can view and print the approved agreement.'],
    disputed: selectedParty === agreement.responsible_party
      ? ['Delivery needs attention', 'Review the reported problem, then submit the corrected work.']
      : ['Problem reported', `Waiting for ${responsible} to address your feedback and resubmit the work.`]
  };
  const waitingForUnderstanding = awaitingReview && agreement.understanding?.requested && !agreement.understanding.ready;
  const [headline, detail] = waitingForUnderstanding
    ? [agreement.understanding.state === 'awaiting_other' ? `Waiting for ${personName(selectedParty === 'a' ? 'b' : 'a')}` : 'Understanding needs review', understandingStatus(agreement.understanding)]
    : awaitingReview
    ? (canAct ? ['Your response is needed', `Review ${offererName}'s ${agreement.offer_revision ? 'counteroffer' : 'offer'} and choose how to proceed.`]
      : ['Waiting for a response', `${reviewerName} is reviewing your ${agreement.offer_revision ? 'counteroffer' : 'offer'}. This page updates automatically.`])
    : (messages[agreement.status] || ['Agreement updated', 'See the current agreement details below.']);
  const role = selectedParty === 'a' ? 'Initiator' : 'Recipient';
  const needsUnderstanding = awaitingReview && agreement.understanding?.requested && !agreement.understanding.ready;
  let action = '';
  if (canAct) {
    const changes = agreement.offer_changes.map(change => `<div class="review-change">
      <span>${escapeHtml(fieldNames[change.field] || change.field)}</span>
      <span><del>${escapeHtml(change.old_value)}</del> → <strong>${escapeHtml(change.new_value)}</strong></span>
    </div>`).join('');
    const summary = Object.entries(fieldNames).map(([field, label]) => `<div class="review-term">
      <span>${escapeHtml(label)}</span><strong>${escapeHtml(agreement.terms[field])}</strong>
    </div>`).join('');
    const blocked = agreement.understanding?.requested && !agreement.understanding.ready;
    action = `<details class="response-review" id="response-review">
      <summary>Review ${agreement.offer_revision ? 'counteroffer' : 'offer'}</summary>
      <div class="response-review-body">
        ${changes ? `<div class="review-differences">${changes}</div>` : ''}
        <div class="review-terms">${summary}</div>
        ${agreement.offer_note ? `<p class="review-note">Message from ${escapeHtml(offererName)}: ${escapeHtml(agreement.offer_note)}</p>` : ''}
        ${blocked ? `<p class="review-note">${escapeHtml(understandingStatus(agreement.understanding))}</p>` : ''}
        <div class="review-actions">
          ${blocked
            ? `<button type="button" class="button button-primary" data-stage-action="understanding">${agreement.understanding.state === 'awaiting_other' ? 'View understanding status' : 'Resolve understanding'}</button>`
            : `<button type="button" class="button button-primary" data-stage-action="accept">Accept ${agreement.offer_revision ? 'counteroffer' : 'offer'}</button>`}
          <button type="button" class="button button-secondary" data-stage-action="counter">Suggest different terms</button>
          <button type="button" class="text-button" data-stage-action="decline">Decline</button>
        </div>
      </div>
    </details>`;
  } else if (agreement.status === 'in_progress' && selectedParty === agreement.responsible_party
      || agreement.status === 'awaiting_completion_review' && selectedParty !== agreement.responsible_party
      || agreement.status === 'disputed' && selectedParty === agreement.responsible_party) {
    action = '<button type="button" class="text-button next-step" data-jump="completion-panel">View delivery <span aria-hidden="true">→</span></button>';
  }
  if (needsUnderstanding && !canAct) {
    action = `<button type="button" class="button button-secondary next-step" data-stage-action="understanding">${agreement.understanding.state === 'awaiting_other' ? 'View understanding status' : 'Complete understanding'} <span aria-hidden="true">→</span></button>`;
  }
  elements.stageSummary.innerHTML = `<small class="viewer-label">Viewing as ${escapeHtml(person)} · ${role}</small><strong>${escapeHtml(headline)}</strong><span>${escapeHtml(detail)}</span>${action}`;
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

function checklistStatus(value) {
  return ({pending: 'Not submitted', submitted: 'Awaiting review', disputed: 'Needs correction', accepted: 'Accepted'})[value] || 'Not started';
}

function renderChecklist() {
  const plan = agreement.delivery_plan;
  const responsible = agreement.responsible_party;
  const provider = personName(responsible);
  const reviewer = personName(responsible === 'a' ? 'b' : 'a');
  const intro = `<p class="muted-copy">${escapeHtml(provider)} delivers the work. ${escapeHtml(reviewer)} checks each agreed item against its acceptance criteria.</p>`;
  if (!plan || plan.status === 'rejected') {
    const previous = plan?.status === 'rejected' ? `<p class="delivery-outcome">The earlier checklist was declined: ${escapeHtml(plan.review_note || 'Please revise the checklist.')}</p>` : '';
    return `${intro}${previous}<form id="plan-form" class="nested-form">
      <p class="muted-copy">Agree on what must be delivered before work is marked complete. Both people must approve this checklist. Screenshots are attached later, when the responsible person submits each finished item.</p>
      <div id="plan-items">
        <div class="deliverable-fields">
          <label>Deliverable<input name="description" required minlength="5" maxlength="250" placeholder="e.g. Complete the website homepage"></label>
          <label>How it will be accepted<textarea name="acceptance_criteria" required minlength="5" maxlength="350" rows="2" placeholder="e.g. Homepage works on mobile and desktop"></textarea></label>
        </div>
      </div><div class="form-actions"><button type="button" class="button button-secondary" data-plan="add">Add deliverable</button><button type="submit" class="button button-primary">Send checklist for approval</button></div>
    </form>`;
  }
  const items = plan.items || [];
  const list = items.map(item => {
    const head = `<div class="deliverable-head"><strong>${escapeHtml(item.description)}</strong><span class="deliverable-badge">${escapeHtml(checklistStatus(item.status))}</span></div>
      <p class="muted-copy">Accept when: ${escapeHtml(item.acceptance_criteria)}</p>`;
    if (plan.status === 'pending') return `<div class="deliverable-item">${head}</div>`;
    const website = item.reference?.startsWith('https://')
      ? `<a href="${escapeHtml(item.reference)}" target="_blank" rel="noopener noreferrer">Open the supplied website</a>`
      : item.reference ? `<span>Reference: ${escapeHtml(item.reference)}</span>` : '';
    const canSubmit = selectedParty === responsible && ['pending','disputed'].includes(item.status);
    const canReview = selectedParty !== responsible && item.status === 'submitted';
    const statement = item.statement ? `<div class="delivery-record"><strong>Delivery statement</strong><p>${escapeHtml(item.statement)}</p>
      ${website ? `<p class="evidence-link">${website}</p>` : ''}
      ${imageGallery(item.screenshots)}${imageGallery(item.earlier_screenshots,true)}</div>` : '';
    const insight = item.evidence_insight ? `<div class="evidence-insight"><strong>✦ AI evidence insight</strong>
      <p><b>What it shows:</b> ${escapeHtml(item.evidence_insight.visible)}</p>
      <p><b>Not verified:</b> ${escapeHtml(item.evidence_insight.uncertain)}</p>
      <p><b>Check next:</b> ${escapeHtml(item.evidence_insight.next_check)}</p>
      <small>AI observations, not proof of authenticity. You decide whether to accept.</small></div>` : '';
    const reviewingEvidence = evidenceReviewPendingId === item.id;
    const aiAction = canReview && item.screenshots?.length && !item.evidence_insight ? `
      <div class="evidence-review-action">
        <button type="button" class="button button-secondary" data-evidence-check="${escapeHtml(item.id)}" ${evidenceReviewPendingId ? 'disabled' : ''}>
          ${reviewingEvidence ? '<span class="evidence-spinner" aria-hidden="true"></span> Checking evidence…' : '✦ Check evidence with AI'}
        </button>
        ${reviewingEvidence ? `<div class="evidence-review-progress" role="status" aria-live="polite">
          <strong>AI review in progress</strong>
          <p>Examining the screenshot against the agreed criteria${item.reference?.startsWith('https://') ? ' and checking available public website text' : ''}. No decision will be made automatically.</p>
          <small>It may take a moment. You can still accept or request changes yourself.</small>
        </div>` : ''}
      </div>` : '';

    const review = item.review_note ? `<p class="delivery-outcome">Review: ${escapeHtml(item.review_note)}</p>` : '';
    const entry = canSubmit ? `<form data-item-submit="${escapeHtml(item.id)}" class="nested-form">
      <label>What was completed?<textarea name="statement" required minlength="8" maxlength="1500" rows="2" placeholder="Describe what was done and how it meets the criteria"></textarea></label>
      <label>Website link or reference (optional)<input name="reference" maxlength="500" placeholder="https://example.com/finished-page"></label>
      <label class="evidence-upload">Attach screenshots (optional, up to two)<input type="file" name="screenshots" accept="image/png,image/jpeg,image/webp" multiple><small>PNG, JPG or WebP · 2 MB each</small></label>
      <div class="evidence-upload-preview" aria-live="polite"></div>
      <button type="submit" class="button button-primary">${item.status === 'disputed' ? 'Resubmit corrected work' : 'Submit work for review'}</button></form>` : '';
    const decision = canReview ? `<div class="form-actions"><button type="button" class="button button-primary" data-item-review="${escapeHtml(item.id)}" data-accept="true">Accept item</button><button type="button" class="button button-secondary" data-show-dispute="${escapeHtml(item.id)}">Request correction</button></div>
      <form class="nested-form hidden" id="dispute-${escapeHtml(item.id)}" data-item-dispute="${escapeHtml(item.id)}">
        <label>What needs correction?<textarea name="note" minlength="5" maxlength="1000" required rows="2"></textarea></label><button type="submit" class="button button-secondary">Send correction request</button></form>` : '';
    return `<div class="deliverable-item">${head}${statement}${insight}${review}${entry}${aiAction}${decision}</div>`;
  }).join('');
  if (plan.status === 'pending') {
    const canReview = selectedParty !== plan.author;
    return `${intro}<p class="delivery-outcome">Checklist proposed by ${escapeHtml(personName(plan.author))}. ${canReview ? 'Review each item before approving.' : `Waiting for ${escapeHtml(personName(selectedParty === 'a' ? 'b' : 'a'))} to approve.`}</p>${list}
      ${canReview ? `<div class="form-actions"><button class="button button-primary" data-plan="approve" type="button">Approve checklist</button><button class="button button-secondary" data-plan="decline" type="button">Request changes</button></div>
      <form class="nested-form hidden" id="plan-rejection"><label>What should change?<textarea name="note" rows="2" required minlength="5" maxlength="700"></textarea></label><button type="submit" class="button button-secondary">Send feedback</button></form>` : ''}`;
  }
  const completed = plan.accepted_count || 0;
  const total = plan.total_count || items.length;
  const finished = completed === total;
  const roleHint = finished && selectedParty === responsible
    ? '<p class="muted-copy">Your submitted work was accepted. This delivery is complete, so there is nothing further to submit.</p>'
    : finished ? '<p class="muted-copy">You accepted the submitted work. The delivery record is now complete.</p>'
    : selectedParty === responsible
      ? '<p class="muted-copy">To send finished work, use <strong>Submit work for review</strong> below each outstanding item. Screenshots can be attached in that form.</p>'
      : `<p class="muted-copy">${escapeHtml(provider)} submits evidence for each item. You can review the images, accept the item or request a correction.</p>`;
  return `${intro}<div class="delivery-progress"><strong>${completed} of ${total} items accepted</strong><span>${finished ? 'All agreed work reviewed' : 'Every item must be accepted before completion'}</span></div>
    ${roleHint}${list}${finished ? '<p class="delivery-outcome">All deliverables were accepted by the reviewing participant. The delivery record is preserved in the agreement history.</p>' : ''}`;
}

function renderCompletion() {
  const delivery = agreement.completion;
  const responsible = agreement.responsible_party;
  const provider = personName(responsible);
  const reviewer = personName(responsible === 'a' ? 'b' : 'a');
  elements.completionPanel.classList.toggle('hidden', !agreement.active);
  elements.deliveryHelp.textContent = `${provider} is responsible for delivery. ${reviewer} reviews the result.`;
  if (!agreement.active) return;
  if (agreement.delivery_plan || !delivery) {
    elements.completionContent.innerHTML = renderChecklist();
    return;
  }
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

function renderConversation() {
  const conversation = agreement.conversation || { messages: [], review: null, review_current: false };
  const messages = conversation.messages || [];
  elements.conversationMessages.innerHTML = messages.length ? messages.slice(-12).map(message => {
    const author = message.author === 'a' ? agreement.party_a : agreement.party_b;
    return `<div class="conversation-entry${message.author === selectedParty ? ' own' : ''}">
      <div class="conversation-byline"><strong>${escapeHtml(author)}</strong><time>${escapeHtml(formatDate(message.created_at))}</time></div>
      <p>${escapeHtml(message.body)}</p>
    </div>`;
  }).join('') : '<p class="muted-copy">No messages yet. Start the conversation here.</p>';

  elements.conversationReview.disabled = !messages.length || conversationReviewPending;
  elements.conversationReview.textContent = conversationReviewPending ? 'Reviewing conversation…' : 'Review conversation with AI';
  const review = conversation.review;
  if (!review) {
    elements.conversationResult.classList.add('hidden');
    elements.conversationResult.innerHTML = '';
    return;
  }
  const current = conversation.review_current;
  const observations = (review.observations || []).map(item => {
    const author = personName(item.author);
    return `<div class="conversation-observation"><div class="conversation-byline"><strong>${escapeHtml(item.kind.replaceAll('_', ' '))}</strong><span>${escapeHtml(author)}</span></div>
      <blockquote>${escapeHtml(item.quote)}</blockquote>
      ${item.meaning ? `<p>${escapeHtml(item.meaning)}</p>` : ''}</div>`;
  }).join('');
  const changes = (review.changes || []).map(item => `<div class="conversation-change"><strong>${escapeHtml(fieldNames[item.field] || item.field)}</strong>
      <span>${escapeHtml(item.new_value)}</span><small>“${escapeHtml(item.evidence)}”</small></div>`).join('');
  const pendingChange = (agreement.proposals || []).some(item => item.status === 'pending');
  const canDraft = current && review.intent === 'change_proposal' && (review.changes || []).length
    && agreement.active && agreement.status === 'in_progress' && !pendingChange
    && review.last_author === selectedParty;
  const suggested = {...agreement.terms};
  for (const change of review.changes || []) {
    if (Object.hasOwn(suggested, change.field)) suggested[change.field] = change.new_value;
  }
  const termsPreview = Object.entries(suggested).map(([field, value]) => `
    <div class="review-term"><span>${escapeHtml(fieldNames[field] || field)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
  const approveAction = canDraft ? `<details class="review-action">
      <summary>Prepare an amendment</summary>
      ${review.confirmed_prior_offer ? '<p class="muted-copy">Suggested from a quoted price condition and a follow-up confirmation. Check the price carefully; a chat reply alone does not change the agreement.</p>' : ''}
      <p class="muted-copy">Check all the terms before sending. By sending this proposal, you approve the suggested change. The other person must approve it before it takes effect.</p>
      <div class="review-terms">${termsPreview}</div>
      <button class="button button-primary" type="button" id="send-conversation-change">Send for approval</button>
    </details>` : '';
  elements.conversationResult.innerHTML = `<div class="conversation-review-title"><strong>Conversation review</strong><span>${current ? 'Current' : 'Earlier review'}</span></div>
    <p class="muted-copy">${current ? 'Only statements linked to the messages below are shown. Review interpretations before acting.' : 'New messages were added since this review. Run it again for an updated assessment.'}</p>
    ${observations || '<p class="muted-copy">No source-linked observations returned.</p>'}
    ${changes ? `<h3>${review.confirmed_prior_offer ? 'Price discussed and confirmed in conversation' : 'Possible changes in the latest message'}</h3>${changes}` : '<p class="muted-copy">No verified new amendment in the latest message. You can still propose updated terms without AI below.</p>'}
    ${approveAction}
    ${pendingChange && current && review.changes?.length ? '<p class="conversation-safety">An amendment is already awaiting a response. Review it in Changes.</p>' : ''}
    <p class="conversation-safety">The approved agreement stays unchanged until both people explicitly approve an amendment.</p>`;
  elements.conversationResult.classList.remove('hidden');
}

function renderAgreement() {
  elements.createPanel.classList.add('hidden');
  elements.studio.classList.remove('hidden');
  elements.caseTitle.textContent = agreement.title;
  elements.caseDetail.textContent = `${agreement.party_a} and ${agreement.party_b}`;
  renderTerms();
  renderUnderstanding();
  renderChanges();
  renderHistory();
  renderCompletion();
  displayEvidenceImages();
  renderConversation();
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

elements.conversationForm.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = elements.conversationForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  clearNotice();
  try {
    agreement = await request(`/cases/${savedAccess.id}/conversation/messages`, 'POST', {
      message: elements.conversationForm.elements.message.value.trim()
    });
    elements.conversationForm.reset();
    renderAgreement();
  } catch (error) { notify(error.message, true); }
  finally { submit.disabled = false; }
});

function setConversationFeedback(message, isError = false, reviewing = false) {
  if (reviewing) {
    elements.conversationFeedback.innerHTML = `<span class="evidence-spinner" aria-hidden="true"></span>
      <span><strong>${escapeHtml(message)}</strong><small>Looking for proposals, conditions and confirmations. Checking quotations against the conversation. Agreement terms remain unchanged until both participants approve.</small></span>`;
  } else {
    elements.conversationFeedback.textContent = message;
  }
  elements.conversationFeedback.classList.toggle('conversation-feedback-pending', reviewing);
  elements.conversationFeedback.classList.toggle('hidden', !message);
  elements.conversationFeedback.classList.toggle('error', isError);
}

elements.conversationReview.addEventListener('click', async () => {
  if (conversationReviewPending || !agreement?.conversation?.messages?.length) return;
  conversationReviewPending = true;
  elements.conversationReview.disabled = true;
  elements.conversationReview.innerHTML = '<span class="evidence-spinner" aria-hidden="true"></span> Reviewing conversation…';
  setConversationFeedback('Reviewing the conversation with Meta', false, true);
  clearNotice();
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 70000);
  const slowNotice = window.setTimeout(() => {
    setConversationFeedback('Still reviewing with Meta', false, true);
  }, 15000);
  try {
    agreement = await request(`/cases/${savedAccess.id}/conversation/review`, 'POST', undefined, {signal: controller.signal});
    clearTimeout(slowNotice);
    setConversationFeedback('Review complete. Any changes still require both people to approve.');
    renderAgreement();
    elements.conversationResult.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  } catch (error) {
    const message = error.name === 'AbortError'
      ? 'The AI review timed out. Your agreement is unchanged. Please check Meta availability before trying again.'
      : `${error.message} Your agreement is unchanged.`;
    setConversationFeedback(message, true);
  } finally {
    clearTimeout(timeout);
    clearTimeout(slowNotice);
    conversationReviewPending = false;
    elements.conversationReview.disabled = !agreement?.conversation?.messages?.length;
    elements.conversationReview.textContent = 'Review conversation with AI';
  }
});

elements.conversationResult.addEventListener('click', async event => {
  if (event.target.id !== 'send-conversation-change') return;
  const button = event.target;
  if (button.disabled) return;
  button.disabled = true;
  clearNotice();
  try {
    agreement = await request(`/cases/${savedAccess.id}/conversation/prepare-amendment`, 'POST');
    renderAgreement();
    notify('Amendment sent. The other person can now review it. Your agreed terms have not changed.');
    elements.proposals.scrollIntoView({behavior: 'smooth', block: 'center'});
  } catch (error) {
    notify(error.message, true);
    button.disabled = false;
  }
});

elements.createForm.addEventListener('submit', async event => {
  event.preventDefault();
  elements.createButton.disabled = true;
  clearNotice();
  try {
    const values = Object.fromEntries(new FormData(elements.createForm).entries());
    const result = await request('/cases', 'POST', values);
    savedAccess = { id: result.case_id, keys: { a: result.party_a_key } };
    selectedParty = 'a';
    editUnderstanding = false;
    understandingRevision = null;
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
    notify('Offer accepted. The agreement is now active.');
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
    notify('Offer declined. No agreement was activated.');
  } catch (error) { notify(error.message, true); }
});

elements.understandingRequest.addEventListener('click', async () => {
  clearNotice();
  try {
    agreement = await request(`/cases/${savedAccess.id}/understanding/request`, 'POST');
    renderAgreement();
    notify('Understanding check started. Ask the other person to complete their response.');
  } catch (error) { notify(error.message, true); }
});

elements.understandingEdit.addEventListener('click', () => {
  editUnderstanding = true;
  renderUnderstanding();
  elements.understandingForm.querySelector('input')?.focus();
});

elements.understandingUseOffer.addEventListener('click', () => {
  setFormTerms(elements.understandingForm, agreement.terms);
  editUnderstanding = true;
  elements.understandingForm.dataset.dirty = 'true';
  elements.understandingForm.querySelector('input')?.focus();
});

elements.understandingForm.addEventListener('input', () => {
  elements.understandingForm.dataset.dirty = 'true';
});

elements.understandingForm.addEventListener('submit', async event => {
  event.preventDefault();
  clearNotice();
  const submit = elements.understandingForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    const payload = Object.fromEntries(new FormData(elements.understandingForm).entries());
    agreement = await request(`/cases/${savedAccess.id}/understanding`, 'POST', payload);
    delete elements.understandingForm.dataset.dirty;
    editUnderstanding = false;
    renderAgreement();
    const current = agreement.understanding;
    notify(current.ready
      ? 'Both responses match the offer. The reviewer can now accept it.'
      : understandingStatus(current));
  } catch (error) { notify(error.message, true); }
  finally { submit.disabled = false; }
});

elements.counterForm.addEventListener('submit', async event => {
  event.preventDefault();
  clearNotice();
  const payload = Object.fromEntries(new FormData(elements.counterForm).entries());
  try {
    agreement = await request(`/cases/${savedAccess.id}/counter`, 'POST', payload);
    elements.counterPanel.open = false;
    renderAgreement();
    notify('Counteroffer sent. The other person can accept, counter again or decline.');
  } catch (error) {
    const unchanged = error.message.includes('Change at least one term');
    notify(unchanged ? 'To accept the latest offer, use Accept. To counter, change the price, deadline or scope.' : error.message, true);
  }
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
  if (event.target.id === 'plan-form') {
    event.preventDefault();
    const fields = [...event.target.querySelectorAll('.deliverable-fields')];
    const items = fields.map(field => ({
      description: field.querySelector('[name="description"]').value.trim(),
      acceptance_criteria: field.querySelector('[name="acceptance_criteria"]').value.trim()
    }));
    if (!window.confirm('Send this checklist for the other participant to review?')) return;
    try {
      agreement = await request(`/cases/${savedAccess.id}/delivery-plan`, 'POST', {items});
      renderAgreement();
      notify('Checklist sent. The other participant must approve it before delivery can be recorded.');
    } catch (error) { notify(error.message, true); }
    return;
  }
  if (event.target.id === 'plan-rejection') {
    event.preventDefault();
    const plan = agreement.delivery_plan;
    try {
      agreement = await request(`/cases/${savedAccess.id}/delivery-plan/${plan.id}/respond`, 'POST', {
        accepted: false, note: event.target.elements.note.value.trim()
      });
      renderAgreement();
      notify('Checklist feedback sent. A new checklist can now be proposed.');
    } catch (error) { notify(error.message, true); }
    return;
  }
  const disputeForm = event.target.closest('[data-item-dispute]');
  if (disputeForm) {
    event.preventDefault();
    try {
      agreement = await request(`/cases/${savedAccess.id}/delivery-items/${disputeForm.dataset.itemDispute}/review`, 'POST', {
        accepted: false, note: disputeForm.elements.note.value.trim()
      });
      renderAgreement();
      notify('Correction request sent. The agreed item remains outstanding.');
    } catch (error) { notify(error.message, true); }
    return;
  }
  const itemForm = event.target.closest('[data-item-submit]');
  if (itemForm) {
    event.preventDefault();
    const values = {statement: itemForm.elements.statement.value.trim(), reference: itemForm.elements.reference.value.trim()};
    const files = [...itemForm.querySelector('[name="screenshots"]').files];
    const submitButton = itemForm.querySelector('[type="submit"]');
    submitButton.disabled = true;
    try {
      if (files.length > 2) throw new Error('Choose at most two screenshots.');
      values.screenshots = await Promise.all(files.map(encodeScreenshot));
      agreement = await request(`/cases/${savedAccess.id}/delivery-items/${itemForm.dataset.itemSubmit}/submit`, 'POST', values);
      renderAgreement();
      notify('Deliverable submitted. Waiting for the other participant to review it.');
    } catch (error) { notify(error.message, true); }
    finally { submitButton.disabled = false; }
    return;
  }
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

elements.completionContent.addEventListener('change', event => {
  if (event.target.name !== 'screenshots') return;
  const target = event.target.closest('form')?.querySelector('.evidence-upload-preview');
  if (!target) return;
  const files = [...event.target.files];
  target.textContent = files.length ? `${files.length} screenshot${files.length === 1 ? '' : 's'} selected: ${files.map(f => f.name).join(', ')}` : '';
});

elements.completionContent.addEventListener('click', async event => {
  const evidenceCheck = event.target.closest('button[data-evidence-check]');
  if (evidenceCheck) {
    if (evidenceReviewPendingId) return;
    evidenceReviewPendingId = evidenceCheck.dataset.evidenceCheck;
    renderAgreement();
    try {
      agreement = await request(`/cases/${savedAccess.id}/delivery-items/${evidenceReviewPendingId}/check-evidence`, 'POST', {});
      notify('AI evidence insight is ready. You decide whether to accept the work.');
    } catch (error) {
      notify(error.message, true);
    } finally {
      evidenceReviewPendingId = null;
      renderAgreement();
    }
    return;
  }
  const planAction = event.target.closest('button[data-plan]');
  if (planAction) {
    const action = planAction.dataset.plan;
    if (action === 'add') {
      const wrap = elements.completionContent.querySelector('#plan-items');
      if (!wrap || wrap.children.length >= 10) return;
      const block = document.createElement('div');
      block.className = 'deliverable-fields';
      block.innerHTML = `<label>Deliverable<input name="description" required minlength="5" maxlength="250"></label>
        <label>How it will be accepted<textarea name="acceptance_criteria" required minlength="5" maxlength="350" rows="2"></textarea></label>
        <button type="button" class="text-button" data-plan="remove">Remove item</button>`;
      wrap.appendChild(block);
    } else if (action === 'remove') {
      planAction.closest('.deliverable-fields')?.remove();
    } else if (action === 'decline') {
      elements.completionContent.querySelector('#plan-rejection')?.classList.toggle('hidden');
    } else if (action === 'approve') {
      if (!window.confirm('Approve this delivery checklist and its acceptance criteria?')) return;
      try {
        agreement = await request(`/cases/${savedAccess.id}/delivery-plan/${agreement.delivery_plan.id}/respond`, 'POST', {accepted:true,note:''});
        renderAgreement();
        notify('Delivery checklist approved. Each item can now be tracked.');
      } catch (error) { notify(error.message, true); }
    }
    return;
  }
  const showDispute = event.target.closest('[data-show-dispute]');
  if (showDispute) {
    elements.completionContent.querySelector(`#dispute-${showDispute.dataset.showDispute}`)?.classList.toggle('hidden');
    return;
  }
  const reviewItem = event.target.closest('[data-item-review]');
  if (reviewItem) {
    if (!window.confirm('Have you checked this item against its acceptance criteria?')) return;
    try {
      agreement = await request(`/cases/${savedAccess.id}/delivery-items/${reviewItem.dataset.itemReview}/review`, 'POST', {accepted:true,note:''});
      renderAgreement();
      notify(agreement.status === 'completed' ? 'Every deliverable was accepted. The agreement is complete.' : 'Deliverable accepted.');
    } catch (error) { notify(error.message, true); }
    return;
  }
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

function openUnderstanding() {
  const panel = elements.understandingPanel;
  if (panel.classList.contains('hidden')) return;
  panel.scrollIntoView({behavior: 'smooth', block: 'center'});
  panel.classList.remove('understanding-focus');
  void panel.offsetWidth;
  panel.classList.add('understanding-focus');
  const form = elements.understandingForm;
  const target = !form.classList.contains('hidden')
    ? form.querySelector('input, textarea')
    : !elements.understandingRequest.classList.contains('hidden')
      ? elements.understandingRequest
      : panel;
  window.setTimeout(() => target?.focus({preventScroll: true}), 350);
}

elements.stageSummary.addEventListener('click', event => {
  const action = event.target.closest('button[data-stage-action]')?.dataset.stageAction;
  if (action === 'understanding') {
    openUnderstanding();
    return;
  }
  if (action === 'accept') {
    if (elements.confirmButton.disabled) openUnderstanding();
    else elements.confirmButton.click();
    return;
  }
  if (action === 'counter') {
    elements.counterPanel.open = true;
    setFormTerms(elements.counterForm, agreement.terms);
    elements.counterPanel.scrollIntoView({behavior: 'smooth', block: 'center'});
    return;
  }
  if (action === 'decline') {
    elements.declinePanel.classList.remove('hidden');
    elements.declinePanel.scrollIntoView({behavior: 'smooth', block: 'center'});
    return;
  }
  const target = event.target.closest('button[data-jump]');
  if (target) document.getElementById(target.dataset.jump)?.scrollIntoView({behavior: 'smooth', block: 'center'});
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
  const plan = agreement?.delivery_plan;
  const checklist = documentRecord.current && plan?.status === 'active'
    ? `<h2>Delivery checklist</h2><p class="muted-copy">${plan.accepted_count} of ${plan.total_count} items accepted.</p>${plan.items.map(item => `
      <div class="paper-checklist-item"><strong>${escapeHtml(item.description)}</strong>
        <p>Acceptance criteria: ${escapeHtml(item.acceptance_criteria)}</p>
        <p>Status: ${escapeHtml(checklistStatus(item.status))}</p>
        ${item.statement ? `<p>Submitted work: ${escapeHtml(item.statement)}</p>` : ''}
        ${item.reference ? `<p>Evidence reference: ${escapeHtml(item.reference)}</p>` : ''}
        ${item.review_note ? `<p>Review note: ${escapeHtml(item.review_note)}</p>` : ''}</div>`).join('')}
      <p class="muted-copy">Participant approvals record acceptance of the submitted evidence; the platform does not independently certify workmanship, identity or legal validity.</p>`
    : '';
  const legacy = documentRecord.current && delivery
    ? `<h2>Delivery record</h2><p>${escapeHtml(delivery.statement)}</p><p class="muted-copy">Status: ${escapeHtml(delivery.status)}${delivery.review_note ? ` · ${escapeHtml(delivery.review_note)}` : ''}</p>` : '';
  elements.documentDelivery.innerHTML = checklist || legacy;
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
  sessionStorage.removeItem(storageKey);
  savedAccess = null;
  invitationLink = null;
  agreement = null;
  selectedParty = 'a';
  editUnderstanding = false;
  understandingRevision = null;
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
      : health.restricted_demo ? 'This is a restricted competition demonstration using synthetic agreements. It is not an identity-verified or legally certified service.' : 'Local development preview. Message analysis runs in offline demonstration mode, and invitation links work only on this running server.';
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
      if (savedAccess) saveAccess();
    }
    if (savedAccess) {
      try { await refreshAgreement(); }
      catch { sessionStorage.removeItem(storageKey); savedAccess = null; }
    }
  } catch (error) {
    notify(`Unable to connect to the local server: ${error.message}`, true);
  }
}

initialize();

let backgroundRefresh = false;
async function refreshInBackground() {
  if (backgroundRefresh || document.hidden || !savedAccess || !agreement || elements.studio.classList.contains('hidden')) return;
  const active = document.activeElement;
  if (active?.matches('input, textarea, select') && active.closest('form')) return;
  backgroundRefresh = true;
  try {
    const fresh = await request(`/cases/${savedAccess.id}`);
    const relevant = value => JSON.stringify([value.status, value.terms, value.proposals,
      value.completion, value.delivery_plan, value.history.length, value.offer_revision, value.understanding,
      value.conversation?.messages?.length, value.conversation?.review_id]);
    if (relevant(fresh) !== relevant(agreement)) {
      agreement = fresh;
      renderAgreement();
    }
  } catch {
  } finally {
    backgroundRefresh = false;
  }
}
window.setInterval(refreshInBackground, 6000);
window.addEventListener('focus', refreshInBackground);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refreshInBackground();
});
