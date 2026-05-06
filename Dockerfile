FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget gnupg curl \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2t64 \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "app.py"]
