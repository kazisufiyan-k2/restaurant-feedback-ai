---
title: Restaurant Feedback AI
emoji: 🍽️
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 8000
pinned: false
short_description: Analyze restaurant reviews with a trained ML model
---

# Restaurant Feedback AI

A small API and demo that analyses English restaurant reviews. It uses a trained scikit-learn model plus VADER to predict sentiment (positive, neutral, or negative), pick out aspects such as taste or delivery, tag emotions, and draft a reply.

Live demo: https://huggingface.co/spaces/<HF_USERNAME>/restaurant-feedback-ai

## How to use

Open the live demo, or open http://localhost:8000/demo after a local run. Type a review, optionally add a star rating from 1 to 5, and click Submit. The demo does not need an API key and never sends email.

API docs are at `/docs`. Health is at `/health`. API routes (except `/`, `/demo`, `/health` and `/docs`) need this header:

`x-api-key: <your API_KEY>`

## Run locally

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m textblob.download_corpora
cp .env.example .env
uvicorn app.main:app --reload
```

Then open http://localhost:8000/demo or http://localhost:8000/docs.

Tests:

```
python tests/test-api.py
python tests/test-email.py
```

The trained files are already in `models/` (`feedback-model.pkl` is about 4.3 MB, not Git LFS). Versions must match training: Python 3.13, scikit-learn 1.8.0, numpy 2.3.5, joblib 1.5.2.

## API endpoints

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

Header for all except `/`, `/demo`, `/health` and `/docs`: `x-api-key: <your API_KEY>`

## Request example

**Analyze a review**

```json
{
  "text": "The pasta was great but delivery was late",
  "rating": 4,
  "customer_name": "Alex",
  "business_name": "Our Restaurant",
  "email": "customer@example.com"
}
```

Response includes `final_label`, `aspects`, `emotions`, `admin_suggestion`, `suggested_reply`,
`recommended_template` and `email_status` (`no_email`, `pending`, `sent`, `skipped`, `failed`).

**Preview a template**

`POST /templates/apology-coupon/preview`

```json
{
  "customer_name": "Alex",
  "business_name": "Our Restaurant",
  "coupon_code": "SORRY20",
  "review_text": "Delivery was late but the food was great",
  "rating": 3
}
```

## Environment variables

On Hugging Face Spaces, add these in Settings. Only `API_KEY` is required for the demo and the API to work.

**Secret (required)**

| Name | What it does | Example (not a real secret) |
|---|---|---|
| `API_KEY` | Auth for API routes (not needed for the demo) | `change-this-to-a-long-secret-key` |

**Optional variables**

| Name | Default | What it does |
|---|---|---|
| `ALLOWED_ORIGINS` | `*` | CORS origins, comma-separated |
| `MODEL_DIR` | `models` | Folder with the pickle and config |
| `BUSINESS_NAME` | `Our Restaurant` | Name used in replies and templates |
| `TEMPLATES_FILE` | `data/templates.json` | Where edited templates are saved |
| `AUTO_SEND` | `false` | Auto-send email after `/analyze` when an address is given. Keep this false on a public Space. |
| `AUTO_SEND_LABELS` | `positive` | Labels that may be auto-sent |
| `DEFAULT_COUPON` | `THANKYOU10` | Fallback coupon placeholder |
| `REVIEW_LINK` | empty | Review link used in templates |
| `BUSINESS_PHONE` | empty | Phone used in urgent templates |

**Optional SMTP secrets** (not available on Hugging Face Spaces)

`SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_REPLY_TO`.

Hugging Face Spaces only allow outbound traffic on ports 80, 443 and 8080. SMTP ports 25, 465 and 587 are blocked, so `/send-email` will time out there even if these are set. Leave them unset on Spaces. The public demo never sends email. Without SMTP the API still works: `/send-email` returns 503 and auto email shows `skipped` or `pending`.

## Deploy on Hugging Face Spaces

1. Create a new Space at https://huggingface.co/new-space. Choose SDK **Docker**, hardware **CPU basic**, and visibility **Public**. Name it `restaurant-feedback-ai`.
2. Push this repo to the Space, or connect the GitHub repo.
3. In the Space, open Settings and add the `API_KEY` secret.
4. Wait for the build. The Space opens on the demo (`/` redirects to `/demo`).
