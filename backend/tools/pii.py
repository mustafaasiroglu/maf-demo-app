"""
PII (Personally Identifiable Information) masking module.
Uses Azure AI Language PII Entity Recognition to detect and mask sensitive data
before sending user messages to the LLM.
"""

import os
import re
import json
import logging
import time
import requests
from contextvars import ContextVar
from typing import List, Tuple, Optional

# Context variable that holds PII replacements for the current request.
# Tool functions read this to unmask their parameters before execution.
_pii_replacements: ContextVar[List[Tuple[str, str]]] = ContextVar("_pii_replacements", default=[])


def set_pii_replacements(replacements: List[Tuple[str, str]]) -> None:
    """Store PII replacements in the current async context."""
    _pii_replacements.set(replacements)


def get_pii_replacements() -> List[Tuple[str, str]]:
    """Retrieve PII replacements from the current async context."""
    return _pii_replacements.get()


def unmask_value(value: str) -> str:
    """Unmask a single string value using current context replacements.
    
    Replaces mask placeholders (e.g. ``[[Person 1]]``) back to the original
    PII values so that tool functions receive plain-text parameters.
    """
    replacements = get_pii_replacements()
    if not replacements:
        return value
    for original, mask in replacements:
        value = value.replace(mask, original)
    return value


def _unmask_any(obj):
    """Recursively unmask all string values inside an arbitrary object."""
    if isinstance(obj, str):
        return unmask_value(obj)
    if isinstance(obj, list):
        return [_unmask_any(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _unmask_any(v) for k, v in obj.items()}
    return obj


def pii_unmask_args(func):
    """Decorator that unmasks PII placeholders in **all** arguments of *func*.

    When PII masking is active the LLM may pass masked values
    (e.g. ``[[Person 1]]``) as tool parameters.  This decorator transparently
    converts every string argument (including strings nested inside lists and
    dicts) back to the original plain-text value before the wrapped function
    executes, so individual tool implementations stay PII-agnostic.
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        new_args = tuple(_unmask_any(a) for a in args)
        new_kwargs = {k: _unmask_any(v) for k, v in kwargs.items()}
        return func(*new_args, **new_kwargs)

    return wrapper

logger = logging.getLogger(__name__)


def _get_pii_endpoint() -> str:
    """Read PII_ENDPOINT lazily so it picks up dotenv values."""
    return os.getenv("PII_ENDPOINT", "")


def _get_pii_key() -> str:
    """Read PII_KEY lazily so it picks up dotenv values."""
    return os.getenv("PII_KEY", "")

PII_CONFIDENCE_THRESHOLD = 0.80

PII_CATEGORIES = [
    "Person",
    "TRNationalIdentificationNumber",
    "Email",
    "Address",
    "Organization",
    "Age",
    "CreditCardNumber",
]

# Turkish number words for masking
_TURKISH_NUMBER_WORDS = [
    "bir", "iki", "üç", "dört", "beş", "altı", "yedi",
    "sekiz", "dokuz", "on", "yüz", "bin", "milyon",
    "milyar", "trilyon",
]


def mask_numbers(text: str) -> str:
    """Replace digit sequences and Turkish number words with [[Number]]."""
    text = re.sub(r'(\d[\d\s.\-]*\d)+', lambda _: "[[Number]]", text)
    for word in _TURKISH_NUMBER_WORDS:
        text = re.sub(r'\b' + word + r'\b', lambda _: "[[Number]]", text)
    return text


def _preprocess_text(text: str) -> str:
    """Sentence-case words that are fully UPPERCASE (longer than 1 char)."""
    def _fix(match: re.Match) -> str:
        word = match.group(0)
        if len(word) > 1 and word.isupper():
            return word.capitalize()
        return word
    return re.sub(r'\b\w+\b', _fix, text)


def analyze_text(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Send *text* to Azure PII Entity Recognition and return
    ``(masked_text, replacements)`` where *replacements* is a list of
    ``(original_value, mask_placeholder)`` pairs so the caller can later
    reverse the masking on the LLM response.

    If the PII service is unreachable or not configured the original text is
    returned unchanged with an empty replacement list.
    """
    pii_endpoint = _get_pii_endpoint()
    pii_key = _get_pii_key()
    if not pii_endpoint or not pii_key:
        logger.warning("PII endpoint/key not configured – skipping PII masking")
        return text, []

    # text = _preprocess_text(text)

    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": pii_key,
    }

    body = {
        "kind": "PiiEntityRecognition",
        "parameters": {
            "modelVersion": "latest",
            "piiCategories": PII_CATEGORIES,
        },
        "analysisInput": {
            "documents": [
                {
                    "id": "1",
                    "language": "tr",
                    "text": text,
                }
            ]
        },
    }

    try:
        response = requests.post(
            pii_endpoint, headers=headers, data=json.dumps(body), timeout=10
        )
    except requests.RequestException as exc:
        logger.error("PII service request failed: %s", exc)
        return text, []

    if response.status_code != 200:
        logger.error(
            "PII service returned status %s: %s", response.status_code, response.text
        )
        return text, []

    response_json = response.json()
    doc = response_json["results"]["documents"][0]
    redacted_text: str = doc["redactedText"]
    entities = doc["entities"]

    cat_counts: dict[str, int] = {}
    txt_parts: list[str] = []
    replacements: list[tuple[str, str]] = []
    start = 0

    for entity in entities:
        before = redacted_text[start : entity["offset"]]
        score = entity.get("confidenceScore", 1.0)
        if score < PII_CONFIDENCE_THRESHOLD:
            # Low confidence – restore the original text instead of masking
            logger.info(
                "PII entity '%s' (%s) skipped: confidence %.2f < %.2f",
                entity["text"], entity["category"], score, PII_CONFIDENCE_THRESHOLD,
            )
            txt_parts.append(mask_numbers(before) + entity["text"])
        else:
            cat = entity["category"]
            subcat = ":" + entity["subcategory"] if "subcategory" in entity else ""
            allcat = cat + subcat
            cat_counts[allcat] = cat_counts.get(allcat, 0) + 1
            mask = f"[[{allcat} {cat_counts[allcat]}]]"
            txt_parts.append(mask_numbers(before) + mask)
            replacements.append((entity["text"], mask))
        start = entity["offset"] + entity["length"]

    masked_text = "".join(txt_parts) + mask_numbers(redacted_text[start:])
    return masked_text, replacements


