# SamePage agreement workflow

An agreement is not only a PDF. SamePage manages a mutual commitment from the initial offer through delivery acceptance or a documented disagreement.

## Roles

- **Initiator (A):** creates and approves the initial offer, names the recipient and assigns responsibility for delivery.
- **Recipient (B):** accepts, declines or counteroffers. A counteroffer replaces the unaccepted draft and requires A to confirm again.
- **Delivering party:** A or B, explicitly selected when the agreement is created. Only this participant can report completion.
- **Reviewing party:** the other participant, who accepts the reported delivery or disputes it with a reason.

## Lifecycle

1. `Awaiting recipient`: A has sent the initial offer. The proposed terms are not yet active.
2. `Review counteroffer`: B has proposed different initial terms. A must approve them.
3. `In progress`: both participants have approved the same terms. The accepted record is viewable and printable.
4. `Change pending`: a proposed amendment is reviewed by both parties. It does not overwrite currently accepted terms.
5. `Review delivery`: the responsible participant reports completion, with an optional evidence reference.
6. `Completed`: the other participant explicitly accepts the delivery record.
7. `Disputed`: the other participant challenges the reported delivery with a reason. The delivering party can resubmit an amended completion report for another review. This is not an adjudication or resolution.

Initial offers can be declined by B. A declined offer is not an active agreement.

## Deterministic safeguards

- Participant access keys determine which actions are permitted.
- Price adjustments must retain the same currency.
- A counteroffer or manually authored amendment requires an actual changed term.
- Previous accepted terms remain available after amendments.
- Pending amendments prevent new delivery submissions.
- Delivery cannot be submitted by the reviewing party.
- The delivering party cannot accept their own work.
- Every transition is logged in the local audit history.

## Role of AI

Meta models assist with interpretation of *new messages* and suggestions for amendments. They do not approve terms, assign participant identity, calculate final monetary totals without independent validation, or determine whether work was completed satisfactorily.

A manual amendment flow works even when Meta is unavailable. This protects users from reliance on AI service availability.

## Local demo vs public product

The first party receives a recipient invitation URL containing an access token in its URL fragment. The initiator's browser retains only its own key. A second browser session can join as the recipient, but both sessions must connect to the same running server. These tokens prove possession, **not real-world identity**, and have no expiry or revocation. The prototype is not suitable for a public deployment or real legal/financial disputes.

Before launch: verified accounts, HTTPS, expiring and revocable invitations, privacy controls, abuse prevention, file evidence handling, reliable backups, notification consent, granular terms, dispute resolution workflows and independent security assessment are required.

## Competition evidence

Benchmark model-assisted change interpretation against an ordinary prompt and the offline detector. Evaluate fabricated changes, false refusals, conditional promises, monetary arithmetic, and exact evidence quotation. The existing test suite checks workflow invariants; it does not establish live model accuracy, legal validity, or security readiness.
