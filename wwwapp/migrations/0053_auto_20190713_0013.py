# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-13 00:13
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0052_auto_20190712_1935'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='userprofile',
            options={'permissions': [('see_all_users', 'Can see all users'), ('export_workshop_registration', 'Can download workshop registration data')]},
        ),
    ]