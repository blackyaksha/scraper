FROM python:3.10-slim

# Prevent Python from writing .pyc files and force unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies and Chromium + Chromedriver
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project files
COPY . /app/

EXPOSE 10000

# ✅ Ensure uvicorn points to your file + app
CMD ["uvicorn", "SensorDataScraper:app", "--host", "0.0.0.0", "--port", "10000"]
