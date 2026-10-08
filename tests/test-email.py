"""
Test templates + email endpoints WITHOUT a real SMTP server (emails are captured, not sent).
Run from project root:   python tests/test-email.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("API_KEY", "test-key")
os.environ["TEMPLATES_FILE"] = os.path.join(tempfile.mkdtemp(), "templates.json")
os.environ.update({"SMTP_HOST": "fake", "SMTP_USER": "fake@test.com", "SMTP_PASSWORD": "x"})

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

SENT = []
main.send_mail = lambda to, subject, text, html=None: SENT.append({"to": to, "subject": subject, "text": text})
main.API_KEY = os.environ["API_KEY"]
main.AUTO_SEND = True
H = {"x-api-key": main.API_KEY}


def run():
    with TestClient(main.app) as c:
        h = c.get("/health").json()
        assert h["smtp_configured"] and h["templates"] >= 19, h
        print(f"✅ /health: {h['templates']} templates, smtp={h['smtp_configured']}, auto_send={h['auto_send']}")

        lst = c.get("/templates", headers=H).json()
        print(f"✅ GET /templates: {lst['count']} -> {[t['id'] for t in lst['templates']]}")
        neg = c.get("/templates?category=negative", headers=H).json()
        print(f"✅ negative templates: {[t['id'] for t in neg['templates']]}")

        assert c.get("/templates/apology-coupon", headers=H).status_code == 200
        assert c.get("/templates/nope", headers=H).status_code == 404
        print("✅ GET /templates/{id} ok (and 404 for unknown)")

        new = {"id": "diwali-offer", "name": "Diwali offer", "category": "positive",
               "subject": "Happy Diwali {customer_name}!",
               "body": "Hi {customer_name},\n\n{reply}\n\nUse {coupon_code} this Diwali.\n\n{business_name} Team"}
        assert c.post("/templates", headers=H, json=new).status_code == 201
        assert c.post("/templates", headers=H, json=new).status_code == 409
        assert c.put("/templates/diwali-offer", headers=H, json={"subject": "Diwali treat for {customer_name}"}).status_code == 200
        print("✅ create / duplicate 409 / edit template ok")

        p = c.post("/templates/apology-coupon/preview", headers=H,
                   json={"customer_name": "Rahul", "business_name": "Spice Hub", "coupon_code": "SORRY20",
                         "review_text": "Delivery was late but the food was great", "rating": 3}).json()
        print("✅ preview:\n   Subject:", p["subject"], "\n   " + p["body"].replace("\n", "\n   "))

        r = c.post("/send-email", headers=H, json={
            "template_id": "apology-coupon", "to": "rahul@gmail.com", "customer_name": "Rahul",
            "business_name": "Spice Hub", "reply": "Sorry about the late delivery.", "coupon_code": "SORRY20"})
        assert r.status_code == 200 and r.json()["status"] == "sent", r.text
        print("✅ /send-email manual:", r.json()["status"], "->", SENT[-1]["to"], "|", SENT[-1]["subject"])

        r = c.post("/send-email", headers=H, json={
            "template_id": "thank-you", "to": "rahul@gmail.com",
            "subject": "Edited by admin", "body": "Hi Rahul,\n\nThis whole text was edited by admin."})
        assert SENT[-1]["subject"] == "Edited by admin" and "edited by admin" in SENT[-1]["text"]
        print("✅ admin edited subject/body sent as-is")

        assert c.post("/send-email", headers=H, json={"template_id": "thank-you", "to": "bad-email"}).status_code == 422
        print("✅ invalid email rejected")

        before = len(SENT)
        a = c.post("/analyze", headers=H, json={"text": "The biryani was absolutely delicious, will order again!",
                                                "rating": 5, "customer_name": "Priya", "email": "priya@gmail.com"}).json()
        print(f"✅ /analyze positive -> template {a['recommended_template']} | email {a['email_status']}")
        b = c.post("/analyze", headers=H, json={"text": "Food was cold and delivery was 1 hour late",
                                                "rating": 1, "customer_name": "Amit", "email": "amit@gmail.com"}).json()
        print(f"✅ /analyze negative -> template {b['recommended_template']} | email {b['email_status']}")
        n = c.post("/analyze", headers=H, json={"text": "good", "rating": 5}).json()
        print(f"✅ /analyze no email -> {n['email_status']}")
        print(f"   auto emails sent in this block: {len(SENT) - before}")

        assert c.delete("/templates/diwali-offer", headers=H).status_code == 200
        print("✅ delete template ok")
        print("\n🎉 EMAIL + TEMPLATE TESTS PASSED")


if __name__ == "__main__":
    run()