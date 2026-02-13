FROM python:3.11-slim

WORKDIR /app

# Обновляем pip и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY bot.py .

# Создаем папку для данных
RUN mkdir -p /app/data

CMD ["python", "bot.py"]
