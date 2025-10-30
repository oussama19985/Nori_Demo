# app_min.py — minimal multi-turn Streamlit UI + intro FR + boutons de suggestions + reset
import json
import requests
import streamlit as st
from typing import Dict, Any, List

st.set_page_config(page_title="Nori – KB RAG (Multi-turn)", page_icon="💬", layout="wide")
st.title("💬 Nori – Beta")

# ----------------------------
# Sidebar (réglages rapides)
# ----------------------------
with st.sidebar:
    api_url = st.text_input(
        "Function URL (public)",
        value=st.secrets.get("API_URL", ""),
        help="e.g., https://...lambda-url.ca-central-1.on.aws/"
    )
    user_id = st.text_input("User ID (pour le filtre metadata)", value=st.secrets.get("USER_ID", "userA"))
    st.caption("L’app envoie {message, user_id, history[]} à votre Lambda.")

    # 🔁 Reset chat button (no page refresh needed)
    if st.button("🧹 Nouvelle conversation", use_container_width=True):
        if "msgs" in st.session_state:
            del st.session_state["msgs"]      # clear only the conversation
        st.toast("Conversation réinitialisée.")
        st.rerun()                            # re-run so the intro message shows again

    st.divider()
    st.caption("Astuce : ajoute API_URL / USER_ID / API_KEY dans .streamlit/secrets.toml si besoin.")

API_KEY = st.secrets.get("API_KEY", None)  # optionnel (x-api-key)

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
    return buf[-max_pairs*2:]  # dernières paires

# ----------------------------
# State + Intro du coach
# ----------------------------
if "msgs" not in st.session_state:
    st.session_state.msgs = []  # {"role": "user"/"assistant", "content": str, "meta": str|None}

# Injecter une salutation initiale si aucune conversation
if not st.session_state.msgs:
    intro = (
        "Bonjour 👋, je suis **Nori**, ton coach IA pour la remise en forme, la nutrition et le sommeil.\n\n"
        "Je peux utiliser tes données (si disponibles) pour personnaliser mes conseils. "
        "Sinon, je te poserai quelques questions ciblées pour adapter le plan.\n\n"
        "_Choisis un objectif pour commencer, ou pose ta question :_"
    )
    st.session_state.msgs.append({"role": "assistant", "content": intro, "meta": None})

# ----------------------------
# Rendu de l'historique
# ----------------------------
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("meta"):
            with st.expander("Contexte / Sources"):
                st.markdown(m["meta"])

# ----------------------------
# Boutons de suggestions (quick start)
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
# Saisie chat ou clic suggestion
# ----------------------------
user_input = st.chat_input("Pose ta question…")
if clicked_suggestion and not user_input:
    user_input = clicked_suggestion

if user_input:
    if not api_url.strip():
        with st.chat_message("assistant"):
            st.error("Merci d’indiquer la Function URL (public) dans la barre latérale.")
    else:
        # Afficher le tour utilisateur
        st.session_state.msgs.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Construire la charge utile avec historique
        payload = {
            "message": user_input[:3000],
            "user_id": (user_id or "userA").strip(),
            "history": _recent_history(st.session_state.msgs, max_pairs=6),
        }

        headers = {"Content-Type": "application/json"}
        if API_KEY:
            headers["x-api-key"] = API_KEY  # si tu as mis un petit gate côté Lambda

        # Appel HTTP
        try:
            r = requests.post(api_url.strip(), headers=headers, data=json.dumps(payload), timeout=60)
        except Exception as e:
            with st.chat_message("assistant"):
                st.error(f"Requête échouée : {type(e).__name__}: {e}")
        else:
            # Parsing de la réponse Lambda
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
                    js = r.json(); data = js.get("data", js); err = data.get("error", err)
                except Exception:
                    pass
                answer = f"Erreur {r.status_code} : {err}"

            with st.chat_message("assistant"):
                st.markdown(answer if answer else "_No answer_")
                if sources_md:
                    with st.expander("Contexte / Sources"):
                        st.markdown(sources_md)

            st.session_state.msgs.append({"role": "assistant", "content": answer, "meta": sources_md})
