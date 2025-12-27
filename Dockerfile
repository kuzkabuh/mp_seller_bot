# Версия файла: 2.0.0
# Описание: Сборка mp_seller_bot с установленным Nginx и запуском приложения и веб-сервера в одном контейнере
# Дата изменения: 2025-12-27

FROM python:3.12-slim

# Рабочая директория
WORKDIR /app

# Отключаем запись .pyc-файлов и буферизацию stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем необходимые пакеты (curl, ca-certificates) и nginx
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    nginx && \
    rm -rf /var/lib/apt/lists/*

# Копируем зависимости и устанавливаем их (aiohttp, httpx должны быть в requirements.txt)
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем код приложения
COPY app /app

# Копируем конфигурацию nginx (файл nginx.conf должен быть рядом с Dockerfile)
COPY nginx.conf /etc/nginx/nginx.conf

# Открываем порт 80 для Nginx и 8000 для aiohttp (можно опустить EXPOSE 8000, если он не пробрасывается наружу)
EXPOSE 80 8000

# Запускаем nginx и затем Python-приложение
# nginx запускается в фоновом режиме, Python остаётся основным процессом контейнера
CMD bash -c "nginx && python -m main"
