# Use official Python image
FROM python:3.11

# Install system dependencies required for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    xvfb \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libdrm2 \
    libxdamage1 \
    libgbm1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy everything to container
COPY . .

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium
RUN playwright install --with-deps chromium

# Expose port for web service (needed by Railway)
EXPOSE 10000

# Start the Twitter bot
CMD ["python", "-u", "merge.py"]
