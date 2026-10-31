# SamePage AI — Agreement Drift Guardian

**Fresh Meta Global AI Developer Hackathon prototype (October 26 – November 4, 2026).**

A two-party, versioned agreement experience. It can propose changes extracted from incoming messages, preserve the source text, and apply an amendment **only after both parties confirm**. Created from scratch as competition-period work.

> **Important:** The default `offline_demo` analyzer is a **limited deterministic pattern demonstrator, not Meta AI**. It recognizes a small illustrative set of weekday and NGN-price modifications. Enable `ANALYSIS_MODE=meta` with valid credits and a Meta Model API key to use Muse Spark 1.3. The Meta-backed path is implemented but **has not been live-tested without access to your account/credits**. We do not silently fall back to rules if a paid AI call fails.

## Meta agreement intelligence (v0.4)

The new `app/engine.py` implementation requests **schema-constrained results** from `muse-spark-1.3` (Standard mode). It distinguishes proposals, questions, conditions, rejections, withdrawals, and ordinary messages. Only clear change proposals reach the approval screen. Evidence quotes must be literal substrings of the source message. Price additions and reductions are independently calculated in Python, not trusted from the model output. Changes still require both parties to approve and never alter earlier versions.

The implementation was tested against a mocked Meta API response, but **no live Meta API call was made as part of this package**. To test it locally, use sample data until you've confirmed billing and the free credits are active.

### Start with Meta AI without saving a key to disk

Close the current local server with Ctrl+C. From the project folder, run:

```powershell
uv run --python 3.13 --with-requirements requirements.txt python scripts/run_meta.py
```

When prompted, paste your Meta API key. The input is hidden and is only passed to the local server process; don't paste it in chat, screenshots, GitHub or `.env`. Open http://127.0.0.1:8000 and try one fictional example. The key is not stored by the launcher. The billing account must be unrestricted for API calls to succeed. To return to offline preview, stop this server and use your original `uv run ... uvicorn ...` command.

The default local allowance is **10 API attempts per UTC day**, with no automatic retries. `MAX_META_CALLS_PER_DAY` can be adjusted from 1 to 200. This is a *request counter*, **not a guaranteed monetary spending cap**. Monitor Meta's Billing page and never assume the $150 credit automatically prevents further charges.

### Testing

Run all offline tests with:

```powershell
uv run --python 3.13 --with-requirements requirements.txt python -m pytest -q
```

A labeled development set of 22 messages is included in `tests/fixtures/semantic_cases.jsonl`. See `scripts/evaluate_meta.py` for an explicit opt-in live evaluator (it will make paid API calls only with `--live`). The development set is intentionally small and cannot establish production reliability or a competitive advantage by itself.

**Security:** The browser's participant switcher still holds both sample participant keys in local storage. The app is for localhost demos only and must not be exposed to real people until separate authentication, secure invitations, privacy controls and production hardening are implemented. Do not upload real conversations while testing.

## Approved agreement documents (v0.3)

After both participants confirm, choose **View agreement** in the workspace. The document includes the current terms, reference, version and individual confirmation timestamps. Use **Print / Save PDF** to save or print the confirmed version. You may switch to earlier versions after an amendment; earlier approved terms are preserved from the agreement event history.

The document is a record of in-app confirmations, not verified identities or legal signatures. It requires a party access key and is deliberately unavailable before both people confirm. The existing local demo's dual-key switcher is not safe for production.

The v0.3 update ZIP replaces `app/main.py`, adds `app/documents.py`, and updates files in `web/` and `tests/`. Keep your existing `data/` folder when installing the update. Restart the server with your existing `uv run` command; no new Python dependencies are required.

## Interface update (v0.2)

The agreement workspace has a simplified header, cleaner terms and approvals, readable change comparisons, and human-readable activity. Technical details remain in the project documentation instead of the user interface.

For an existing local installation, replace the files in `web/` with the ones from the interface update ZIP. Keep your `data/` directory and `.env` unchanged, restart the local server, then refresh your browser with Ctrl+Shift+R. No dependency reinstall is needed.

To start the project using uv:

```powershell
uv run --python 3.13 --with-requirements requirements.txt uvicorn app.main:app --reload
```

The preview mode still uses sample data and is not a production-ready multi-user application.

## Local setup (Windows PowerShell)

1. Extract the downloaded ZIP and open PowerShell **inside** the `samepage-ai-hackathon` folder.
2. Install Python 3.10 or newer if it is not installed.
3. Run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. You can also use `python -m venv` if `py` is unavailable. If PowerShell blocks `Activate.ps1`, avoid changing your security policy: run `\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` instead.

**No API key, card, or Meta credits needed for the default offline demo.**

## Demonstrate the proof of concept

