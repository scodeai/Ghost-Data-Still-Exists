"""Optional LLM helper (Anthropic). Everything degrades gracefully to None when no API key is set,
so the deterministic pipeline always runs. The LLM is used ONLY for ambiguous text."""
import os, json, base64
_cache = {}
_client = None
MODEL = os.getenv("ORCH_MODEL", "claude-sonnet-5-5")
ENABLED = os.getenv("ORCH_NO_LLM", "") == ""


def available():
    global _client
    if not ENABLED or not os.getenv("ANTHROPIC_API_KEY"):
        return False
    if _client is None:
        try:
            import anthropic
            _client = anthropic.Anthropic()
        except Exception:
            return False
    return True


def _ask(system, user, key):
    if key in _cache:
        return _cache[key]
    if not available():
        return None
    try:
        r = _client.messages.create(model=MODEL, max_tokens=300, system=system,
                                    messages=[{"role": "user", "content": user}])
        txt = "".join(b.text for b in r.content if b.type == "text").strip()
        txt = txt.replace("```json", "").replace("```", "").strip()
        out = json.loads(txt)
    except Exception:
        out = None
    _cache[key] = out
    return out


def classify_intent(request_text):
    """-> 'DELETE' | 'NOT_DELETE' | None"""
    out = _ask('Classify a customer message. Reply ONLY JSON: {"intent":"DELETE"|"NOT_DELETE"}. '
               'DELETE = the person asks to delete/erase/close their account and data. '
               'NOT_DELETE = they cancel/withdraw a deletion, only want an export/copy, ask something else, or refuse deletion.',
               request_text[:2000], ("intent", request_text))
    return out.get("intent") if isinstance(out, dict) else None


def judge_condition(condition, record_text):
    """-> True/False/None: does the policy condition hold for this record?"""
    out = _ask('You apply a data-retention policy condition to a record. Reply ONLY JSON: {"holds": true|false}.',
               f"Condition: {condition}\nRecord: {record_text[:1500]}", ("cond", condition, record_text))
    return out.get("holds") if isinstance(out, dict) and isinstance(out.get("holds"), bool) else None


def evidence_state(text, category):
    """-> 'PRESENT' | 'REMOVED' | None for a piece of free-text evidence."""
    out = _ask('Decide whether the evidence shows the personal data still exists or was removed. '
               'Reply ONLY JSON: {"state":"PRESENT"|"REMOVED"}.',
               f"Category: {category}\nEvidence: {text[:2500]}", ("ev", category, text[:300]))
    return out.get("state") if isinstance(out, dict) else None


def ocr_image(path):
    if not available():
        return None
    try:
        data = base64.b64encode(open(path, "rb").read()).decode()
        ext = str(path).lower().rsplit(".", 1)[-1].replace("jpg", "jpeg")
        r = _client.messages.create(model=MODEL, max_tokens=1000, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": f"image/{ext}", "data": data}},
            {"type": "text", "text": "Transcribe all text in this image verbatim."}]}])
        return "".join(b.text for b in r.content if b.type == "text")
    except Exception:
        return None