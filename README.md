Aplikacja WWW
=============

[![Python test](https://github.com/warsztatywww/aplikacjawww/workflows/Python%20test/badge.svg)](https://github.com/warsztatywww/aplikacjawww/actions?query=branch%3Amaster+workflow%3A%22Python+test%22)
[![codecov](https://codecov.io/gh/warsztatywww/aplikacjawww/branch/master/graph/badge.svg?token=xqOEznDxRX)](https://codecov.io/gh/warsztatywww/aplikacjawww)
[![Updates](https://pyup.io/repos/github/warsztatywww/aplikacjawww/shield.svg)](https://pyup.io/repos/github/warsztatywww/aplikacjawww/)

Django-based application to manage registration of people for [scientific summer school](https://warsztatywww.pl/).

### Setup:
- install `python3`, `pip3` and `npm`
- `python3 -m venv venv` - create a virtual python environment for the app
- `source venv/bin/activate` - activate venv
- `npm install` - download js/css dependencies
- `npm run build` - run webpack to build the static js/css files (you can use `build-dev` instead during development - it's faster and doesn't minify)
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
