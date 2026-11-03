# Deploy SamePage to Railway (restricted hackathon demonstration)

This is a **password-protected, sample-data-only demonstration**, not a production agreement service. Real identity verification, role-based accounts, user isolation, encrypted document storage, and abuse controls remain out of scope.

## Before deployment

1. Run the existing tests: `uv run --python 3.13 --with-requirements requirements.txt python -m pytest -q`.
2. Run the local delivery proof: `uv run --python 3.13 --with-requirements requirements.txt python -m scripts.prove_delivery`.
3. Verify the repository does not contain `.env`, API secrets, databases, private agreement records or ZIP archives (including **Git history**, not just current files). Rotate any credential that has been committed.
4. Push the new `Dockerfile`, `.dockerignore`, `app/main.py`, `web/app.js`, `tests/test_public_demo.py`, and this documentation to your GitHub repository.

## Railway dashboard setup

1. Sign in at `https://railway.com/`, create a **New Project**, and deploy **from GitHub Repo** `namijindny/samepage-ai-hackathon`. Authorize the GitHub repository if prompted. Railway automatically detects the root `Dockerfile`.
2. Under the new service, **attach a persistent volume** mounted at the exact path `/data`. Without it, SQLite agreements and the per-day Meta call allowance may reset after redeployment. Configure a single replica; this SQLite demo is not intended for horizontal scaling.
3. Under **Variables**, set:

   | Name | Value |
   | --- | --- |
   | `PUBLIC_DEMO` | `1` |
   | `DEMO_USERNAME` | `judge` |
   | `DEMO_PASSWORD` | A new unique randomly generated password, **at least 16 characters** |
   | `SAMEPAGE_DB` | `/data/samepage.sqlite3` |
   | `ANALYSIS_MODE` | `meta` |
   | `MODEL_API_KEY` | Your **private** Meta Model API key |
   | `MAX_META_CALLS_PER_DAY` | `5` (initially) |

   Do not enter credentials in GitHub, the README, an issue, or screenshots. Use Railway's secret variables. Railway supplies `PORT` automatically. The Dockerfile starts one Uvicorn worker on that port.
4. Deploy the staged changes; check the service's deploy logs and the private health check **`/healthz`** (does not reveal agreement data; the route itself is public for monitoring).
5. Go to service **Settings → Networking → Generate Domain** (the naming of settings may change). The generated HTTPS URL should ask for the demo username and password in your browser. If not, **do not share the domain**.
6. Open the application, create a synthetic agreement, copy the recipient's invitation and test it in an Incognito browser session. Use only imaginary names, prices and messages. Test one real conversation review, then monitor Meta billing and remaining free credits.
7. Provide the restricted demo URL and **separate test username/password** to the judges through the competition's submission fields if permitted. Do not post the demo password publicly. If the platform has no appropriate private access field, record the full demo video as the primary proof and request an authorized route for judge access rather than exposing an unprotected app.
8. After the event, disable the deployment or rotate/remove its credentials and API key.

## Verify security before sharing

- An unauthenticated visit to the URL returns HTTP 401 with a browser password prompt.
- API routes including `/api/health` and `/api/cases` must also require the **same** password.
- HTTPS must be enabled; never enter Basic credentials over plain HTTP on the internet.
- Only `/healthz` is accessible without the password.
- The app's party invitation keys are **not identity-verified login credentials**. This demo has a separate shared outer access password and accepts **synthetic data only**.
- The server enforces a daily attempt count but this is **not a guaranteed monetary cost cap**. Check Meta billing.
- If the Railway free trial is network-restricted, outbound calls to the Meta Model API might fail. Confirm successful Meta requests after deployment. Review Railway plan terms before adding payment information.

## Problems to avoid

- **502 / app won't start:** Check Railway deploy logs. `PUBLIC_DEMO=1` requires a valid demo password and `SAMEPAGE_DB`, and Meta mode requires `MODEL_API_KEY`.
- **Agreements disappear:** Make sure the Railway volume is truly mounted at `/data`, and `SAMEPAGE_DB` is `/data/samepage.sqlite3`.
- **Public domain opens without authentication:** Stop and check `PUBLIC_DEMO=1` on the deployed service.
- **Meta calls fail:** Check API key permissions, billing availability, outbound network access, daily quota and service logs; never print the secret.
- **Browser remembers an old invite:** Use an Incognito window or different browser profile for the other participant.

## Submission facts

- Submit the **public source repository** after reviewing Git history for sensitive information. A private GitHub repository does not satisfy the organizer rule.
- Submit the working demonstration and the **required three-minute video** by **November 4, 2026 at 9 PM ET** (November 5 at 3 AM WAT).
- Do not claim independent real-world evidence verification or legally binding e-signatures. The delivery engine records what participants submitted and approved; it does not prove the work actually happened.
