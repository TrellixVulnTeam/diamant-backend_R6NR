# Generated by Django 3.2.5 on 2021-07-16 10:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('game_engine', '0006_auto_20210716_0951'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='github_username',
        ),
    ]