1. Create the prefilled sample: Amina and Bello; ₦120,000; Friday; repair vehicle engine.
2. As Amina, confirm initial terms. Switch to Bello and confirm the same terms.
3. Switch to Bello, submit: `I will finish on Monday. You'll need to add ₦40,000 for the extra work.`
4. The analyzer creates a **pending** change: price ₦160,000 and deadline Monday. The active agreement must remain unchanged.
5. Approve as Bello, switch to Amina and approve. Only now should version 2 become active.
6. Try a question such as `Could we finish on Tuesday?` — offline demo abstains rather than silently changing anything.
7. See the event history and hash verification indicator.

The local browser intentionally stores **both** test-party keys so judges can simulate two people. Never deploy this onboarding flow for real users. Use separate, secure invitations and authenticated accounts in production.

## Enable live Meta Muse Spark (after claiming credits)

Meta documentation: https://dev.meta.ai/docs/quickstart and https://dev.meta.ai/docs/cookbook/structured-output

Meta Model API:
- Base URL: `https://api.meta.ai/v1`
- Model: `muse-spark-1.3` (Standard, **not Contributor**)
- Auth environment variable: `MODEL_API_KEY`
- Structured JSON: `response_format={"type":"json_schema", ...}`

PowerShell, **in the terminal that starts the server**:

```powershell
$env:ANALYSIS_MODE = "meta"
$env:MODEL_API_KEY = "YOUR_REAL_META_MODEL_API_KEY"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For best security set the key in your environment/secret manager; **never put your secret key in the repository, browser code, screenshots or chat**. You must have valid billing and credits to call the API. Test with one case, monitor your billed usage, and avoid sharing private real-world agreements while evaluating the prototype. `max_completion_tokens=650`, 2.5k-character message cap, and zero automatic retries are enforced for the Meta analysis call. Billing alerts are not hard spending caps.

## Run tests

```powershell
python -m pytest -q
```

## Small evaluation fixture (not a performance claim)

```powershell
python -m scripts.evaluate_offline
```

This only evaluates the narrow deterministic offline rules against hand-authored cases. It is not a general accuracy benchmark or Meta-model result.

## Architecture

- `app/main.py`: FastAPI web and endpoints; per-party authorization by hashed local test keys.
- `app/engine.py`: clearly separated offline pattern demo and Meta structured-output analysis.
- `app/storage.py`: SQLite persistence, per-event SHA-256 hash chaining and audit verification.
- `web/`: responsive zero-build UI.
- `tests/`: unit/API tests (fake data; no external calls).
- `docs/`: project scope, limitations, proof-of-concept evaluation plan, hackathon submission requirements.

## Current features

- Create a two-party agreement with price, deadline and scope.
- Separate confirmations before active status.
- Offline or Meta-backed proposal extraction; proposed changes retain an evidence quote.
- Both-party approval; only then apply amendments to a new agreement version.
- Reject a proposal without mutating the current agreement.
- Serialized SQLite updates and protected read/write routes using party tokens.
- Local audit hash-chain validation, tests, ready-to-run local web UI.

## What this is NOT

- Not a legally binding contract or electronic-signature service.
- Not secure for public internet deployment: no account recovery, invite delivery, encryption at rest, independent signatures, rate limiting, web application security review, or production consent/privacy controls.
- Not yet supporting document uploads, WhatsApp integrations, audio, currencies other than NGN in offline mode, or other languages.
- Audit hash chains are **not tamper-proof** against an attacker who can edit the database and recompute hashes.
- Not a verified 1st-place product; accuracy and originality need measured evaluations.

The intended hackathon demonstration must **clearly disclose the analysis mode**. Do not show rule-based analysis as though it were Meta AI. For Meta-powered evaluation, switch to Meta mode and test live after credits are active.

## Publish to GitHub (public repository)

Use the **Source Control** icon in VS Code and select **Initialize Repository**. Review `.gitignore` first; it excludes local `data/`, `.env`, cache files and `.venv`. Stage the source files, commit with a meaningful message such as `Build SamePage agreement workflows`, then choose **Publish to GitHub** and select **Public**. Authorize VS Code when prompted.

Do not upload your SQLite database, API keys, actual users' conversations, or any private documents. A public repository is a requirement for the competition but does not make this local demo safe to deploy publicly.

## Agreement lifecycle update (v0.5)

The workflow now identifies the initiator and recipient. The initiator sends the initial offer and shares a private invitation link. The recipient accepts, declines, or sends a counteroffer. Once accepted, either participant can propose a manual amendment without Meta AI; both must still approve model-suggested amendments. The delivery-responsible participant can submit a completion statement and supporting reference, and the other participant reviews or disputes it.

The agreement document now distinguishes the original agreement from accepted revisions. This update migrates the existing SQLite schema without deleting previously created records.

See [Product workflow](docs/product-workflow.md) for permitted transitions, security limitations, and the difference between deterministic processing and Meta AI.

**Upgrade existing installations:** Extract the incremental update into the project root, replacing files inside `app`, `web`, `tests`, and `docs`. Keep your existing `data` folder. Restart the server with your usual `uv run` command. Do not upload `data`, `.env`, API keys, or access links to GitHub.
