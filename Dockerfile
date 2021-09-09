FROM node:current-alpine AS build_frontend
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci
COPY webpack.config.js .
COPY frontend ./frontend
RUN npm run build


FROM python:alpine
WORKDIR /usr/src/app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev libffi-dev zlib-dev jpeg-dev rust cargo

RUN pip install --upgrade pip wheel gunicorn
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
COPY --from=build_frontend /app/static/dist static/dist

RUN echo "import os" > wwwapp/local_settings.py && \
    echo "SECRET_KEY = os.environ['SECRET_KEY']" >> wwwapp/local_settings.py && \
    echo "ALLOWED_HOSTS = ['*']" >> wwwapp/local_settings.py && \
    echo "DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql_psycopg2', 'HOST': 'db', 'NAME': 'aplikacjawww', 'USER': 'app', 'PASSWORD': 'app'}}" >> wwwapp/local_settings.py && \
    echo "GOOGLE_ANALYTICS_KEY = None" >> wwwapp/local_settings.py && \
    echo "MEDIA_ROOT = os.environ['MEDIA_ROOT']" >> wwwapp/local_settings.py && \
    echo "SENDFILE_ROOT = os.environ['SENDFILE_ROOT']" >> wwwapp/local_settings.py && \
    echo "USE_X_FORWARDED_HOST = True" >> wwwapp/local_settings.py && \
    echo "SESSION_COOKIE_SECURE = False" >> wwwapp/local_settings.py && \
    echo "CSRF_COOKIE_SECURE = False" >> wwwapp/local_settings.py

CMD gunicorn wwwapp.wsgi:application --bind 0.0.0.0:8000
ENTRYPOINT ["./entrypoint.sh"]
