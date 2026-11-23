
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ticket ./ticket

CMD ["uvicorn", "ticket.main:app", "--host", "0.0.0.0", "--port", "8070"]
