"""
Feedback analyzer
=================
One pipeline that combines:
  1. Your trained model (TF-IDF + Logistic Regression)  -> models/feedback-model.pkl
  2. VADER (pretrained, used inside the meta-model + conflict flag)
  3. Meta-model (stacks 1 + 2) + bias correction
  4. Aspect detection (taste, delivery, price, ...)
  5. NRCLex emotions
  6. Star rating + text combination

The cleaning logic MUST stay identical to the training notebook.
"""
import json
import os
import re

import joblib
import numpy as np
from nrclex import NRCLex
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

POS_EMO = {"joy", "trust", "anticipation"}
NEG_EMO = {"anger", "disgust", "fear", "sadness"}

DISHES = [
    "biryani", "pizza", "burger", "pasta", "noodles", "paneer", "chicken", "mutton", "fish", "prawns",
    "dosa", "idli", "sandwich", "fries", "momos", "shawarma", "kebab", "kebabs", "tikka", "curry", "dal",
    "naan", "roti", "rice", "cake", "dessert", "desserts", "ice cream", "coffee", "tea", "shake", "milkshake",
    "salad", "soup", "wrap", "rolls", "thali", "pancakes", "waffles", "brownie", "steak", "sushi", "tacos",
    "haleem", "mandi", "manchurian", "fried rice", "butter chicken", "starters", "pastry", "mocktail",
]
DISH_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, DISHES), key=len, reverse=True)) + r")\b")
NEGATION = re.compile(r"\b(not|no|never)\b")
SENT_SPLIT = re.compile(r"[.!?\n;]+|\bbut\b|\bhowever\b|\balthough\b|\bthough\b", flags=re.I)


