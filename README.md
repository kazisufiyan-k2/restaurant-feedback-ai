# Feedback API

Customer review analysis for restaurants and food businesses (English only).
Your trained model + VADER + aspects + emotions + star rating, with an auto-generated reply.

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

Open http://localhost:8000/docs. Each POST has an `x-api-key` field: paste the `API_KEY` from your `.env`.

Auto test (no server needed):

```
python tests/test-api.py
```

## 3. Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Status + model info |
| POST | `/analyze` | One review: label, aspects, emotions, admin suggestion, reply |
| POST | `/analyze-batch` | Up to 100 reviews |
| POST | `/reply` | Regenerate reply (change `seed`) |
| POST | `/insights` | Dashboard summary of many reviews |

Request body:

```json
{ "text": "Biryani was great but delivery was late", "rating": 4, "customer_name": "Rahul", "business_name": "Spice Hub" }
```

Header: `x-api-key: <your API_KEY>`

## 4. Deploy on Dokploy

1. Push this folder to GitHub (including `models/`).
2. Dokploy: Create Application, select the repo, Build Type: **Dockerfile**.
3. Environment: `API_KEY=...`, `ALLOWED_ORIGINS=https://your-website.com`, optional `BUSINESS_NAME=...`
4. Port: **8000**. Add domain. Deploy.
5. Check `https://your-domain/health`.

## 5. Website call (from your backend, never put the key in browser JS)

```js
const res = await fetch("https://api.your-domain.com/analyze", {
  method: "POST",
  headers: { "Content-Type": "application/json", "x-api-key": process.env.FEEDBACK_API_KEY },
  body: JSON.stringify({ text, rating, customer_name, business_name })
});
const data = await res.json();
// data.final_label, data.aspects, data.emotions, data.admin_suggestion, data.suggested_reply
```

## Versions (must match training)

Python 3.13, scikit-learn 1.8.0, numpy 2.3.5, joblib 1.5.2
