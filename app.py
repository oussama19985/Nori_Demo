# app_min.py — minimal multi-turn Streamlit UI + intro FR + suggestions + reset
import json
import requests
import streamlit as st
from typing import Dict, Any, List

st.set_page_config(page_title="Nori – KB RAG (Multi-turn)", page_icon="💬", layout="wide")
st.title("💬 Nori – Beta")

# ----------------------------
# Config (from secrets only)
# ----------------------------
API_URL = (st.secrets.get("API_URL", "") or "").strip()
API_KEY = st.secrets.get("API_KEY", None)  # optional (x-api-key)

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:

    # user must fill this (no default from secrets)
    user_id = st.text_input("User ID (requis)", value="", placeholder="ex: userA")

    # reset chat
    if st.button("🧹 Nouvelle conversation", use_container_width=True):
        if "msgs" in st.session_state:
            del st.session_state["msgs"]
        st.toast("Conversation réinitialisée.")
        st.rerun()

    st.divider()
    if not API_URL:
        st.error("API_URL manquant dans .streamlit/secrets.toml")

# ----------------------------
# Utils
# ----------------------------
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
    return buf[-max_pairs * 2:]

# ----------------------------
# State + Intro
# ----------------------------
if "msgs" not in st.session_state:
    st.session_state.msgs = []

if not st.session_state.msgs:
    intro = (
        "Bonjour 👋, je suis **Nori**, ton coach IA pour la remise en forme, la nutrition et le sommeil.\n\n"
        "_Choisis un objectif pour commencer, ou pose ta question :_"
    )
    st.session_state.msgs.append({"role": "assistant", "content": intro, "meta": None})

# ----------------------------
# Render history
# ----------------------------
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("meta"):
            with st.expander("Contexte / Sources"):
                st.markdown(m["meta"])

# ----------------------------
# Suggestions
# ----------------------------
st.divider()
st.markdown("**Suggestions rapides :**")
suggestions = [
    "Objectif : masse musculaire",
    "Objectif : perte de poids",
    "Améliorer mon sommeil/énergie",
]
cols = st.columns(len(suggestions))
clicked_suggestion = None
for col, label in zip(cols, suggestions):
    if col.button(label, use_container_width=True, key=f"sugg_{label}"):
        clicked_suggestion = label

# ----------------------------
# Chat input
# ----------------------------
user_input = st.chat_input("Pose ta question…")
if clicked_suggestion and not user_input:
    user_input = clicked_suggestion

if user_input:
    if not API_URL:
        with st.chat_message("assistant"):
            st.error("Configuration invalide : API_URL manquant dans secrets.toml.")
    elif not user_id.strip():
        with st.chat_message("assistant"):
            st.error("Merci de renseigner un **User ID** dans la barre latérale.")
    else:
        # show user turn
        st.session_state.msgs.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        payload = {
            "message": user_input[:3000],
            "user_id": user_id.strip(),
            "history": _recent_history(st.session_state.msgs, max_pairs=6),
        }

        headers = {"Content-Type": "application/json"}
        if API_KEY:
            headers["x-api-key"] = API_KEY

        try:
            r = requests.post(API_URL, headers=headers, data=json.dumps(payload), timeout=60)
        except Exception as e:
            with st.chat_message("assistant"):
                st.error(f"Requête échouée : {type(e).__name__}: {e}")
        else:
            answer, sources_md = "_No answer_", None
            if r.status_code == 200:
                try:
                    js = r.json()
                    data = js.get("data", js) if isinstance(js, dict) else {}
                    answer = data.get("answer", answer)
                    hits = data.get("retrievalResults", []) or []
                    sources_md = _format_sources(hits)
                except Exception:
                    answer = f"Corps non-JSON :\n\n```\n{r.text[:1500]}\n```"
            else:
                err = r.text
                try:
                    js = r.json()
                    data = js.get("data", js)
                    err = data.get("error", err)
                except Exception:
                    pass
                answer = f"Erreur {r.status_code} : {err}"

            with st.chat_message("assistant"):
                st.markdown(answer if answer else "_No answer_")
                if sources_md:
                    with st.expander("Contexte / Sources"):
                        st.markdown(sources_md)

            st.session_state.msgs.append({"role": "assistant", "content": answer, "meta": sources_md})
