# AI evidence review reliability

The Evidence Check button never decides acceptance. On API errors, SamePage now renders the error next to the clicked button, not only in the page-wide notice. The original delivery remains submitted for human review.

The Muse Spark 1.3 evidence response budget matches the conversation review budget (3500 completion tokens) to reduce the possibility of reasoning tokens exhausting the response. It does not automatically retry a failed paid request. The per-day Meta request cap remains active.

If the model returns no final content or reaches the token limit, the Python API returns a non-success status with a sanitized explanation. Server logs contain exception type/status/reason only, not uploaded screenshots, passwords or API keys.

Before retrying on VPS, check `journalctl -u samepage -n 80 --no-pager` and the `model_usage` table; repeated attempts may be blocked by `MAX_META_CALLS_PER_DAY`.
