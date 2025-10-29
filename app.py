# app_min.py — minimal multi-turn Streamlit UI calling your public Function URL
import json, requests, streamlit as st
from typing import Dict, Any, List

st.set_page_config(page_title="Nori – KB RAG (Multi-turn)", page_icon="💬", layout="wide")
st.title("💬 Nori – Bedrock KB (user_id-filtered, multi-turn)")

with st.sidebar:
    api_url = st.text_input("Function URL (public)", value="", help="e.g., https://...lambda-url.ca-central-1.on.aws/")
    user_id = st.text_input("User ID (metadata filter)", value="userA")
    st.caption("This app POSTs {message, user_id, history[]} to your Lambda.")

def _format_sources(hits: List[Dict[str, Any]]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        text = (h.get("content") or {}).get("text", "") or ""
        snippet = (text[:600] + "…") if len(text) > 600 else text
        keys = ["source", "s3Uri", "doc_id", "user_id", "file", "title", "page", "language"]
        meta_bits = [f"{k}={meta[k]}" for k in keys if k in meta]
        lines.append(f"**#{i}**  {' | '.join(meta_bits)}\n\n{snippet}")
    return "\n\n---\n\n".join(lines) if lines else "_No sources returned_"

def _recent_history(msgs, max_pairs=6):
    buf = []
    for m in msgs:
        if m["role"] in ("user", "assistant"):
            buf.append({"role": m["role"], "content": m["content"]})
    return buf[-max_pairs*2:]  # last N pairs

if "msgs" not in st.session_state:
    st.session_state.msgs = []  # {"role": "user"/"assistant", "content": str, "meta": str|None}

# render history
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("meta"):
            with st.expander("Context / Sources"):
                st.markdown(m["meta"])

prompt = st.chat_input("Ask your coach…")
if prompt:
    if not api_url.strip():
        st.error("Provide the Function URL in the sidebar.")
        st.stop()

    # show user
    st.session_state.msgs.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    payload = {
        "message": prompt[:3000],
        "user_id": user_id.strip() or "userA",
        "history": _recent_history(st.session_state.msgs, max_pairs=6)
    }

    try:
        r = requests.post(api_url.strip(), headers={"Content-Type": "application/json"},
                          data=json.dumps(payload), timeout=60)
    except Exception as e:
        with st.chat_message("assistant"):
            st.error(f"Request failed: {type(e).__name__}: {e}")
        st.stop()

    # parse Lambda response (supports {"statusCode":..., "data": {...}} in body)
    answer, sources_md = "_No answer_", None
    if r.status_code == 200:
        try:
            js = r.json()
            data = js.get("data", js) if isinstance(js, dict) else {}
            answer = data.get("answer", answer)
            hits = data.get("retrievalResults", []) or []
            sources_md = _format_sources(hits)
        except Exception:
            answer = f"Non-JSON body:\n\n```\n{r.text[:1500]}\n```"
    else:
        err = r.text
        try:
            js = r.json(); data = js.get("data", js); err = data.get("error", err)
        except Exception: pass
        answer = f"Error {r.status_code}: {err}"

    with st.chat_message("assistant"):
        st.markdown(answer if answer else "_No answer_")
        if sources_md:
            with st.expander("Context / Sources"):
                st.markdown(sources_md)

    st.session_state.msgs.append({"role": "assistant", "content": answer, "meta": sources_md})
