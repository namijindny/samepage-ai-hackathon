# SamePage: evidence-led mutual commitments

## What we're building

SamePage helps ordinary people avoid misunderstandings before accepting an agreement, tracks negotiated amendments, and records completion and review. Its value is a shared workflow, not another contract summarizer.

## Demonstrable capability

1. Initiator proposes a price, deadline and deliverable.
2. Either participant requests a check before acceptance.
3. Both independently describe their understanding.
4. Python checks both responses against the live offer, identifying discrepancies without inventing intent.
5. The recipient cannot accept while the check is unresolved.
6. The parties correct their understanding or counteroffer, and acceptance only applies to the current proposal.
7. Once accepted, both parties must review later amendments. Work completion is submitted and reviewed separately.

## Why an ordinary chat model isn't enough

A general model can summarize a conversation, but it cannot independently obtain both parties' authenticated confirmations, enforce transitions across an application's persisted state, or prevent a proposed amendment from becoming binding in the application. SamePage's Python state machine implements those safeguards, while Meta models interpret unstructured negotiation messages.

This is product differentiation, not proof that no competing service offers similar features. Existing contract-management products already provide AI review, change history and obligation tracking. The distinct target user and demonstrated mutual-understanding workflow must be tested with actual participants.

## What we can measure

- Understanding conflicts identified before acceptance.
- Incorrect approvals prevented by the state engine.
- Source-grounded extraction performance compared with a plain Muse Spark baseline.
- False or missed amendment suggestions in held-out negotiation cases.
- Agreement completion without procedural dead ends.

## Before public deployment

Add real authentication, expiring invitations, granular access controls, data retention controls, abuse protections, privacy review, event notifications and reliable backup/recovery. Do not claim legal enforceability, certified e-signatures, fraud prevention, or identity verification from the prototype.
