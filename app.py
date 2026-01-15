# app_min.py — Streamlit chat UI with User ID + Studio ID selectors (required)
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
API_KEY = st.secrets.get("API_KEY", None)

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar:
    st.markdown("### Paramètres")

    user_id = st.text_input("User ID (requis)", value="userA", placeholder="ex: userA")
    studio_id = st.text_input("Studio ID (requis)", value="1001", placeholder="ex: 1001")

    if st.button("🧹 Nouvelle conversation", use_container_width=True):
        st.session_state.clear()
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

        keys = [
            "layer", "studio_id", "user_id", "doc_type",
            "x-amz-bedrock-kb-source-uri", "x-amz-bedrock-kb-document-page-number",
            "source", "title", "language"
        ]
        meta_bits = [f"{k}={meta[k]}" for k in keys if k in meta]

        lines.append(f"**#{i}**  {' | '.join(meta_bits)}\n\n{snippet}")

    return "\n\n---\n\n".join(lines) if lines else "_No sources returned_"

def _recent_history(msgs: List[Dict[str, Any]], max_pairs: int = 6) -> List[Dict[str, str]]:
    buf = []
    for m in msgs:
        if m.get("role") in ("user", "assistant"):
            buf.append({"role": m["role"], "content": m.get("content", "")})
    return buf[-max_pairs * 2:]

def _merge_hits(api_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Your Lambda returns retrievalResults_studio + retrievalResults_user.
    Keep backward compatibility if only retrievalResults exists.
    """
    hits: List[Dict[str, Any]] = []
    if isinstance(api_data.get("retrievalResults_studio"), list):
        hits.extend(api_data.get("retrievalResults_studio") or [])
    if isinstance(api_data.get("retrievalResults_user"), list):
        hits.extend(api_data.get("retrievalResults_user") or [])
    if not hits:
        hits = api_data.get("retrievalResults", []) or []
    return hits

# ----------------------------
# State initialization
# ----------------------------
if "msgs" not in st.session_state:
    st.session_state.msgs = []

if "suggestions_used" not in st.session_state:
    st.session_state.suggestions_used = False

if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

# ----------------------------
# Intro message
# ----------------------------
if not st.session_state.msgs:
    st.session_state.msgs.append({
        "role": "assistant",
        "content": (
            "Bonjour 👋, je suis **Nori**, ton coach IA pour la remise en forme, "
            "la nutrition et le sommeil.\n\n"
            "_Choisis un objectif pour commencer, ou pose ta question :_"
        ),
        "meta": None
    })

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
# One-time suggestions
# ----------------------------
if not st.session_state.suggestions_used:
    st.divider()
    st.markdown("**Suggestions rapides :**")

    suggestions = [
        "Objectif : masse musculaire",
        "Objectif : perte de poids",
        "Améliorer mon sommeil/énergie",
    ]
    cols = st.columns(len(suggestions))
    for col, label in zip(cols, suggestions):
        if col.button(label, use_container_width=True, key=f"sugg_{label}"):
            st.session_state.pending_input = label
            st.session_state.suggestions_used = True
            st.rerun()

# ----------------------------
# Chat input (manual or suggestion)
# ----------------------------
user_input = st.chat_input("Pose ta question…")

# suggestion click has priority
if st.session_state.pending_input:
    user_input = st.session_state.pending_input
    st.session_state.pending_input = None

if user_input:
    st.session_state.suggestions_used = True

    if not API_URL:
        with st.chat_message("assistant"):
            st.error("Configuration invalide : API_URL manquant dans secrets.toml.")
            st.stop()

    if not user_id.strip() or not studio_id.strip():
        with st.chat_message("assistant"):
            st.error("Merci de renseigner un **User ID** et un **Studio ID** dans la barre latérale.")
            st.stop()

    # show user message
    st.session_state.msgs.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    payload = {
        "message": user_input[:3000],
        "user_id": user_id.strip(),
        "studio_id": studio_id.strip(),
        "history": _recent_history(st.session_state.msgs),
    }

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["x-api-key"] = API_KEY

    # assistant response + spinner
    with st.chat_message("assistant"):
        with st.spinner("Nori réfléchit…"):
            try:
                r = requests.post(
                    API_URL,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=60,
                )
            except Exception as e:
                st.error(f"Requête échouée : {type(e).__name__}: {e}")
                st.stop()

        answer = "_No answer_"
        sources_md = None

        if r.status_code == 200:
            try:
                js = r.json()
                data = js.get("data", js)

                answer = data.get("answer", answer)
                hits = _merge_hits(data)
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

        st.markdown(answer)
        if sources_md:
            with st.expander("Contexte / Sources"):
                st.markdown(sources_md)

    st.session_state.msgs.append({
        "role": "assistant",
        "content": answer,
        "meta": sources_md
    })
