# Imagen base ligera de Python 3.11
FROM python:3.11-slim

# Evita que Python genere archivos .pyc y buffers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crea directorio de trabajo
WORKDIR /app

# Copia solo los requirements primero (mejor cache)
COPY requirements.txt .

# Instala dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Comando principal
CMD ["python", "bot.py"]