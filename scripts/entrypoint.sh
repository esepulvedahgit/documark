#!/bin/sh
set -e

# Only the web service needs to bootstrap the initial admin / run an
# immediate cleanup pass — celery_worker and celery_beat share this same
# image/entrypoint but would otherwise redundantly race each other (and the
# web service) to do the same thing on every startup.
if [ "$1" = "gunicorn" ]; then
    python manage.py migrate --noinput
    python manage.py create_initial_admin
    python manage.py cleanup_expired
fi

exec "$@"
