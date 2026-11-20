# Hugging Face Spaces runs the container as UID 1000.
# Docs: https://huggingface.co/docs/hub/spaces-sdks-docker
FROM python:3.13-slim

RUN useradd -m -u 1000 user

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    NLTK_DATA=/home/user/nltk_data

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && mkdir -p /home/user/nltk_data /app/data \
 && python -m textblob.download_corpora \
 && chown -R user:user /home/user/nltk_data /app/data

COPY --chown=user app ./app
COPY --chown=user models ./models

USER user

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