def analyze_text_with_details(text: str) -> dict:
    """
    Like :func:`analyze_text` but returns a rich diagnostic dict::

        {
            "masked_text": str,
            "replacements": [(original, mask), ...],
            "status": "ok" | "skipped" | "error",
            "detail": str | None,          # human-readable reason on non-ok
            "http_status": int | None,
            "entities_found": int,
        }
    """
    start_time = time.time()

    result: dict = {
        "masked_text": text,
        "replacements": [],
        "status": "ok",
        "detail": None,
        "http_status": None,
        "entities_found": 0,
        "duration_ms": 0,
        "request_body": None,
        "response_body": None,
    }

    pii_endpoint = _get_pii_endpoint()
    pii_key = _get_pii_key()
    if not pii_endpoint or not pii_key:
        result["status"] = "skipped"
        result["detail"] = "PII_ENDPOINT or PII_KEY environment variable is not set"
        result["duration_ms"] = round((time.time() - start_time) * 1000, 2)
        logger.warning(result["detail"])
        return result

    preprocessed = _preprocess_text(text)

    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": pii_key,
    }

    body = {
        "kind": "PiiEntityRecognition",
        "parameters": {
            "modelVersion": "latest",
            "piiCategories": PII_CATEGORIES,
        },
        "analysisInput": {
            "documents": [
                {
                    "id": "1",
                    "language": "tr",
                    "text": preprocessed,
                }
            ]
        },
    }

    result["request_body"] = body

    try:
        response = requests.post(
            pii_endpoint, headers=headers, data=json.dumps(body), timeout=10
        )
    except requests.RequestException as exc:
        result["status"] = "error"
        result["detail"] = f"PII service request failed: {exc}"
        result["duration_ms"] = round((time.time() - start_time) * 1000, 2)
        logger.error(result["detail"])
        return result

    result["http_status"] = response.status_code

    if response.status_code != 200:
        result["status"] = "error"
        result["detail"] = f"PII service returned HTTP {response.status_code}: {response.text[:500]}"
        result["response_body"] = response.text[:2000]
        result["duration_ms"] = round((time.time() - start_time) * 1000, 2)
        logger.error(result["detail"])
        return result

    response_json = response.json()
    result["response_body"] = response_json
    doc = response_json["results"]["documents"][0]
    redacted_text: str = doc["redactedText"]
    entities = doc["entities"]
    result["entities_found"] = len(entities)

    cat_counts: dict[str, int] = {}
    txt_parts: list[str] = []
    replacements: list[tuple[str, str]] = []
    start = 0

    for entity in entities:
        before = redacted_text[start : entity["offset"]]
        score = entity.get("confidenceScore", 1.0)
        if score < PII_CONFIDENCE_THRESHOLD:
            # Low confidence – restore the original text instead of masking
            logger.info(
                "PII entity '%s' (%s) skipped: confidence %.2f < %.2f",
                entity["text"], entity["category"], score, PII_CONFIDENCE_THRESHOLD,
            )
            txt_parts.append(mask_numbers(before) + entity["text"])
        else:
            cat = entity["category"]
            subcat = ":" + entity["subcategory"] if "subcategory" in entity else ""
            allcat = cat + subcat
            cat_counts[allcat] = cat_counts.get(allcat, 0) + 1
            mask = f"[[{allcat} {cat_counts[allcat]}]]"
            txt_parts.append(mask_numbers(before) + mask)
            replacements.append((entity["text"], mask))
        start = entity["offset"] + entity["length"]

    result["masked_text"] = "".join(txt_parts) + mask_numbers(redacted_text[start:])
    result["replacements"] = replacements
    result["duration_ms"] = round((time.time() - start_time) * 1000, 2)
    return result


def unmask_response(response_text: str, replacements: List[Tuple[str, str]]) -> str:
    """
    Restore original PII values in the LLM *response_text* by reversing the
    mask placeholders produced by :func:`analyze_text`.
    """
    for original, mask in replacements:
        response_text = response_text.replace(mask, original)
    return response_text
