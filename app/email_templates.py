"""
Email templates
===============
Default templates live in this file. Any create / edit / delete from the API is saved
to data/templates.json (set TEMPLATES_FILE to change the path).

Placeholders you can use in subject and body:
  {customer_name} {business_name} {reply} {coupon_code} {review_link} {business_phone}
"""
import html
import json
import os
import threading

CATEGORIES = ["positive", "neutral", "negative", "urgent", "general"]

SIGN = "\n\nWarm regards,\n{business_name} Team"

DEFAULT_TEMPLATES = [
    # ---------- general ----------
    {"id": "ai-reply", "name": "AI reply", "category": "general",
     "description": "Sends only the AI generated reply.",
     "subject": "Thank you for your feedback",
     "body": "Hi {customer_name},\n\n{reply}" + SIGN},
    # ---------- positive ----------
    {"id": "thank-you", "name": "Thank you", "category": "positive",
     "description": "Happy customer, simple thank you.",
     "subject": "Thank you for your lovely feedback!",
     "body": "Hi {customer_name},\n\n{reply}\n\nCustomers like you are the reason we love what we do." + SIGN},
    {"id": "request-review", "name": "Request Google review", "category": "positive",
     "description": "Happy customer, ask for a public review.",
     "subject": "Glad you loved it! Would you share it?",
     "body": "Hi {customer_name},\n\n{reply}\n\nIf you have a minute, we'd be grateful if you could share your experience here:\n{review_link}" + SIGN},
    {"id": "loyalty-offer", "name": "Loyalty offer", "category": "positive",
     "description": "Happy repeat customer, small reward.",
     "subject": "A small thank you from us",
     "body": "Hi {customer_name},\n\n{reply}\n\nAs a thank you, here's a code for your next order: {coupon_code}" + SIGN},
    {"id": "referral-ask", "name": "Referral ask", "category": "positive",
     "description": "Happy customer, ask them to tell friends.",
     "subject": "Know someone who'd love this too?",
     "body": "Hi {customer_name},\n\n{reply}\n\nIf you enjoyed it, we'd love it if you told a friend about us. Share the code {coupon_code} so they get a treat on their first order." + SIGN},
    {"id": "welcome-back", "name": "Welcome back", "category": "positive",
     "description": "Returning customer.",
     "subject": "Great to have you back!",
     "body": "Hi {customer_name},\n\n{reply}\n\nIt's always great to see you again. See you soon!" + SIGN},
    # ---------- neutral ----------
    {"id": "follow-up", "name": "Follow up", "category": "neutral",
     "description": "Neutral feedback, ask how to improve.",
     "subject": "Thanks for your feedback",
     "body": "Hi {customer_name},\n\n{reply}\n\nWhat's one thing we could do to make your next experience 5 stars? Just reply to this email." + SIGN},
    {"id": "feedback-survey", "name": "Feedback survey", "category": "neutral",
     "description": "Ask for more detailed feedback.",
     "subject": "Help us get better",
     "body": "Hi {customer_name},\n\n{reply}\n\nWe'd really value a few more details. Simply reply and tell us what you liked and what we could improve." + SIGN},
    {"id": "try-again-offer", "name": "Try again offer", "category": "neutral",
     "description": "Neutral customer, invite them back with a code.",
     "subject": "Give us another try?",
     "body": "Hi {customer_name},\n\n{reply}\n\nWe'd love to show you our best. Use code {coupon_code} on your next order." + SIGN},
    {"id": "improvement-promise", "name": "Improvement promise", "category": "neutral",
     "description": "Neutral with some complaints.",
     "subject": "We're working on it",
     "body": "Hi {customer_name},\n\n{reply}\n\nWe've shared your points with the team and are working on them." + SIGN},
    # ---------- negative ----------
    {"id": "apology", "name": "Apology", "category": "negative",
     "description": "General apology.",
     "subject": "We're sorry about your experience",
     "body": "Hi {customer_name},\n\n{reply}\n\nPlease reply to this email so we can make it right." + SIGN},
    {"id": "apology-coupon", "name": "Apology with coupon", "category": "negative",
     "description": "Apology plus a discount code.",
     "subject": "We're sorry, here's something for your next order",
     "body": "Hi {customer_name},\n\n{reply}\n\nAs an apology, please use code {coupon_code} on your next order." + SIGN},
    {"id": "delivery-apology", "name": "Delivery apology", "category": "negative",
     "description": "Late or poor delivery.",
     "subject": "Sorry about your delivery",
     "body": "Hi {customer_name},\n\n{reply}\n\nWe're reviewing this with our delivery team. Your next order is on us with code {coupon_code}." + SIGN},
    {"id": "quality-apology", "name": "Quality apology", "category": "negative",
     "description": "Taste or food quality complaint.",
     "subject": "Sorry the food wasn't right",
     "body": "Hi {customer_name},\n\n{reply}\n\nOur kitchen team has been informed. We'd love the chance to make it up to you, use code {coupon_code} next time." + SIGN},
    {"id": "refund-info", "name": "Refund information", "category": "negative",
     "description": "Customer may need a refund.",
     "subject": "About your refund",
     "body": "Hi {customer_name},\n\n{reply}\n\nPlease reply with your order details and we'll process a refund for you." + SIGN},
    {"id": "replacement-offer", "name": "Replacement offer", "category": "negative",
     "description": "Offer to replace the order.",
     "subject": "Let us replace your order",
     "body": "Hi {customer_name},\n\n{reply}\n\nWe'd like to send you a fresh replacement. Just reply to this email with your order details." + SIGN},
    # ---------- urgent ----------
    {"id": "urgent-callback", "name": "Urgent callback", "category": "urgent",
     "description": "Serious complaint, manager will call.",
     "subject": "Our manager will contact you",
     "body": "Hi {customer_name},\n\n{reply}\n\nOur manager will personally contact you shortly. You can also reach us at {business_phone}." + SIGN},
    {"id": "hygiene-response", "name": "Hygiene response", "category": "urgent",
     "description": "Hygiene issue (hair, insect, dirty).",
     "subject": "We're investigating this right away",
     "body": "Hi {customer_name},\n\n{reply}\n\nWe've started an immediate check of our kitchen. Our manager will contact you personally. You can also reach us at {business_phone}." + SIGN},
    {"id": "manager-apology", "name": "Manager apology", "category": "urgent",
     "description": "Personal apology from the manager.",
     "subject": "A personal apology from our manager",
     "body": "Hi {customer_name},\n\n{reply}\n\nI'm personally looking into this and will make sure it doesn't happen again. Please reply or call us at {business_phone}." + SIGN},
]


