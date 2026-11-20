"""
Feedback API
============
Analysis:
  POST /analyze          one review -> sentiment, aspects, emotions, admin suggestion, reply,
                         recommended template (+ auto email if enabled)
  POST /analyze-batch    up to 100 reviews
  POST /reply            regenerate the reply (new seed = new version)
  POST /insights         dashboard summary
Templates:
  GET    /templates              list (filter: ?category=negative&active_only=true)
  GET    /templates/{id}         one template
  POST   /templates              create
  PUT    /templates/{id}         edit
  DELETE /templates/{id}         delete
  POST   /templates/{id}/preview filled email (no sending)
Email:
  POST /send-email       send a template email (admin can override subject / body)
  GET  /health           status

All endpoints except /, /demo, /health and /docs need header:  x-api-key: <API_KEY>
"""
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from typing import List, Optional

import gradio as gr
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from .analyzer import FeedbackAnalyzer
from .email_templates import CATEGORIES, TemplateStore, recommend_template
from .insights import satisfaction_insights
from .mailer import send_mail, smtp_configured
from .demo import build_demo
from .replies import generate_admin_suggestion, generate_draft_reply

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("feedback-api")

API_KEY = os.getenv("API_KEY", "")
MODEL_DIR = os.getenv("MODEL_DIR", "models")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
DEFAULT_BUSINESS = os.getenv("BUSINESS_NAME") or "Our Restaurant"
AUTO_SEND = os.getenv("AUTO_SEND", "false").lower() == "true"
AUTO_SEND_LABELS = {x.strip() for x in os.getenv("AUTO_SEND_LABELS", "positive").split(",") if x.strip()}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,49}$")
STATE = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_KEY:
        log.warning("API_KEY is not set. Set it in .env or the host environment variables.")
    STATE["analyzer"] = FeedbackAnalyzer(MODEL_DIR)
    STATE["templates"] = TemplateStore()
    log.info("Model loaded from '%s' (stacked=%s) | SMTP configured: %s | auto send: %s",
             MODEL_DIR, STATE["analyzer"].use_stack, smtp_configured(), AUTO_SEND)
    yield
    STATE.clear()


app = FastAPI(title="Feedback API", version="1.1.0", lifespan=lifespan,
              description="Review analysis, auto reply, email templates and sending.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"])


# ---------------- auth ----------------
def require_key(x_api_key: str = Header(..., description="Your API key")):
    if not API_KEY or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _check_email(v):
    if v is not None and v != "" and not EMAIL_RE.match(v.strip()):
        raise ValueError("Invalid email address")
    return v.strip() if v else None


# ---------------- schemas ----------------
class ReviewIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, examples=["Biryani was delicious but delivery was late"])
    rating: Optional[float] = Field(None, ge=1, le=5, description="Star rating 1-5 (optional)")
    customer_name: Optional[str] = Field(None, max_length=100, examples=["Alex"])
    business_name: Optional[str] = Field(None, max_length=100, examples=["Our Restaurant"])
    email: Optional[str] = Field(None, max_length=200, description="Customer email (needed for auto email)")
    phone: Optional[str] = Field(None, max_length=30, description="Customer phone (saved, not used for sending)")
    auto_send: Optional[bool] = Field(None, description="Override AUTO_SEND for this request")

    @field_validator("email")
    @classmethod
    def _v_email(cls, v):
        return _check_email(v)


class ReplyIn(ReviewIn):
    seed: Optional[int] = Field(None, description="Change this number to get a different reply")


class BatchIn(BaseModel):
    reviews: List[ReviewIn] = Field(..., min_length=1, max_length=100)


class InsightsIn(BaseModel):
    reviews: List[ReviewIn] = Field(..., min_length=1, max_length=1000)


class TemplateIn(BaseModel):
    id: str = Field(..., examples=["diwali-offer"], description="lowercase letters, numbers and hyphens")
    name: str = Field(..., max_length=100)
    category: str = Field(..., examples=["positive"])
    subject: str = Field(..., max_length=200)
    body: str = Field(..., max_length=5000, description="Use {customer_name} {business_name} {reply} "
                                                        "{coupon_code} {review_link} {business_phone}")
    description: Optional[str] = Field("", max_length=300)
    active: bool = True


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = None
    subject: Optional[str] = Field(None, max_length=200)
    body: Optional[str] = Field(None, max_length=5000)
    description: Optional[str] = Field(None, max_length=300)
    active: Optional[bool] = None


