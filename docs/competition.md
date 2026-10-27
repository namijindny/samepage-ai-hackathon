# Hackathon project brief — SamePage AI

## Track and theme

- Proposed track: **Indie Developer** (verify that this is the registered track).
- Theme: **Build for Your World**.
- Working title: **SamePage AI: Agreement Drift Guardian**.
- Core claim: Detect proposed changes in ongoing informal agreements and preserve clear versioned, two-person acceptance.
- Desired original technical contribution: evidence-grounded semantic drift extraction + deterministic bilateral approval/contract-state engine.

## Evidence of user value

A user can create terms, receive another party's confirmation, investigate a new proposed change, independently accept/reject an amendment, and view or print every confirmed document version. Do not claim the system creates legally enforceable contracts.

## Why this is not just a chatbot

The application maintains a deterministic state machine; model text cannot unilaterally change the agreement. The model proposes structured change records with evidence, server validates fields and quote matches, and both parties independently authorize a versioned transition. We must still prove these functions are meaningfully better than a basic model in tests.

## Hackathon constraints from organizers' Discord screenshots

- New work and demonstrable contributions during event; fresh public repository, no pre-hackathon code masquerading as new.
- Public repository and working link at submission.
- 3-minute demo video.
- Teams max 4, choose a single track, submit once.
- Deadline: November 4, 2026 at 9:00 PM Eastern Time.
- Avoid generic RAG/chatbot wrappers, unsupported rights/asset usage, or unsafe content.

## Minimum test plan

1. Proposed deadline vs confirmed deadline is detected but not applied.
2. Added payment is correctly interpreted as a delta rather than a replacement.
3. A question or hypothetical is not automatically promoted to an amendment.
4. No mutation with only one participant's approval.
5. Old proposals cannot be applied against a newer version; old approved documents remain viewable.
6. Rejection leaves active terms unchanged.
7. Untrusted text inside a message does not bypass rules.
8. Source quote must match literal user-provided text.
9. Baseline a generic Muse prompt with equivalent input and compare drift classification and false positives.

## Milestones

- Oct 26: Fresh project scaffold, clean tests, offline demonstration, public repo initialized.
- Oct 27: Approved-document view, version history and print-to-PDF; public repository. Claim credits and live-test Meta when available.
- Oct 28–29: Stronger evidence evaluation, ambiguity and contradiction detection.
- Oct 30–31: Harden authentication, secure sharing, improve UX.
- Nov 1–2: Held-out benchmark, report failure cases honestly.
- Nov 3: Record real 3-minute demo showing LIVE Meta operation; avoid staged or fake outputs.
- Nov 4: Submit links and contribution statement before 9 PM ET.

## Three-minute video story

0:00–0:25 Problem / two parties have different expectations.
0:25–0:55 Create & confirm agreement.
0:55–1:35 Incoming changed price/deadline detected by Meta model with evidence.
1:35–2:10 One party approves; it remains pending. Second approves; version increments.
2:10–2:35 Ambiguous question is correctly handled; no silent change.
2:35–3:00 Real code, benchmark results, contribution disclosure, future potential.

## Cost governance

- Default = `offline_demo`, free.
- Live model = `muse-spark-1.3` Standard via Meta API.
- At most 650 completion tokens per request; limit input to a short message and the current terms.
- No automatic API retries; estimate/log local call counts before more complex pipelines.
- API billing alerts are not equivalent to automatic hard spending limits.

## Honest capability boundaries (October 27)

- Confirmations and agreement changes run in Python/FastAPI and are tested locally. A clean printable agreement is implemented.
- `offline_demo` is still a narrow regular-expression rule set, not AI. Do not call it Meta-powered in the demonstration.
- `ANALYSIS_MODE=meta` is wired to Muse Spark but **has not yet been tested using live Meta credits**. It must be validated and evaluated on held-out conversations before any accuracy claims.
- Distinct participant invitations, identity verification, safe hosted deployment, secure backups, genuine document evidence, real multilingual/audio ingestion and full evaluation remain unfinished.
- Reliable user value depends on producing accurate change detections while minimizing false changes, not merely generating a contract document.
