#!/bin/sh
coverage erase
coverage run manage.py test wwwapp
coverage report
coverage html
