# Usar explícitamente Python 3.11
FROM python:3.11-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Copiar dependencias
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# Comando que ejecutará el bot
CMD ["python", "bot.py"]