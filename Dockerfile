FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Tinkoff Invest API separately as it might need extra index
RUN pip install t-tech-investments \
    --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple \
    --trusted-host opensource.tbank.ru

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
