import gradio as gr
import json
from tutor.curriculum_loader import load_seed, expand_curriculum
from tutor.adaptive import BKT


CURRICULUM_PATH = "T3.1_Math_Tutor/curriculum_seed.json"


def load_items():
    items = load_seed(CURRICULUM_PATH)
    items = expand_curriculum(items, target=24)
    return items


ITEMS = load_items()


def get_item_html(item):
    stem = item.get("stem_en", item.get("stem_fr", ""))
    visual = item.get("visual", "")
    html = f"<div><h3>{stem}</h3>"
    if visual:
        html += f"<p>(visual: {visual})</p>"
    html += "</div>"
    return html


def make_demo():
    bkts = {item['id']: BKT() for item in ITEMS}
    idx = {"i": 0}

    def next_item():
        i = idx['i'] % len(ITEMS)
        idx['i'] += 1
        return get_item_html(ITEMS[i]), ITEMS[i]['id']

    def submit_answer(item_id, answer_text):
        # try to parse integer
        try:
            ans = int(answer_text.strip())
            correct = (ans == next(x for x in ITEMS if x['id'] == item_id)['answer_int'])
        except Exception:
            correct = False
        bkt = bkts[item_id]
        bkt.update(correct)
        prob = bkt.predict_correct()
        feedback = "Correct!" if correct else "Try again"
        return feedback + f" (P_known={prob:.2f})"

    with gr.Blocks() as demo:
        gr.Markdown("# AI Math Tutor — Demo (seed)")
        with gr.Row():
            item_box = gr.HTML()
            item_id = gr.Textbox(visible=False)
        with gr.Row():
            ans = gr.Textbox(label="Answer (type number)")
            submit = gr.Button("Submit")
            nxt = gr.Button("Next")
        out = gr.Textbox(label="Feedback")

        submit.click(submit_answer, inputs=[item_id, ans], outputs=[out])
        nxt.click(lambda: next_item(), outputs=[item_box, item_id])

    return demo


if __name__ == "__main__":
    demo = make_demo()
    demo.launch()
