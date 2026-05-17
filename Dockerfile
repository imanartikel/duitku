FROM python:3.11-slim

# Mencegah Python menulis file .pyc ke dalam disk
ENV PYTHONDONTWRITEBYTECODE=1

# Memastikan log Python langsung tampil di console Railway (tanpa buffering)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependensi sistem yang dibutuhkan (jika ada compiler/tool build yang diperlukan)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependensi Python terlebih dahulu agar bisa dicache oleh Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin source code proyek
COPY . .

# Jalankan bot
CMD ["python", "bot.py"]
