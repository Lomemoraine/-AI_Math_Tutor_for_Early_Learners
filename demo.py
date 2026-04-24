"""
demo.py
Gradio child-facing demo for AI Math Tutor.
Run: python demo.py
"""

import json
from urllib import response
import gradio as gr
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from tutor.curriculum_loader import CurriculumLoader
from tutor.adaptive import BKTTracker, EloTracker, AdaptiveSelector
from tutor.lang_detect import detect_language, extract_numeric_answer, build_feedback, get_reply_language
from tutor.store import ProgressStore

SEED_PATH = "T3.1_Math_Tutor/curriculum_seed.json"

# ---------------------------------------------------------------------------
# Global state (single-session demo — multi-learner handled via learner_id)
# ---------------------------------------------------------------------------
loader = CurriculumLoader(SEED_PATH)
store = ProgressStore()

_sessions = {}  # learner_id → {bkt, elo, selector, session_id, current_item, lang}

EMOJI_SKILLS = {
    "counting": "🔢",
    "number_sense": "🧠",
    "addition": "➕",
    "subtraction": "➖",
    "word_problem": "📖",
}

WELCOME = {
    "en": "👋 Hello! I am your Math Tutor.",
    "fr": "👋 Bonjour! Je suis ton tuteur de maths. Comment t'appelles-tu?",
    "kin": "👋 Muraho! Ndi umwarimu wawe w'imibare. ",
}

SILENCE_PROMPT = {
    "en": "🤔 Take your time! Try saying the number out loud, or type it below. No worries!",
    "fr": "🤔 Prends ton temps! Essaie de dire le nombre, ou écris-le ci-dessous.",
    "kin": "🤔 Fata umwanya! Gerageza kuvuga umubare, cyangwa uwandike hepfo.",
}


def _get_or_create_session(learner_id: str, lang: str):
    if learner_id not in _sessions:
        store.register_learner(learner_id)
        bkt_dict = store.load_bkt_state(learner_id)
        bkt = BKTTracker.from_dict(bkt_dict) if bkt_dict else BKTTracker()
        elo = EloTracker()
        selector = AdaptiveSelector(loader.items)
        sid = store.start_session(learner_id, lang)
        _sessions[learner_id] = {
            "bkt": bkt, "elo": elo, "selector": selector,
            "session_id": sid, "current_item": None, "lang": lang,
            "awaiting_name": False,
        }
    return _sessions[learner_id]


