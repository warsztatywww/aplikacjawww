# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-08-16 10:23
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0061_reverse_userprofile_userinfo'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='workshop',
            options={'permissions': (('see_all_workshops', 'Can see all workshops'), ('edit_all_workshops', 'Can edit all workshops'))},
        ),
    ]
