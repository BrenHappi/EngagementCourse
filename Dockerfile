FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["gunicorn", "--preload", "-w", "4", "--threads", "2", "--bind", "0.0.0.0:8000", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "engagement_course.app:create_app()"]
