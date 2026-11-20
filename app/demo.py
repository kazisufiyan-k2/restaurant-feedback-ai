"""Public Gradio demo. No API key. Does not send email."""
import gradio as gr

EXAMPLES = [
    ["The pasta was tasty but delivery was late", 4],
    ["Food was cold and the portion was small", 2],
    ["Loved the dessert, will come again", 5],
]


def build_demo(analyze_fn):
    return gr.Interface(
        fn=analyze_fn,
        inputs=[
            gr.Textbox(
                label="Review",
                lines=5,
                placeholder="The pasta was tasty but delivery was late",
            ),
            gr.Number(
                label="Star rating (optional, 1 to 5)",
                minimum=1,
                maximum=5,
                step=1,
                value=None,
            ),
        ],
        outputs=[
            gr.Textbox(label="Label"),
            gr.Textbox(label="Star rating"),
            gr.Textbox(label="Aspects"),
            gr.Textbox(label="Emotions"),
            gr.Textbox(label="Suggested reply", lines=6),
        ],
        title="Restaurant Feedback AI",
        description=(
            "Paste an English restaurant review. The model predicts sentiment, "
            "aspects, emotions, and a suggested reply. No email is sent."
        ),
        examples=EXAMPLES,
        flagging_mode="never",
        analytics_enabled=False,
    )
