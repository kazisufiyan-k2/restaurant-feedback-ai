"""
Feedback API
============
POST /analyze        one review  -> sentiment + aspects + emotions + admin suggestion + suggested reply
POST /analyze-batch  up to 100 reviews
POST /reply          regenerate the reply (new seed = new version)
POST /insights       summary of many reviews for the admin dashboard
GET  /health         status + model info

All POST endpoints need header:  x-api-key: <API_KEY>
"""
import logging
import os
import secrets
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .analyzer import FeedbackAnalyzer
from .insights import satisfaction_insights
from .replies import generate_admin_suggestion, generate_draft_reply

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("feedback-api")

API_KEY = os.getenv("API_KEY", "")
MODEL_DIR = os.getenv("MODEL_DIR", "models")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
DEFAULT_BUSINESS = os.getenv("BUSINESS_NAME", "") or None

STATE = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_KEY:
        log.warning("API_KEY is not set. Set it in .env or Dokploy environment variables!")
    STATE["analyzer"] = FeedbackAnalyzer(MODEL_DIR)
    log.info("Model loaded from '%s' (stacked=%s)", MODEL_DIR, STATE["analyzer"].use_stack)
    yield
    STATE.clear()


app = FastAPI(title="Feedback API", version="1.0.0", lifespan=lifespan,
              description="Customer review analysis: sentiment, aspects, emotions, star rating, auto reply.")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["*"])


# ---------------- auth ----------------
def require_key(x_api_key: str = Header(..., description="Your API key")):
    if not API_KEY or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------- schemas ----------------
class ReviewIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, examples=["Biryani was delicious but delivery was late"])
    rating: Optional[float] = Field(None, ge=1, le=5, description="Star rating 1-5 (optional)")
    customer_name: Optional[str] = Field(None, max_length=100, examples=["Rahul"])
    business_name: Optional[str] = Field(None, max_length=100, examples=["Spice Hub"])


class ReplyIn(ReviewIn):
    seed: Optional[int] = Field(None, description="Change this number to get a different reply")


class BatchIn(BaseModel):
    reviews: List[ReviewIn] = Field(..., min_length=1, max_length=100)


class InsightsIn(BaseModel):
    reviews: List[ReviewIn] = Field(..., min_length=1, max_length=1000)


# ---------------- core ----------------
def process(r: ReviewIn, seed: Optional[int] = None) -> dict:
    text = r.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Review text is empty")
    try:
        a = STATE["analyzer"].analyze(text, r.rating)
    except Exception as e:
        log.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    business = r.business_name or DEFAULT_BUSINESS
    a["admin_suggestion"] = generate_admin_suggestion(a)
    a["suggested_reply"] = generate_draft_reply(a, r.customer_name, business, seed=seed, text=text)
    a["text"] = text
    return a


# ---------------- routes ----------------
@app.get("/")
def root():
    return {"name": "Feedback API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    an = STATE.get("analyzer")
    cfg = an.config if an else {}
    return {"status": "ok" if an else "loading", "model_version": cfg.get("version"),
            "trained_on": cfg.get("trained_on"), "metrics": cfg.get("metrics"),
            "stacked_with_vader": an.use_stack if an else None}


@app.post("/analyze", dependencies=[Depends(require_key)])
def analyze(r: ReviewIn):
    return process(r)


@app.post("/analyze-batch", dependencies=[Depends(require_key)])
def analyze_batch(b: BatchIn):
    return {"count": len(b.reviews), "results": [process(r) for r in b.reviews]}


@app.post("/reply", dependencies=[Depends(require_key)])
def reply(r: ReplyIn):
    a = process(r, seed=r.seed)
    return {"suggested_reply": a["suggested_reply"], "final_label": a["final_label"],
            "aspects": a["aspects"], "seed": r.seed}


@app.post("/insights", dependencies=[Depends(require_key)])
def insights(b: InsightsIn):
    return satisfaction_insights([process(r) for r in b.reviews])
