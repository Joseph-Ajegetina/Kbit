# Generated by Django 3.1.3 on 2020-11-19 19:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_auto_20201119_1910'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='slug',
            field=models.SlugField(default='test product'),
            preserve_default=False,
        ),
    ]
