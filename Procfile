release: python manage.py migrate
web: gunicorn lcpsych.wsgi --log-file -
worker: celery -A lcpsych worker --loglevel=info --concurrency=2
beat: celery -A lcpsych beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
