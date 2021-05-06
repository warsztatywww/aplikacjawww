FROM    node:16-alpine3.13 AS build-frontend
WORKDIR /app

COPY    package.json \
        package-lock.json \
        ./
RUN     npm clean-install

COPY    webpack.config.js .
COPY    frontend ./frontend
RUN     npm run build


FROM    python:3.9-alpine3.13 AS runner
WORKDIR /usr/src/app


# RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev libffi-dev zlib-dev jpeg-dev
RUN     apk update \
&&      apk add \
                cargo \
                gcc \
                jpeg-dev \
                libffi-dev \
                musl-dev \
                openssl-dev \
                postgresql-dev \
                python3-dev \
                zlib-dev \
;

ENV     PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1

RUN     pip install --upgrade pip setuptools
COPY    requirements.txt .
RUN     pip install gunicorn -r requirements.txt

COPY --from=build-frontend \
        /app/static/dist \
        static/dist
COPY    . .

RUN     echo "import os" >>wwwapp/local_settings.py \
&&      echo "DEBUG = True" >>wwwapp/local_settings.py \
&&      echo "SECRET_KEY = os.environ['SECRET_KEY']" >>wwwapp/local_settings.py \
&&      echo "ALLOWED_HOSTS = ['*']" >>wwwapp/local_settings.py \
&&      echo "class Anything: __contains__ = lambda *args: True" >>wwwapp/local_settings.py \
&&      echo "INTERNAL_IPS = Anything()" >>wwwapp/local_settings.py \
&&      echo "DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql_psycopg2', 'HOST': 'db', 'NAME': 'aplikacjawww', 'USER': 'app', 'PASSWORD': 'app'}}" >>wwwapp/local_settings.py \
&&      echo "GOOGLE_ANALYTICS_KEY = None" >>wwwapp/local_settings.py \
&&      echo "MEDIA_ROOT = os.environ['MEDIA_ROOT']" >>wwwapp/local_settings.py \
&&      echo "SENDFILE_ROOT = os.environ['SENDFILE_ROOT']" >>wwwapp/local_settings.py \
&&      echo "USE_X_FORWARDED_HOST = True" >>wwwapp/local_settings.py \
&&      echo "SESSION_COOKIE_SECURE = False" >>wwwapp/local_settings.py \
&&      echo "CSRF_COOKIE_SECURE = False" >>wwwapp/local_settings.py \
;


EXPOSE  8000
CMD     ./entrypoint.sh
