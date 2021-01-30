# Generated by Django 3.1.6 on 2021-02-23 19:03

from django.db import migrations, models
import wwwapp.models


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0071_enable_uploads_for_new_workshops'),
    ]

    operations = [
        migrations.AlterField(
            model_name='solutionfile',
            name='file',
            field=models.FileField(storage=wwwapp.models.UploadStorage(), upload_to=wwwapp.models.solutions_dir, verbose_name='Plik'),
        ),
        migrations.AlterField(
            model_name='workshop',
            name='qualification_problems',
            field=models.FileField(blank=True, null=True, storage=wwwapp.models.UploadStorage(), upload_to='qualification'),
        ),
    ]