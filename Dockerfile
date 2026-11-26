# One container serves both the app and the API.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY recipekeeper/ recipekeeper/
COPY scripts/ scripts/
COPY --from=web /web/dist web/dist
ENV COOKIE_SECURE=1
EXPOSE 8000
# Each start first moves any photos still in the database into R2 (does nothing once done).
CMD ["sh", "-c", "python -m scripts.move_photos_to_r2 || true; uvicorn recipekeeper.api:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
