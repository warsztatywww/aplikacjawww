# Generated by Django 3.1.7 on 2021-03-06 12:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0073_qualification_comment_to_textfield'),
    ]

    operations = [
        migrations.AddField(
            model_name='workshop',
            name='short_description',
            field=models.CharField(blank=True, max_length=140),
        ),
    ]