class FeedbackAnalyzer:
    def __init__(self, model_dir: str = "models"):
        model_path = os.path.join(model_dir, "feedback-model.pkl")
        config_path = os.path.join(model_dir, "feedback-config.json")
        if not os.path.exists(model_path) or not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Model files not found in '{model_dir}/'. Copy feedback-model.pkl and "
                f"feedback-config.json from your notebook's models folder."
            )

        bundle = joblib.load(model_path)
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        self.vectorizer = bundle["vectorizer"]
        self.model = bundle["model"]
        self.meta = bundle.get("meta")
        self.use_stack = bool(bundle.get("use_stack")) and self.meta is not None
        self.bias = (float(bundle["bias"][0]), float(bundle["bias"][1]))
        self.classes = [str(c) for c in bundle["classes"]]
        self.idx = {c: i for i, c in enumerate(self.classes)}

        self.config = cfg
        self.contractions = cfg["contractions"]
        self.no_apos = cfg["no_apos"]
        self.slang = cfg["slang"]
        self.emojis = cfg["emojis"]
        self.aspects = cfg["aspects"]
        self.aspect_re = {a: re.compile(r"\b(" + "|".join(map(re.escape, kws)) + r")\b")
                          for a, kws in self.aspects.items()}
        self.neg_cues = re.compile(cfg["neg_cues"])
        self.pos_cues = re.compile(cfg["pos_cues"])
        self.emo_keep = set(cfg["emo_keep"])
        self.vader = SentimentIntensityAnalyzer()

    # ---------- cleaning (same as notebook) ----------
    def clean_text(self, t: str) -> str:
        t = str(t)
        for e, w in self.emojis.items():
            t = t.replace(e, w)
        t = t.lower().replace("\u2019", "'").replace("`", "'")
        t = re.sub(r"<.*?>", " ", t)
        t = re.sub(r"http\S+|www\.\S+", " ", t)
        t = re.sub(r"\s+n'?t\b", "n't", t)
        for pat, rep in self.contractions.items():
            t = re.sub(pat, rep, t)
        t = re.sub(r"(.)\1{2,}", r"\1\1", t)
        t = re.sub(r"[^a-z0-9!?\s]", " ", t)
        t = " ".join(self.slang.get(w, self.no_apos.get(w, w)) for w in t.split())
        return re.sub(r"\s+", " ", t).strip()

    # ---------- text sentiment ----------
    def _vader_feats(self, text: str) -> np.ndarray:
        r = self.vader.polarity_scores(str(text))
        return np.array([[r["compound"], r["neg"], r["neu"], r["pos"]]])

    def predict_text(self, text: str) -> dict:
        c = self.clean_text(text)
        p = self.model.predict_proba(self.vectorizer.transform([c]))
        if self.use_stack:
            length = np.array([[np.log1p(len(c.split()))]])
            p = self.meta.predict_proba(np.hstack([p, self._vader_feats(text), length]))
        logp = np.log(p[0] + 1e-9)
        logp[self.idx["neutral"]] += self.bias[0]
        logp[self.idx["positive"]] += self.bias[1]
        probs = np.exp(logp) / np.exp(logp).sum()

        label = self.classes[int(probs.argmax())]
        conf = float(probs.max())
        vader_c = self.vader.polarity_scores(str(text))["compound"]
        conflict = (label == "positive" and vader_c < -0.3) or (label == "negative" and vader_c > 0.3)
        return {
            "label": label,
            "score": round(float(probs[self.idx["positive"]] - probs[self.idx["negative"]]), 3),
            "confidence": round(conf, 3),
            "confidence_level": "high" if conf >= 0.75 else "medium" if conf >= 0.5 else "low",
            "conflict": bool(conflict),
            "probabilities": {c_: round(float(v), 3) for c_, v in zip(self.classes, probs)},
            "word_count": len(c.split()),
        }

    # ---------- aspects ----------
    @staticmethod
    def split_sentences(text: str) -> list:
        return [p.strip() for p in SENT_SPLIT.split(str(text)) if p and len(p.strip().split()) >= 2]

    def detect_aspects(self, text: str) -> dict:
        found = {}
        for sent in self.split_sentences(text):
            c = self.clean_text(sent)
            hits = [a for a, rx in self.aspect_re.items() if rx.search(c)]
            if not hits:
                continue
            s = self.predict_text(sent)
            label, conf = s["label"], s["confidence"]
            if (label == "neutral" or conf < 0.6) and not NEGATION.search(c):
                neg, pos = bool(self.neg_cues.search(c)), bool(self.pos_cues.search(c))
                if neg and not pos:
                    label, conf = "negative", max(conf, 0.7)
                elif pos and not neg:
                    label, conf = "positive", max(conf, 0.7)
            for a in hits:
                if a not in found or conf > found[a]["confidence"]:
                    found[a] = {"sentiment": label, "confidence": round(conf, 3), "text": sent}
        return found

    def find_dishes(self, text: str) -> dict:
        """Dishes mentioned in positive / negative sentences (used to personalise replies)."""
        out = {"positive": [], "negative": []}
        for sent in self.split_sentences(text) or [str(text)]:
            dishes = DISH_RE.findall(self.clean_text(sent))
            if not dishes:
                continue
            s = self.predict_text(sent)["label"]
            if s in out:
                for d in dishes:
                    if d not in out[s]:
                        out[s].append(d)
        return out

    # ---------- emotions ----------
    def get_emotions(self, text: str, label: str = None, top: int = 3) -> list:
        try:
            e = NRCLex()                    # new instance per call = thread safe
            e.load_raw_text(str(text))
            scores = e.raw_emotion_scores
        except Exception:
            return []
        scores = {k: v for k, v in scores.items() if k in self.emo_keep and v > 0}
        if label == "negative":
            scores = {k: v for k, v in scores.items() if k not in POS_EMO}
        if label == "positive":
            scores = {k: v for k, v in scores.items() if k not in NEG_EMO}
        return [k for k, _ in sorted(scores.items(), key=lambda x: -x[1])[:top]]

    # ---------- star + text ----------
    @staticmethod
    def rating_label(rating):
        if rating is None:
            return None
        if rating <= 2:
            return "negative"
        if rating < 4:
            return "neutral"
        return "positive"

    @staticmethod
    def combine(text_res: dict, rating):
        """Blend text sentiment with star rating. Text weight depends on model confidence."""
        if rating is None:
            return text_res["label"], text_res["score"], False
        rating_score = (float(rating) - 3) / 2                     # 1..5 -> -1..1
        level = text_res["confidence_level"]
        w = {"high": 0.7, "medium": 0.5, "low": 0.3}[level]
        if text_res["word_count"] <= 3:                           # "ok", "good food" -> trust stars more
            w = min(w, 0.3)
        final = w * text_res["score"] + (1 - w) * rating_score
        final_label = "positive" if final > 0.3 else "negative" if final < -0.3 else "neutral"
        mismatch = level != "low" and (
            (text_res["label"] == "negative" and rating >= 4) or
            (text_res["label"] == "positive" and rating <= 2))
        return final_label, round(final, 3), bool(mismatch)

    # ---------- full analysis ----------
    def analyze(self, text: str, rating=None) -> dict:
        t = self.predict_text(text)
        aspects_full = self.detect_aspects(text)

        # Plain factual short text ("Received the order") -> neutral
        c = self.clean_text(text)
        if (not aspects_full and t["word_count"] <= 4
                and self.vader.polarity_scores(c)["compound"] == 0
                and not self.neg_cues.search(c) and not self.pos_cues.search(c)
                and t["confidence"] < 0.9):
            t.update({"label": "neutral", "score": 0.0, "confidence": 0.6, "confidence_level": "medium"})

        final_label, final_score, mismatch = self.combine(t, rating)
        return {
            "text_label": t["label"],
            "text_score": t["score"],
            "confidence": t["confidence"],
            "confidence_level": t["confidence_level"],
            "probabilities": t["probabilities"],
            "conflict": t["conflict"],
            "rating": rating,
            "rating_label": self.rating_label(rating),
            "rating_mismatch": mismatch,
            "final_label": final_label,
            "final_score": final_score,
            "aspects": {a: v["sentiment"] for a, v in aspects_full.items()},
            "aspect_details": aspects_full,
            "dishes": self.find_dishes(text),
            "emotions": self.get_emotions(text, t["label"]),
            "is_short": t["word_count"] <= 3,
        }