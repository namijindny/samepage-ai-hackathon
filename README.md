# SamePage

A two-person agreement workspace built during the Meta Global AI Developer Hackathon (October 26–November 4, 2026).

SamePage helps two people propose terms, negotiate a counteroffer, check whether they understood the same terms, approve amendments, and track delivery. The application preserves accepted versions instead of rewriting the original agreement.

## What works

- An initiator creates an offer and gives the recipient a separate invitation link.
- Either party can counter; the other can accept, counter again, or decline.
- An optional shared-understanding check compares each person's price, deadline, and deliverable against the pending offer. Conflicts block acceptance until resolved.
- Accepted terms cannot be changed without approval. Delivery can be submitted, accepted, or disputed.
- Accepted versions can be viewed and printed.
- Meta Muse Spark can interpret incoming change proposals; Python independently verifies quoted evidence and changes. Approval decisions are not delegated to the model.

## Run locally

Requires [uv](https://docs.astral.sh/uv/). From the project directory:

```powershell
uv run --python 3.13 --with-requirements requirements.txt python scripts/run_meta.py
```

This prompts for a Meta Model API key without storing it in the repository. Model calls can incur charges; verify billing and available credits before testing. A local offline demonstrator is also available:

```powershell
uv run --python 3.13 --with-requirements requirements.txt uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The offline pattern demonstrator is limited; do not represent its output as a model result.

## Tests

```powershell
uv run --python 3.13 --with-requirements requirements.txt pytest -q
```

## Repository structure

- `app/` — Python API, agreement workflow, semantic analysis, storage and safeguards.
- `web/` — responsive client interface.
- `tests/` — workflow and validation tests.
- `scripts/` — local startup and evaluation tools.
- `docs/` — technical design and evaluation notes.

## Current limitations

This is a hackathon prototype, not a contract-signing or legal-advice service. Access is based on private invitation tokens rather than verified identities, and local storage is not production-hardened. Do not deploy it with sensitive agreements until authentication, privacy protections, rate limiting and a security review have been completed. Agreement history hashes are integrity indicators, not independent notarization.

`data/`, local databases, credentials, caches and generated archives are excluded from Git. Keep real conversations and private links out of public commits.
