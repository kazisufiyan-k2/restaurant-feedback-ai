"""
Satisfaction insights
=====================
Aggregates many analysed reviews into a dashboard summary for the admin.
"""
from collections import Counter

from .replies import ACTIONS

NAMES = {"taste": "food taste", "delivery": "delivery", "packaging": "packaging", "quantity": "portion size",
         "price": "pricing", "service": "service", "ambience": "ambience", "hygiene": "hygiene"}


def satisfaction_insights(results: list) -> dict:
    """results = list of full /analyze outputs (analysis + admin_suggestion)."""
    n = len(results)
    if n == 0:
        return {"total_reviews": 0, "message": "No reviews to analyse."}

    labels = Counter(r["final_label"] for r in results)
    pct = {k: round(labels.get(k, 0) * 100 / n, 1) for k in ["positive", "neutral", "negative"]}
    score = round(sum((r["final_score"] + 1) / 2 for r in results) * 100 / n, 1)

    ratings = [r["rating"] for r in results if r.get("rating") is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    neg_aspects, pos_aspects = Counter(), Counter()
    for r in results:
        for a, s in r["aspects"].items():
            if s == "negative":
                neg_aspects[a] += 1
            elif s == "positive":
                pos_aspects[a] += 1

    urgent = sum(1 for r in results if r["admin_suggestion"]["priority"] == "urgent")
    manual = sum(1 for r in results if r["admin_suggestion"]["needs_manual_review"])
    mismatch = sum(1 for r in results if r.get("rating_mismatch"))
    emotions = Counter(e for r in results for e in r.get("emotions", []))

    suggestions = []
    if urgent:
        suggestions.append(f"{urgent} urgent review(s) need a reply within 2 hours.")
    if neg_aspects:
        top, cnt = neg_aspects.most_common(1)[0]
        suggestions.append(f"Most complaints are about {NAMES.get(top, top)} ({cnt} review(s)). {ACTIONS.get(top, '')}".strip())
    if pct["negative"] >= 30:
        suggestions.append("Negative reviews are above 30%. Review operations this week.")
    if pct["positive"] >= 70:
        suggestions.append("Customers are mostly happy. Ask satisfied customers for Google reviews.")
    if pos_aspects:
        best, cnt = pos_aspects.most_common(1)[0]
        suggestions.append(f"Customers love your {NAMES.get(best, best)} ({cnt} review(s)). Highlight it in your marketing.")
    if mismatch:
        suggestions.append(f"{mismatch} review(s) have star rating and text that don't match. Read them manually.")
    if not suggestions:
        suggestions.append("Not enough signal yet. Collect more reviews.")

    level = ("excellent" if score >= 80 else "good" if score >= 65 else
             "average" if score >= 50 else "poor")

    return {
        "total_reviews": n,
        "satisfaction_score": score,
        "satisfaction_level": level,
        "average_rating": avg_rating,
        "label_counts": dict(labels),
        "label_percent": pct,
        "top_complaints": [{"aspect": a, "count": c} for a, c in neg_aspects.most_common(5)],
        "top_praises": [{"aspect": a, "count": c} for a, c in pos_aspects.most_common(5)],
        "top_emotions": [{"emotion": e, "count": c} for e, c in emotions.most_common(5)],
        "urgent_reviews": urgent,
        "needs_manual_review": manual,
        "rating_mismatches": mismatch,
        "suggestions": suggestions,
    }
