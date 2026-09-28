# Multi-stage: build + runtime para Aferix (Django + uWSGI)
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt uwsgi==2.0.30

COPY . .

RUN python manage.py collectstatic --noinput --settings=app.settings

EXPOSE 8000

CMD ["uwsgi", "--ini", "uwsgi.ini"]
