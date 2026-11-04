# Evidence-review UX correction

- Screenshot thumbnails use authenticated, short-lived browser object URLs; the Content Security Policy now explicitly permits `blob:` images. Private evidence remains behind both SamePage access checks and the demo gate.
- The reviewing participant sees an animated busy state while the backend is reviewing evidence. The indicator deliberately has no percentage or staged completion estimates because the server does not expose real-time analysis stages.
- The responsible participant sees **Submit work for review** only on unsubmitted or disputed deliverables. After acceptance/completion, the record is read-only and clearly explains why no submit button appears.
- The Meta prompt no longer invites a mockup inference based merely on polished design, cropping or a phone frame. An image alone cannot establish authenticity, and a screenshot alone cannot verify actual functionality.
- Previous saved AI insights and agreement audit history are not changed. The improved instructions apply to subsequent checks on new evidence submissions.

## Deployment

Update `app/main.py`, `app/evidence.py`, `web/app.js`, and `web/styles.css` in the local Git repository and Hostinger VPS. No database migrations or new dependencies. Keep `SAMEPAGE_DB`, demo credentials and API keys unchanged.

Local verification: `uv run --python 3.13 --with-requirements requirements.txt python -m pytest -q`.

VPS: after uploading the ZIP into `~/samepage-deploy`, extract only the four runtime files, preserve ownership, and restart the `samepage` systemd service. The health endpoint should return `{\"ok\":true}`. If the browser still shows old styles, use Ctrl+Shift+R.
