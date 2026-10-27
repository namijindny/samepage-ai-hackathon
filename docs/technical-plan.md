# SamePage — Technical delivery plan

## Implemented by October 27

- FastAPI API for an agreement with two participant keys, initial confirmations, revisions and decisions.
- SQLite event history and a local hash-chain integrity check (not externally tamper-proof).
- Preservation of every approved version as an authenticated, printable agreement document.
- A limited local pattern-based demo detector. This is explicitly not an AI system.
- Optional Muse Spark call, whose results require real-account testing and held-out evaluation.

## What will make the actual AI system worth testing

1. **Commitment extraction**: identify proposed obligations from conversational turns, with exact evidence spans, actor, timing, amount and uncertainty.
2. **Semantic drift**: compare proposed obligations to the latest mutually approved state, recognizing negotiation, questions, withdrawals, contradictions and accepted amendments.
3. **Evidence and safety**: require original text support, reject unsupported changes, keep the model incapable of directly applying any modification.
4. **Agreement lifecycle**: two independent identities, secure delivery of approvals, immutable version records and a useful document for each finalized version.
5. **Evaluation**: prepare unseen conversations in varied phrasing and languages; measure precision and recall for real proposed changes, false amendments on ambiguous messages, evidence accuracy and reliability under incomplete context.

## Priorities before submission

1. Enable and live-test Meta Muse Spark using real credits with an explicit cost cap.
2. Build a held-out dataset and compare the AI + verification system with a plain Meta model and deterministic baseline.
3. Replace the local two-party key switcher with securely delivered independent invitations and access.
4. Make initial terms richer and support real message/document ingestion and revision explanation.
5. Create an authentic three-minute demonstration, publish only hackathon-period code, and disclose limitations.

## Constraints

Never advertise production security, verified identity, legal enforceability or evaluated AI performance before those properties have been proven. Do not add real users' private conversations to a public repository or shared demo.
