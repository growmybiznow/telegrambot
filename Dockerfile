# Usa Python 3.11 para evitar incompatibilidades
FROM python:3.11-slim

# Configura el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia el archivo de dependencias
COPY requirements.txt .

# Instala las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el contenido del proyecto
COPY . .

# Comando para ejecutar el bot
CMD ["python", "bot.py"]