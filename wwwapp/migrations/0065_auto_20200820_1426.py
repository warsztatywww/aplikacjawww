# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-08-20 14:26
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0064_auto_20200819_1925'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='workshop',
            options={'permissions': (('see_all_workshops', 'Can see all workshops'), ('edit_all_workshops', 'Can edit all workshops'), ('change_workshop_status', 'Can change workshop status'))},
        ),
    ]
