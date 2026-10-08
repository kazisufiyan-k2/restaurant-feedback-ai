# Feedback API

Customer review analysis for restaurants and food businesses (English only).
Your trained model + VADER + aspects + emotions + star rating, with an auto-generated reply,
19 email templates and email sending (manual or automatic).

## 1. Add your model (one time)

Copy from `F:\feedback-api\models\` into this project's `models\` folder:

- `feedback-model.pkl`
- `feedback-config.json`

## 2. Run locally (Windows, Antigravity terminal)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m textblob.download_corpora
copy .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs. Each endpoint has an `x-api-key` field: paste only the key value from your `.env`.

Auto tests (no server needed):

```
python tests/test-api.py
python tests/test-email.py
```

## 3. Endpoints

### Analysis

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Status, model info, SMTP status, template count |
| POST | `/analyze` | One review: label, aspects, emotions, admin suggestion, reply, recommended template, auto email |
| POST | `/analyze-batch` | Up to 100 reviews |
| POST | `/reply` | Regenerate reply (change `seed`) |
| POST | `/insights` | Dashboard summary of many reviews |

### Templates

| Method | Path | What it does |
|---|---|---|
| GET | `/templates` | List all templates (filter: `?category=negative&active_only=true`) |
| GET | `/templates/{id}` | One template |
| POST | `/templates` | Create a template |
| PUT | `/templates/{id}` | Edit a template |
| DELETE | `/templates/{id}` | Delete a template |
| POST | `/templates/{id}/preview` | Filled email (subject + body + html), nothing is sent |

### Email

| Method | Path | What it does |
|---|---|---|
| POST | `/send-email` | Send an email using a template ID (admin can override subject or body) |

Header for all except `/` and `/health`: `x-api-key: <your API_KEY>`

## 4. Request examples

**Analyze a review**

```json
{
  "text": "Biryani was great but delivery was late",
  "rating": 4,
  "customer_name": "Rahul",
  "business_name": "Mumbai Kitchen",
  "email": "rahul@gmail.com"
}
```

Response includes `final_label`, `aspects`, `emotions`, `admin_suggestion`, `suggested_reply`,
`recommended_template` and `email_status` (`no_email`, `pending`, `sent`, `skipped`, `failed`).

**Preview a template**

`POST /templates/apology-coupon/preview`

```json
{
  "customer_name": "Rahul",
  "business_name": "Mumbai Kitchen",
  "coupon_code": "SORRY20",
  "review_text": "Delivery was late but the food was great",
  "rating": 3
}
```

**Send an email**

```json
{
  "template_id": "delivery-apology",
  "to": "rahul@gmail.com",
  "customer_name": "Rahul",
  "business_name": "Mumbai Kitchen",
  "reply": "Sorry about the late delivery.",
  "coupon_code": "SORRY20"
}
```

If `reply` is empty and `review_text` is given, the AI writes the reply.
Send `subject` and `body` only when the admin has edited the email.

**Create a template**

```json
{
  "id": "diwali-offer",
  "name": "Diwali offer",
  "category": "positive",
  "subject": "Happy Diwali {customer_name}!",
  "body": "Hi {customer_name},\n\n{reply}\n\nUse {coupon_code} this Diwali.\n\nWarm regards,\n{business_name} Team"
}
```

Placeholders: `{customer_name}` `{business_name}` `{reply}` `{coupon_code}` `{review_link}` `{business_phone}`

## 5. Templates (19 built in)

| Category | Template IDs |
|---|---|
| General | ai-reply |
| Positive | thank-you, request-review, loyalty-offer, referral-ask, welcome-back |
| Neutral | follow-up, feedback-survey, try-again-offer, improvement-promise |
| Negative | apology, apology-coupon, delivery-apology, quality-apology, refund-info, replacement-offer |
| Urgent | urgent-callback, hygiene-response, manager-apology |

## 6. Auto email

When `AUTO_SEND=true` and the review has an email:

- Review label is in `AUTO_SEND_LABELS` (default `positive`) and no manual review is needed: email is sent automatically with the recommended template.
- Everything else stays `pending` so the admin can choose a template, edit and send with `/send-email`.

A request can override the setting with `"auto_send": true` or `false`.

## 7. Environment variables

```
API_KEY=long-secret-key
ALLOWED_ORIGINS=*
MODEL_DIR=models
BUSINESS_NAME=Mumbai Kitchen

SMTP_HOST=smtppro.zoho.com.au
SMTP_PORT=587
SMTP_USER=info@yourdomain.com
SMTP_PASSWORD=app-password
MAIL_FROM=Mumbai Kitchen <info@yourdomain.com>
MAIL_REPLY_TO=
AUTO_SEND=false
AUTO_SEND_LABELS=positive
DEFAULT_COUPON=THANKYOU10
REVIEW_LINK=https://g.page/r/your-google-review-link
BUSINESS_PHONE=+91 00000 00000
```

Without SMTP the API still works. `/send-email` returns 503 and auto email shows `skipped` or `pending`.
After adding SMTP in Dokploy, redeploy.

## 8. Deploy on Dokploy

1. Push this folder to GitHub (including `models/`).
2. Dokploy: Create Application, select the repo, branch `main`, Build Type: **Dockerfile**.
3. Environment: add the variables from section 7.
4. Port: **8000**. Add domain. Deploy.
5. Check `https://your-domain/health`.
6. Optional: to keep custom templates after redeploys, add a volume with mount path `/app/data`.

## 9. Website call (from your backend, never put the key in browser JS)

```js
const res = await fetch("https://api.your-domain.com/analyze", {
  method: "POST",
  headers: { "Content-Type": "application/json", "x-api-key": process.env.FEEDBACK_API_KEY },
  body: JSON.stringify({ text, rating, customer_name, business_name, email })
});
const data = await res.json();
// data.final_label, data.aspects, data.admin_suggestion, data.suggested_reply,
// data.recommended_template, data.email_status
```

## Versions (must match training)

Python 3.13, scikit-learn 1.8.0, numpy 2.3.5, joblib 1.5.2