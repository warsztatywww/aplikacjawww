# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-07-02 16:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0059_auto_20200701_1631'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='k8s_password',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='k8s_user',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
    ]