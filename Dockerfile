FROM python:3.12-slim-bookworm

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir -e .

EXPOSE 5000

CMD ["python3", "main.py"]