class _Safe(dict):
    def __missing__(self, key):
        return ""


class TemplateStore:
    def __init__(self, path: str = None):
        self.path = path or os.getenv("TEMPLATES_FILE", "data/templates.json")
        self.lock = threading.Lock()
        self.items = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    return {t["id"]: t for t in data}
            except Exception:
                pass
        return {t["id"]: {**t, "active": True, "built_in": True} for t in DEFAULT_TEMPLATES}

    def _save(self):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(list(self.items.values()), f, indent=2, ensure_ascii=False)

    # ---------- CRUD ----------
    def list(self, category=None, active_only=False):
        out = list(self.items.values())
        if category:
            out = [t for t in out if t["category"] == category]
        if active_only:
            out = [t for t in out if t.get("active", True)]
        return out

    def get(self, tid):
        return self.items.get(tid)

    def create(self, t: dict):
        with self.lock:
            if t["id"] in self.items:
                raise KeyError("exists")
            self.items[t["id"]] = {**t, "built_in": False}
            self._save()
            return self.items[t["id"]]

    def update(self, tid, fields: dict):
        with self.lock:
            if tid not in self.items:
                raise KeyError("missing")
            self.items[tid].update({k: v for k, v in fields.items() if v is not None})
            self._save()
            return self.items[tid]

    def delete(self, tid):
        with self.lock:
            if tid not in self.items:
                raise KeyError("missing")
            del self.items[tid]
            self._save()

    # ---------- render ----------
    def render(self, tid, values: dict, subject_override=None, body_override=None):
        t = self.items.get(tid)
        if not t:
            raise KeyError("missing")
        v = _Safe({
            "customer_name": values.get("customer_name") or "there",
            "business_name": values.get("business_name") or os.getenv("BUSINESS_NAME") or "The",
            "reply": values.get("reply") or "",
            "coupon_code": values.get("coupon_code") or os.getenv("DEFAULT_COUPON", "THANKYOU10"),
            "review_link": values.get("review_link") or os.getenv("REVIEW_LINK", ""),
            "business_phone": values.get("business_phone") or os.getenv("BUSINESS_PHONE", ""),
        })
        subject = (subject_override or t["subject"]).format_map(v)
        body = (body_override or t["body"]).format_map(v).strip()
        return {"template_id": tid, "subject": subject, "body": body, "html": to_html(body)}


def to_html(text: str) -> str:
    safe = html.escape(text).replace("\n", "<br>")
    return ('<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;'
            'color:#222;max-width:600px">' + safe + "</div>")


def recommend_template(a: dict) -> str:
    """Pick the best template for an analysed review."""
    prio = a.get("admin_suggestion", {}).get("priority")
    final, rating = a["final_label"], a.get("rating")
    neg = [k for k, v in a["aspects"].items() if v == "negative"]
    if prio == "urgent":
        return "hygiene-response" if "hygiene" in neg else "urgent-callback"
    if final == "negative" or a["text_label"] == "negative":
        if "delivery" in neg:
            return "delivery-apology"
        if "taste" in neg:
            return "quality-apology"
        return "apology-coupon" if prio == "high" else "apology"
    if final == "neutral":
        return "improvement-promise" if neg else "follow-up"
    if neg:
        return "ai-reply"
    return "request-review" if rating is not None and rating >= 4 else "thank-you"