class EmailFields(BaseModel):
    customer_name: Optional[str] = Field(None, max_length=100)
    business_name: Optional[str] = Field(None, max_length=100)
    reply: Optional[str] = Field(None, max_length=5000, description="Reply text. If empty and review_text is given, AI writes it")
    review_text: Optional[str] = Field(None, max_length=5000)
    rating: Optional[float] = Field(None, ge=1, le=5)
    coupon_code: Optional[str] = Field(None, max_length=50)
    review_link: Optional[str] = Field(None, max_length=500)
    business_phone: Optional[str] = Field(None, max_length=50)
    subject: Optional[str] = Field(None, max_length=200, description="Admin edited subject (optional)")
    body: Optional[str] = Field(None, max_length=10000, description="Admin edited full body (optional)")


class SendEmailIn(EmailFields):
    template_id: str = Field(..., examples=["apology-coupon"])
    to: str = Field(..., max_length=200, examples=["customer@example.com"])

    @field_validator("to")
    @classmethod
    def _v_to(cls, v):
        return _check_email(v)


# ---------------- helpers ----------------
def reply_core(full_reply: str) -> str:
    """Remove greeting + sign-off from the AI reply so it fits inside a template."""
    parts = full_reply.split("\n\n")
    return parts[1] if len(parts) >= 3 else full_reply


def analyse(text, rating, customer_name, business_name, seed=None) -> dict:
    try:
        a = STATE["analyzer"].analyze(text, rating)
    except Exception as e:
        log.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    business = business_name or DEFAULT_BUSINESS
    a["admin_suggestion"] = generate_admin_suggestion(a)
    a["suggested_reply"] = generate_draft_reply(a, customer_name, business, seed=seed, text=text)
    a["recommended_template"] = recommend_template(a)
    return a


def try_send(to, subject, body, html) -> dict:
    if not smtp_configured():
        return {"status": "skipped", "reason": "SMTP not configured"}
    try:
        send_mail(to, subject, body, html)
        return {"status": "sent", "to": to}
    except Exception as e:
        log.exception("Email failed")
        return {"status": "failed", "reason": str(e)}


def process(r: ReviewIn, seed: Optional[int] = None) -> dict:
    text = r.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Review text is empty")
    a = analyse(text, r.rating, r.customer_name, r.business_name, seed)
    a["text"] = text
    a["email"], a["phone"] = r.email, r.phone

    auto = AUTO_SEND if r.auto_send is None else r.auto_send
    tid = a["recommended_template"]
    if not r.email:
        a["email_status"] = {"status": "no_email"}
    elif not auto:
        a["email_status"] = {"status": "pending", "reason": "Auto send is off. Send from admin."}
    elif a["final_label"] not in AUTO_SEND_LABELS or a["admin_suggestion"]["needs_manual_review"]:
        a["email_status"] = {"status": "pending", "reason": "Needs admin review before sending."}
    else:
        mail = STATE["templates"].render(tid, {"customer_name": r.customer_name,
                                               "business_name": r.business_name or DEFAULT_BUSINESS,
                                               "reply": reply_core(a["suggested_reply"])})
        a["email_status"] = {**try_send(r.email, mail["subject"], mail["body"], mail["html"]),
                             "template_id": tid, "mode": "auto"}
    return a


def build_email(tid: str, e: EmailFields) -> dict:
    store = STATE["templates"]
    t = store.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{tid}' not found")
    reply = e.reply
    if not reply and e.review_text:
        reply = reply_core(analyse(e.review_text, e.rating, e.customer_name, e.business_name)["suggested_reply"])
    values = {"customer_name": e.customer_name, "business_name": e.business_name or DEFAULT_BUSINESS,
              "reply": reply, "coupon_code": e.coupon_code, "review_link": e.review_link,
              "business_phone": e.business_phone}
    return store.render(tid, values, e.subject, e.body)


# ---------------- routes: basic ----------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/demo")


@app.get("/health")
def health():
    an = STATE.get("analyzer")
    cfg = an.config if an else {}
    return {"status": "ok" if an else "loading", "model_version": cfg.get("version"),
            "trained_on": cfg.get("trained_on"), "metrics": cfg.get("metrics"),
            "stacked_with_vader": an.use_stack if an else None,
            "smtp_configured": smtp_configured(), "auto_send": AUTO_SEND,
            "templates": len(STATE["templates"].items) if STATE.get("templates") else 0}


