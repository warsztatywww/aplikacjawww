Aplikacja WWW
=============

Django-based application to manage registration of people for [scientific summer school](https://warsztatywww.pl/).

[![Updates](https://pyup.io/repos/github/warsztatywww/aplikacjawww/shield.svg)](https://pyup.io/repos/github/warsztatywww/aplikacjawww/)

### Setup:
- install `python3` and `pip3`
- `python3 -m venv venv` - create a virtual python environment for the app
- `source venv/bin/activate` - activate venv
- `./manage.py migrate` - apply DB migrations
- `./manage.py createsuperuser` - script to create a superuser that can modify DB contents via admin panel
- `./manage.py populate_with_test_data` - script to populate the database with data for development

### Run:
- activate virtualenv (if not yet activated)
- `pip install -r requirements.txt`
- `./manage.py runserver`

#### INTERNETy

For the INTERNETy resources authentication a /resource\_auth endpoint is provided. An example nginx config is in `nginx.conf.example` file.

### Online version:
App currently available at https://warsztatywww.pl/
