# SamePage AI

A two-person agreement workspace: negotiate terms, confirm mutual understanding, interpret conversation changes with Meta Muse Spark, approve amendments and verify delivery against an agreed checklist.

Built as new work for the Meta Global AI Developer Hackathon, October 26–November 4, 2026.

## Run locally

Use Python 3.13 and `uv` on Windows:

```powershell
uv run --python 3.13 --with-requirements requirements.txt python scripts/run_meta.py
```

The launcher prompts for your Meta Model API key privately. Do not add the key to GitHub. For a local demonstration without AI requests:

```powershell
uv run --python 3.13 --with-requirements requirements.txt uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Invitations are scoped to this local server and should be used with synthetic data.

## What it does

- Person A creates an agreement; Person B can accept, decline or counteroffer.
- Both participants can independently check their understanding of the terms.
- A structured conversation history allows Muse Spark to identify evidence-linked proposals, conditions and questions. Python validates findings; only explicit human approval changes terms.
- Both people approve a delivery checklist with concrete acceptance criteria.
- The responsible participant submits evidence references for each item. The other participant accepts the item or requests correction.
- Disputed items can be resubmitted; prior review events remain in the audit history. Completion requires all items to be accepted.
- Approved agreement versions and the latest itemized delivery record can be printed.

## Verify

```powershell
uv run --python 3.13 --with-requirements requirements.txt python -m pytest -q
uv run --python 3.13 --with-requirements requirements.txt python -m scripts.prove_delivery
```

See [Delivery proof](docs/delivery-proof.md) and [technical differentiation](docs/technical-differentiation.md) for details. The deterministic delivery proof makes no paid API calls.

## Architecture

- Python / FastAPI / SQLite development database
- Pure Python business rules for permissions, approvals, delivery and audit records
- Meta Muse Spark 1.3 for conversation interpretation, with evidence validation
- Responsive HTML, CSS and JavaScript frontend

## Security and scope

**Local competition prototype only. Not ready for unrestricted public deployment or real customer documents.** The initial invitation mechanism is not a production identity system, and the first creator receives the recipient's invitation token to share. The SQLite audit chain checks consistency but is not independently tamper-proof. The platform does not hold funds, certify work, provide legal advice or verify participant identity.

Do not commit `.env` files, API keys, local databases, private invitations or real agreements. Use synthetic demonstration data. Production deployment requires proper independent accounts, rate limits, secure secret handling, encrypted hosted storage, backup and retention controls.

## Restricted competition deployment

A sample-only Railway deployment is documented in [docs/deployment.md](docs/deployment.md). It uses a separate demo password, HTTPS, a persistent SQLite volume and a small daily Meta API allowance. This access gate is **not** production user authentication. Do not upload real agreements or share the demo password publicly. See also the [three-minute video outline](docs/demo-video.md).


## v1.1 — Visual delivery evidence

Each deliverable can include two private screenshots and an optional public HTTPS page reference. The reviewer may use Meta Muse Spark 1.3 for concise, evidence-aware observations before deciding whether to accept work. A limited, DNS-pinned public HTML check can assist with textual consistency, not visual/functional proof. Original screenshots and audit entries survive resubmissions. Run `python -m pytest -q` for the automated tests; see `docs/visual-evidence.md` for privacy, VPS deployment and GitHub update instructions.
