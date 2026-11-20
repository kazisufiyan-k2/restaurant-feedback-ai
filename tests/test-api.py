"""
Auto test for Feedback API (no server needed).
Run from project root:   python tests/test-api.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("API_KEY", "test-key")

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

main.API_KEY = os.environ["API_KEY"]
H = {"x-api-key": main.API_KEY}

REVIEWS = [
    ("The biryani was absolutely delicious, will order again!", 5),
    ("Worst food ever, totally stale and cold", 1),
    ("Food was okay, nothing special", 3),
    ("Delivery was late but the food was great", 4),
    ("Found a hair in my food, disgusting! Staff didn't even apologize 😡", 1),
    ("Amazing ambience, polite staff, loved the desserts 😍", 5),
    ("Pizza was soggy and overpriced", 2),
    ("food was nt gud", 2),
    ("Super fast delivery and hot food 🔥", 5),
    ("Average taste, quantity was less for the price", 3),
    ("good", 5),
    ("ok", 4),
    ("Thank you", None),
    ("Food was cold and delivery was 1 hour late", 5),          # high star + complaint
    ("Amazing biryani, loved it!", 1),                           # low star + praise
    ("The pizza tasted amazing, however the packaging was leaking", 4),
    ("Staff was rude. Food was cold and overpriced.", 1),
    ("Great value for money, tasty food, fast delivery", None),
    ("I will never order from here again", 1),
    ("Received the order", None),
]


def main_test():
    with TestClient(main.app) as c:
        assert c.get("/health").json()["status"] == "ok", "health failed"
        assert c.post("/analyze", json={"text": "hi"}).status_code in (401, 422), "missing key not blocked"
        assert c.post("/analyze", json={"text": "hi"}, headers={"x-api-key": "wrong"}).status_code == 401
        print("✅ /health ok   ✅ API key check ok\n")

        for i, (text, rating) in enumerate(REVIEWS, 1):
            res = c.post("/analyze", headers=H,
                         json={"text": text, "rating": rating, "customer_name": "Alex", "business_name": "Our Restaurant"})
            assert res.status_code == 200, f"{text} -> {res.status_code} {res.text}"
            a = res.json()
            star = f"{rating}★" if rating else "--"
            flag = " ⚠️manual" if a["admin_suggestion"]["needs_manual_review"] else ""
            print(f"{i:2}. [{star:4}] text:{a['text_label']:8} final:{a['final_label']:8} "
                  f"prio:{a['admin_suggestion']['priority']:6}{flag}")
            print(f"    📝 {text}")
            print(f"    aspects: {a['aspects']} | emotions: {a['emotions']}")
            print("    ✉️ " + a["suggested_reply"].replace("\n", "\n       ") + "\n")

        r1 = c.post("/reply", headers=H, json={"text": REVIEWS[0][0], "rating": 5, "seed": 1}).json()
        r2 = c.post("/reply", headers=H, json={"text": REVIEWS[0][0], "rating": 5, "seed": 2}).json()
        print("🔁 Regenerate seed=1:", r1["suggested_reply"].split("\n\n")[1])
        print("🔁 Regenerate seed=2:", r2["suggested_reply"].split("\n\n")[1], "\n")

        batch = c.post("/analyze-batch", headers=H,
                       json={"reviews": [{"text": t, "rating": r} for t, r in REVIEWS[:5]]})
        assert batch.status_code == 200 and batch.json()["count"] == 5
        print("✅ /analyze-batch ok")

        ins = c.post("/insights", headers=H,
                     json={"reviews": [{"text": t, "rating": r} for t, r in REVIEWS]}).json()
        print("✅ /insights:", {k: ins[k] for k in ["satisfaction_score", "satisfaction_level", "label_percent",
                                                    "top_complaints", "urgent_reviews"]})
        for s in ins["suggestions"]:
            print("   💡", s)
        print("\n🎉 ALL TESTS PASSED")


if __name__ == "__main__":
    main_test()
