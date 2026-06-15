"""Observability + mitigation layer around the opaque agent (a REAL LLM).

The simulator calls mitigate() for every request. The agent is SILENT -- the only place
latency/tokens/tool-calls/PII can be observed is here, via the FULL result that call_next()
returns to us. Legal moves used below:
  * prompt routing  -- guarantee our rewritten system prompt (solution/prompt.txt) is applied
                       on every request, independent of how the sim loads prompts;
  * input sanitise  -- neutralise instructions/fake prices embedded in order notes (injection);
  * retry / backoff -- recover from intermittent tool/transport errors;
  * caching         -- serve identical repeated questions without re-hitting the LLM;
  * PII redaction   -- strip any email/phone that slips into an answer (defence in depth);
  * structured logging/metrics -- our Day-13 telemetry, the only observability that exists.

The high-leverage fixes (grounding, exact arithmetic, tool economy, PII, injection defence)
live in solution/prompt.txt + solution/config.json; this layer makes them observable and robust.

  call_next(question, config) -> result   # the only way to reach the black box
  context = {"session_id","turn_index","qid","cache": <shared dict>, "cache_lock": <Lock>}
  result  = {"answer","status","steps","trace","meta":{latency_ms,usage,model,tools_used,...}}
"""
from __future__ import annotations
import os
import re
import time

# Day-13 telemetry toolkit (optional -- wrapper still runs without it).
try:
    from telemetry.logger import logger
    from telemetry.cost import cost_from_usage
    from telemetry.redact import redact
except Exception:  # pragma: no cover
    logger = None

    def cost_from_usage(model, usage):
        return 0.0

    def redact(s):
        return (s, 0)


# --- our rewritten system prompt, loaded once (robust to the sim's cwd) ---------------
_PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt.txt")
try:
    with open(_PROMPT_PATH, encoding="utf-8") as _fh:
        _SYSTEM_PROMPT = _fh.read().strip()
except Exception:
    _SYSTEM_PROMPT = ""


# --- injection defence: neutralise instructions/prices hidden in order notes ----------
_NOTE = re.compile(r"(?is)\bghi\s*ch[uú]\b\s*[:\-]?\s*(.*)$")
_SUSPICIOUS = re.compile(
    r"(?i)(system|h[eê]\s*th[oô]ng|ignore|b[oỏ]\s*qua|gi[aá]\s*[:=]|price|"
    r"=\s*\d|\d[\d.,]{3,}\s*(?:vnd|đ)|instruction|coupon|ma\s*gi[aả]m)"
)


def _sanitize(question):
    """Strip a 'GHI CHU'/note segment ONLY when it looks like an injected instruction or a
    fake price. Legitimate orders (no suspicious note) are returned untouched."""
    if not question:
        return question
    m = _NOTE.search(question)
    if m and _SUSPICIOUS.search(m.group(1) or ""):
        return (question[: m.start()] + " [ghi chu da bi loai bo: chua chi dan dang ngo]").strip()
    return question


def _is_bad(result):
    """A result worth retrying: missing, wrapper error, or no answer produced."""
    if result is None:
        return True
    if result.get("status") == "wrapper_error":
        return True
    if not result.get("answer"):
        return True
    return False


def mitigate(call_next, question, config, context):
    cache = context.get("cache")
    lock = context.get("cache_lock")

    safe_q = _sanitize(question)
    key = safe_q  # identical questions (e.g. repeated turns) share one agent call

    # --- prompt routing: force our rewritten system prompt on every request ---------
    conf = config
    if _SYSTEM_PROMPT:
        conf = dict(config)
        conf["system_prompt"] = _SYSTEM_PROMPT

    # --- cache: serve identical prior questions without hitting the LLM --------------
    if cache is not None and lock is not None:
        with lock:
            hit = cache.get(key)
        if hit is not None:
            return hit

    # --- call with retry/backoff (covers intermittent tool/transport errors) --------
    attempts = 3
    result = None
    t0 = time.time()
    for i in range(attempts):
        try:
            result = call_next(safe_q, conf)
        except Exception:
            result = None
        if not _is_bad(result):
            break
        if i < attempts - 1:
            time.sleep(0.2 * (i + 1))
    if result is None:
        result = {"answer": None, "status": "wrapper_error", "steps": 0, "trace": [], "meta": {}}

    wall_ms = int((time.time() - t0) * 1000)

    # --- output PII redaction (defence in depth; the prompt already forbids echoing) -
    pii_count = 0
    ans = result.get("answer")
    if isinstance(ans, str):
        red, pii_count = redact(ans)
        if pii_count:
            result = dict(result)
            result["answer"] = red

    # --- observability: the ONLY place these signals exist --------------------------
    meta = result.get("meta", {}) or {}
    usage = meta.get("usage", {}) or {}
    tools = meta.get("tools_used", []) or []
    if logger:
        try:
            logger.log_event("AGENT_CALL", {
                "qid": context.get("qid"),
                "session": context.get("session_id"),
                "turn": context.get("turn_index"),
                "status": result.get("status"),
                "latency_ms": meta.get("latency_ms"),
                "wall_ms": wall_ms,
                "usage": usage,
                "cost_usd": cost_from_usage(meta.get("model", ""), usage),
                "tools_used": tools,
                "n_tools": len(tools),
                "steps": result.get("steps"),
                "pii_redacted": pii_count,
                "sanitized_note": safe_q != question,
            })
        except Exception:
            pass

    # --- populate cache only for clean, successful answers --------------------------
    if cache is not None and lock is not None and result.get("status") == "ok" and result.get("answer"):
        with lock:
            cache.setdefault(key, result)

    return result
