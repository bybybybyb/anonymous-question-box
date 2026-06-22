FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AQBOX_CONFIG=/config/config.yaml

WORKDIR /app

RUN adduser --disabled-password --gecos "" aqbox \
    && mkdir -p /config /data \
    && chown -R aqbox:aqbox /config /data

COPY pyproject.toml README.md ./
COPY backend ./backend

RUN pip install --no-cache-dir .

USER aqbox

EXPOSE 3768

CMD ["uvicorn", "aqbox.main:app", "--host", "0.0.0.0", "--port", "3768"]