def _present_item(session: dict) -> str:
    lang = session["lang"]
    item = session["selector"].select(session["bkt"], lang)
    session["current_item"] = item
    skill_emoji = EMOJI_SKILLS.get(item["skill"], "📐")
    stem_key = f"stem_{lang}"
    stem = item.get(stem_key) or item.get("stem_en", "")
    diff_stars = "⭐" * min(5, max(1, item["difficulty"] // 2))
    return (
        f"{skill_emoji} **{item['skill'].replace('_',' ').title()}** {diff_stars}\n\n"
        f"**{stem}**\n\n"
        f"_(Type your answer below)_"
    )


def _mastery_bar(p: float) -> str:
    filled = int(p * 10)
    return "█" * filled + "░" * (10 - filled) + f" {int(p*100)}%"


def _progress_display(session: dict) -> str:
    profile = session["bkt"].mastery_profile()
    lines = ["**📊 Your Progress:**\n"]
    for skill, p in profile.items():
        emoji = EMOJI_SKILLS.get(skill, "📐")
        lines.append(f"{emoji} {skill.replace('_',' ').title():15s} {_mastery_bar(p)}")
    return "\n".join(lines)


def chat(user_message: str, history: list, learner_id: str, lang: str):
    learner_id = learner_id.strip() or "learner_001"
    lang = lang or "en"
    session = _get_or_create_session(learner_id, lang)

    if not user_message.strip():
        response = SILENCE_PROMPT.get(lang, SILENCE_PROMPT["en"])
        if session["current_item"] is None:
            response += "\n\n" + _present_item(session)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response})
        return history, ""
    
    # First interaction
    if session["current_item"] is None and len(history) == 0:
        greeting = WELCOME.get(lang, WELCOME["en"])
        first_item = _present_item(session)
        response = greeting + "\n\n" + first_item
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response})
        return history, ""

    # Check if this is a name response (first message)
    if len(history) <= 1 and session["current_item"] is None:
        first_item = _present_item(session)
        response = f"Nice to meet you, **{user_message.title()}**! 😊\n\nLet's start!\n\n{first_item}"
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response})
        return history, ""

    # --- Answer processing ---
    item = session["current_item"]
    if item is None:
        item_str = _present_item(session)
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content":  item_str})
        return history, ""

    # Language detection
    detection = detect_language(user_message)
    reply_lang = get_reply_language(detection, fallback=lang)

    # Extract numeric answer
    numeric_ans = extract_numeric_answer(user_message)
    correct_ans = item.get("answer_int")

    if numeric_ans is None:
        # Can't parse — ask again in dominant language
        prompts = {
            "en": f"Hmm, I didn't catch that! Try typing just the number. 😊",
            "fr": f"Hmm, je n'ai pas compris! Essaie d'écrire juste le chiffre. 😊",
            "kin": f"Hmm, sinabibonye! Gerageza kwandika umubare gusa. 😊",
        }
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": prompts.get(reply_lang, prompts["en"])})
        return history, ""

    correct = (numeric_ans == correct_ans)

    # Update BKT + Elo
    session["bkt"].update(item["skill"], correct)
    session["elo"].update(item["skill"], item["difficulty"], correct)

    # Log to store
    store.log_response(learner_id, item["id"], item["skill"],
                       item["difficulty"], correct, reply_lang)

    # Save BKT state
    store.save_bkt_state(learner_id, session["bkt"].to_dict())

    # Build feedback
    feedback = build_feedback(correct, reply_lang, correct_ans)

    # Progress display every 5 responses
    total_responses = sum(
        st.n_attempts for st in session["bkt"].states.values()
    )
    progress_str = ""
    if total_responses % 5 == 0 and total_responses > 0:
        progress_str = "\n\n" + _progress_display(session)

    # Select next item
    session["current_item"] = None
    next_item_str = _present_item(session)

    response = f"{feedback}{progress_str}\n\n---\n\n{next_item_str}"
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": response})
    return history, ""


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------
def build_ui():
    with gr.Blocks(
        title="🧮 AI Math Tutor",
        theme=gr.themes.Soft(), # type: ignore
        css="""
        .gradio-container { max-width: 800px; margin: auto; }
        .chatbot { font-size: 1.1em; }
        footer { display: none !important; }
        """
    ) as demo:
        gr.Markdown(
            """
            # 🧮 AI Math Tutor for Early Learners
            Welcome to the AI Math Tutor demo! This interactive tutor adapts to your learning needs, providing personalized math problems and feedback in multiple languages.---
            """
        )

        with gr.Row():
            learner_id_box = gr.Textbox(
                label="👤 Learner ID",
                placeholder="e.g. child_001",
                value="child_001",
                scale=2,
            )
            lang_box = gr.Dropdown(
                label="🌍 Language",
                choices=[("English", "en"), ("Français", "fr"), ("Ikinyarwanda", "kin")],
                value="kin",
                scale=1,
            )

        chatbot = gr.Chatbot(
            label="Math Tutor",
            height=420,
            show_label=True,
            elem_classes=["chatbot"],
        )

        with gr.Row():
            msg_box = gr.Textbox(
                placeholder="Type your answer here... (e.g. 5, five, eshanu, cinq)",
                label="Your Answer",
                scale=5,
                autofocus=True,
            )
            send_btn = gr.Button("Send ➤", scale=1, variant="primary")

        with gr.Row():
            clear_btn = gr.Button("🔄 New Session", scale=1)
            progress_btn = gr.Button("📊 Show Progress", scale=1)

        progress_box = gr.Markdown(visible=False)

        # Event handlers
        def submit(msg, history, lid, lang):
            return chat(msg, history, lid, lang)

        def show_progress(lid, lang):
            lid = lid.strip() or "child_001"
            session = _get_or_create_session(lid, lang)
            text = _progress_display(session)
            return gr.update(value=text, visible=True)

        def clear_session(lid):
            if lid in _sessions:
                del _sessions[lid]
            return [], gr.update(visible=False)

        msg_box.submit(submit, [msg_box, chatbot, learner_id_box, lang_box],
                       [chatbot, msg_box])
        send_btn.click(submit, [msg_box, chatbot, learner_id_box, lang_box],
                       [chatbot, msg_box])
        progress_btn.click(show_progress, [learner_id_box, lang_box], [progress_box])
        clear_btn.click(clear_session, [learner_id_box], [chatbot, progress_box])

        gr.Markdown(
            """
            ---
            **No dark patterns** · No trackers · No internet required · 
            Progress encrypted locally · 🔒 Private
            """
        )

    return demo


if __name__ == "__main__":
    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
    )