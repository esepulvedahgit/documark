FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

# Minimal system deps: only what's needed to build the few extras that
# don't ship prebuilt wheels for every platform (cryptography's C
# extension being the main one). No ffmpeg/exiftool/etc — those belong to
# formats documark doesn't accept (see requirements-markitdown.txt).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-markitdown.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p storage/secure storage/uploads storage/outputs storage/runtime/cache storage/runtime/locks storage/logs

# Uses whatever DOCUMARK_FERNET_KEY/DOCUMARK_ENV happen to be set at build
# time (or none) — this only compiles the manifest, it doesn't need real
# secrets, and settings.py tolerates a missing key outside DOCUMARK_ENV=production.
RUN python manage.py collectstatic --noinput

RUN chmod +x scripts/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "-c", "config/gunicorn.conf.py"]
