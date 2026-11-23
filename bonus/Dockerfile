FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY bonus ./bonus

CMD ["uvicorn", "bonus.main:app", "--host", "0.0.0.0", "--port", "8050"]