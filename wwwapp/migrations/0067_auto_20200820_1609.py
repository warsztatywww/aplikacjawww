# Generated by Django 3.1 on 2020-08-20 16:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0066_add_camp_model'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='k8s_password',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='k8s_user',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='owncloud_password',
        ),
        migrations.RemoveField(
            model_name='userprofile',
            name='owncloud_user',
        ),
    ]
