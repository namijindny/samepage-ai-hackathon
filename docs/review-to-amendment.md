# Conversation findings and approval

After Meta returns an evidence-backed conversation review, SamePage permits the author of the most recent message to prepare only the changes validated for that specific message.

The server checks the review against the latest message, the approved agreement version, and the offer revision. It rechecks quoted evidence, calculates the differences from approved terms in Python, and creates a proposal that already records the proposer's approval. The other participant must approve separately. The approved agreement and printable historical document remain unchanged until then.

A new message, an agreement revision, a delivery review, or another pending amendment prevents a stale review from being submitted. The current review is distinguished by its saved ID so that participants' screens refresh when an analysis is replaced. No model call is made when preparing an already reviewed proposal.

## Example

1. Both participants accept the original agreement: price ₦150,000 and deadline December 31.
2. Person A writes: “I propose January 15, 2027, with no price change.”
3. Person A requests **Review conversation with AI**.
4. If the result identifies a verified explicit deadline change, the author opens **Prepare an amendment**, checks the full new terms, and selects **Send for approval**.
5. Person B reviews the original price and the proposed deadline and either accepts or declines.
6. Only after Person B accepts does the application move to the next agreement version.

A question, withdrawal, rejection, or conditional/unsupported statement must not create an actionable amendment. If Meta returns no verified change, participants may continue negotiating or use the manual proposal form.

## Limitations

This is a hackathon prototype. Private invitation links are not identity verification, and the application is not ready for unrestricted public use. The system does not provide legal certification or assurance of contract enforceability. AI accuracy needs evaluation against labeled real and synthetic examples.