# ---------------- routes: analysis ----------------
@app.post("/analyze", dependencies=[Depends(require_key)])
def analyze(r: ReviewIn):
    return process(r)


@app.post("/analyze-batch", dependencies=[Depends(require_key)])
def analyze_batch(b: BatchIn):
    return {"count": len(b.reviews), "results": [process(r) for r in b.reviews]}


@app.post("/reply", dependencies=[Depends(require_key)])
def reply(r: ReplyIn):
    a = analyse(r.text.strip(), r.rating, r.customer_name, r.business_name, seed=r.seed)
    return {"suggested_reply": a["suggested_reply"], "final_label": a["final_label"],
            "aspects": a["aspects"], "recommended_template": a["recommended_template"], "seed": r.seed}


@app.post("/insights", dependencies=[Depends(require_key)])
def insights(b: InsightsIn):
    results = [analyse(r.text.strip(), r.rating, r.customer_name, r.business_name) for r in b.reviews]
    return satisfaction_insights(results)


# ---------------- routes: templates ----------------
@app.get("/templates", dependencies=[Depends(require_key)])
def list_templates(category: Optional[str] = None, active_only: bool = False):
    items = STATE["templates"].list(category, active_only)
    return {"count": len(items), "categories": CATEGORIES, "templates": items}


@app.get("/templates/{tid}", dependencies=[Depends(require_key)])
def get_template(tid: str):
    t = STATE["templates"].get(tid)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{tid}' not found")
    return t


@app.post("/templates", dependencies=[Depends(require_key)], status_code=201)
def create_template(t: TemplateIn):
    if not ID_RE.match(t.id):
        raise HTTPException(status_code=422, detail="id: use lowercase letters, numbers and hyphens (2-50 chars)")
    if t.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category must be one of {CATEGORIES}")
    try:
        return STATE["templates"].create(t.model_dump())
    except KeyError:
        raise HTTPException(status_code=409, detail=f"Template '{t.id}' already exists")


@app.put("/templates/{tid}", dependencies=[Depends(require_key)])
def update_template(tid: str, t: TemplateUpdate):
    if t.category is not None and t.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category must be one of {CATEGORIES}")
    try:
        return STATE["templates"].update(tid, t.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Template '{tid}' not found")


@app.delete("/templates/{tid}", dependencies=[Depends(require_key)])
def delete_template(tid: str):
    try:
        STATE["templates"].delete(tid)
        return {"deleted": tid}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Template '{tid}' not found")


@app.post("/templates/{tid}/preview", dependencies=[Depends(require_key)])
def preview_template(tid: str, e: EmailFields):
    return build_email(tid, e)


# ---------------- routes: email ----------------
@app.post("/send-email", dependencies=[Depends(require_key)])
def send_email(e: SendEmailIn):
    if not smtp_configured():
        raise HTTPException(status_code=503, detail="SMTP is not configured on the server")
    mail = build_email(e.template_id, e)
    res = try_send(e.to, mail["subject"], mail["body"], mail["html"])
    if res["status"] != "sent":
        raise HTTPException(status_code=502, detail=f"Email failed: {res.get('reason')}")
    return {**res, "template_id": e.template_id, "subject": mail["subject"], "mode": "manual"}

# ---------------- public demo (no API key, no email) ----------------
def demo_analyze(text, rating):
    text = (text or "").strip()
    if not text:
        return "Please enter a review.", "", "", "", ""
    rating_val = None
    if rating not in (None, ""):
        try:
            rating_val = float(rating)
        except (TypeError, ValueError):
            rating_val = None
        if rating_val is not None and not (1 <= rating_val <= 5):
            rating_val = None
    if STATE.get("analyzer") is None:
        return "Model is still loading. Please try again.", "", "", "", ""
    a = analyse(text, rating_val, None, DEFAULT_BUSINESS)
    aspects = a.get("aspects") or {}
    aspects_txt = ", ".join(f"{k}: {v}" for k, v in aspects.items()) or "None detected"
    emotions = a.get("emotions") or []
    emotions_txt = ", ".join(emotions) or "None detected"
    stars = a.get("rating")
    star_txt = f"{stars:g} / 5" if stars is not None else "No rating given"
    return a.get("final_label") or "", star_txt, aspects_txt, emotions_txt, a.get("suggested_reply") or ""



app = gr.mount_gradio_app(app, build_demo(demo_analyze), path="/demo")
