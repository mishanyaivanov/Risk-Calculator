FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir --index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple \
    t-tech-investments \
    --trusted-host opensource.tbank.ru

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
