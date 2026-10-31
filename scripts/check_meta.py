"""Check the configured Muse Spark agreement-analysis call without editing agreements."""
from __future__ import annotations

import getpass
import os

from app.engine import MetaResponseError, detect


CURRENT = {"price": "₦120,000", "deadline": "Friday", "scope": "Repair vehicle engine"}
MESSAGE = "I propose that we change the deadline to Monday."


def explain_failure(error: Exception) -> str:
    if isinstance(error, MetaResponseError):
        details = {
            "output_limit": "Muse reached the token limit before completing its answer. The app now requests more output tokens with low reasoning effort.",
            "missing_choice": "Meta returned no response choices. The request was not accepted as a usable result.",
            "empty_content": "Meta returned no visible answer. Check model access and response finish reason.",
            "invalid_json": "Meta returned text that was not valid JSON, despite the requested structured-output schema.",
            "unexpected_shape": "Meta returned JSON, but its top-level structure was not an object.",
            "invalid_content": "Meta returned JSON that did not pass the agreement-intent checks.",
        }
        return details.get(error.reason, "Meta returned an unsupported response shape.")
    status = getattr(error, "status_code", None)
    if status == 400:
        return "The API rejected the request format. Check the model and structured-output parameters."
    if status == 401:
        return "The API key was rejected. Create or verify an API key for the correct Meta project."
    if status == 402:
        return "Meta billing blocked the request. Check your payment verification and credit status."
    if status == 403:
        return "The key or team cannot access this model. Check account restrictions and model permissions."
    if status == 404:
        return "The requested model or endpoint was not found for this account."
    if status == 429:
        return "The API rate limit was reached. Avoid repeated requests until the limit resets."
    if status is not None and status >= 500:
        return "Meta returned a server error. Leave the application unchanged and try again later."
    name = type(error).__name__.lower()
    if "connection" in name or "timeout" in name:
        return "Meta could not be reached. Check internet access and connectivity."
    if "dailymeta" in name or "daily meta request allowance" in str(error).lower():
        return "SamePage's local daily request allowance has been reached. No further call was made."
    if isinstance(error, ValueError):
        return "The model response could not be validated. Check structured output and the evidence rules."
    return "An unexpected local integration error occurred. Check the server's private diagnostic logs."


def main() -> int:
    key = os.environ.get("MODEL_API_KEY", "").strip() or getpass.getpass("Meta API key (hidden): ").strip()
    if not key:
        print("No API key entered; no request was made.")
        return 2

    os.environ["MODEL_API_KEY"] = key
    os.environ["ANALYSIS_MODE"] = "meta"
    os.environ.setdefault("MAX_META_CALLS_PER_DAY", "10")
    print("Running one real Meta agreement-analysis request; no agreement data will be modified.")
    try:
        result = detect(MESSAGE, CURRENT)
    except Exception as error:
        status = getattr(error, "status_code", None)
        label = f"HTTP {status}" if status else type(error).__name__
        print(f"Result: FAILED ({label})")
        print(explain_failure(error))
        print("No agreement was changed. Do not paste your API key into screenshots or chat.")
        return 1

    print(f"Result: CONNECTED (analysis mode: {result.mode})")
    print(f"Interpretation: {result.intent}")
    print(f"Verified changes: {[(entry['field'], entry['new_value']) for entry in result.changes]}")
    if not result.changes:
        print("The request succeeded, but the proposed change was not verified. Review the analysis rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
