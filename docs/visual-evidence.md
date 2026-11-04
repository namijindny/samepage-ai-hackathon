# Visual evidence in SamePage (v1.1)

A small addition to the existing delivery checklist. Two people still control approvals.

## User experience

1. Person responsible for delivery writes a statement, attaches **up to two** screenshots (PNG/JPG/WebP, each under 2 MB) and optionally supplies a live website HTTPS URL.
2. The other participant sees private image previews alongside the criteria. They can simply accept or request a correction; they do **not** have to run AI.
3. Optionally click **Check evidence with AI**. Muse Spark 1.3 looks at the attached screenshots and the agreed criteria. If an HTTPS URL is present, the server checks limited public HTML text and passes it to the same model to identify possible inconsistencies.
4. AI returns: what the screenshot shows, what remains unverified, and one practical next check. **AI does not verify screenshot authenticity, render or test the public site, or decide acceptance.**
5. Rejected items can be resubmitted. Earlier evidence is retained and can be viewed by both participants.

## Security and limitations

- Files are decoded, validated and re-encoded as bounded JPEGs via Pillow, then stored in a private folder (default: `<SAMEPAGE_DB-parent>/evidence`), not `public_html`.
- Image endpoints require the correct per-party invitation key, plus the public-demo Basic login when enabled. File names are random, not user-controlled paths. Hashes are included in audit submissions.
- Only the reviewer can invoke evidence AI, and only when screenshots have been submitted. Repeated reviews of the same submission return the **cached result**, without another request or Meta cost.
- Public URL checking requires explicit URL entry and an explicit reviewer action. Only public HTTPS on port 443 is supported; credentials, redirects, private, loopback or reserved IP addresses are rejected. The connection is made to a previously verified public IP using TLS hostname verification, preventing a DNS-rebinding second lookup.
- Remote website text is untrusted input, and may represent a loading screen or SSR content rather than the dynamic page. No page scripts execute. No webpage screenshots are generated. Do not claim this checks live form submissions or proves that an image was not manipulated.
- Image analysis sends screenshot contents to Meta Model API when the reviewer clicks Check evidence with AI. Use synthetic examples for judging; obtain real participants' consent before production use.
- This is a password-protected hackathon demonstration, **not** production-grade identity verification or a legally binding contract platform.

## Deployment to existing Hostinger VPS

Upload `SamePage_v1.1_Visual_Evidence_Update.zip` to `/home/ashwarmediahausa-pro/samepage-deploy/` using CloudPanel File Manager.

As **root**, execute, one block at a time:

```bash
cd /home/ashwarmediahausa-pro/samepage-deploy
cp app/main.py app/main.py.backup-pre-v11
cp app/storage.py app/storage.py.backup-pre-v11
cp app/fulfilment.py app/fulfilment.py.backup-pre-v11
cp web/app.js web/app.js.backup-pre-v11
cp web/styles.css web/styles.css.backup-pre-v11
unzip -o SamePage_v1.1_Visual_Evidence_Update.zip
chown -R ashwarmediahausa-pro:ashwarmediahausa-pro app web requirements.txt
chown -R ashwarmediahausa-pro:ashwarmediahausa-pro docs tests 2>/dev/null || true
sudo -u ashwarmediahausa-pro /home/ashwarmediahausa-pro/samepage-deploy/.venv/bin/python -m pip install -r requirements.txt
/home/ashwarmediahausa-pro/samepage-deploy/.venv/bin/python -m py_compile app/main.py app/evidence.py app/storage.py app/fulfilment.py
systemctl restart samepage
systemctl is-active samepage
curl -s http://127.0.0.1:8010/healthz
```

The `samepage.env` credentials and SQLite database are **not** part of the update. No Nginx changes are needed. A private evidence directory will be created automatically in the same parent folder as `SAMEPAGE_DB` on the first image upload.

To inspect a failed service restart: `journalctl -u samepage -n 35 --no-pager`. Restore backup files and restart if necessary. Never paste `samepage.env` contents into chat or GitHub.

### Verify

Create a new **synthetic** agreement and checklist, then submit a small screenshot for one item. Ensure it previews for both participant sessions. The other person can optionally click **Check evidence with AI** (one budgeted Meta request), then dispute or accept. Test a resubmission and see **Previous screenshots**.

Existing completed items are unchanged and cannot be altered to add retroactive evidence.

## Keep GitHub synchronized

Install the patch into `C:\samepage-ai-hackathon`, then from its VS Code terminal:

```powershell
git status --short
git add app web requirements.txt tests docs README.md
git diff --cached --stat
git commit -m "Add privacy-protected visual evidence and public-page comparison"
git push origin main
```

Before committing, check the staged list and **never** include `.env`, API keys, private `data/`, `.sqlite3`, invitation links, or screenshots containing personal information. `git status` shows whether changes need to be staged. If the repo is private, change it to public only after reviewing it for secrets (GitHub Repository **Settings → General → Danger Zone → Change visibility**). The live VPS is a separate deployment; pushing GitHub alone does not update the server.

## Submission positioning

The Indie Developer criteria are creativity, technical ambition and functionality. Present this as **multimodal evidence assistance grounded in explicit acceptance criteria**, with deterministic two-person approval. Show real code, a live response, and the latest GitHub commit. Do not claim image forensic authenticity, production security, or automated functioning tests.
