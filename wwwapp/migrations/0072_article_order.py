# Generated by Django 3.1.7 on 2021-03-04 11:37

from django.db import migrations, models


def reorder(apps, schema_editor):
    Article = apps.get_model("wwwapp", "Article")
    order = 0
    for item in Article.objects.all():
        order += 1
        item.order = order
        item.save()


class Migration(migrations.Migration):

    dependencies = [
        ('wwwapp', '0071_solutionfile_deleted_at'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='article',
            options={'ordering': ['order'], 'permissions': (('can_put_on_menubar', 'Can put on menubar'),)},
        ),
        migrations.AddField(
            model_name='article',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(reorder, migrations.RunPython.noop),
    ]