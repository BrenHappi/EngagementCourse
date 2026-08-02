FROM python:3.12-slim-bookworm

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["gunicorn", "-w", "4", "--threads", "2", "--bind", "0.0.0.0:8000", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "engagement_course.app:create_app()"]