# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wwwapp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='articlecontenthistory',
            name='modified_by',
            field=models.ForeignKey(default=None, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
