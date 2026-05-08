# Compatible con Oracle Cloud Free Tier (ARM Ampere A1 y AMD x86)
FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY bot.py .

# Directorio para persistencia del JSON
RUN mkdir -p /data

# Variables de entorno por defecto (sobreescribir en docker run o compose)
ENV DATA_FILE=/data/birthdays.json \
    TIMEZONE=America/Lima \
    CHECK_HOUR=8

# El token NUNCA va en la imagen — se pasa en runtime
CMD ["python", "-u", "bot.py"]
