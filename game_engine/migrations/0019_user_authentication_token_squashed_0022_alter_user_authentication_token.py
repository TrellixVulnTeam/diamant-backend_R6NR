# Generated by Django 3.2.5 on 2021-09-04 18:01

from django.db import migrations, models
import game_engine.models


def gen_tokens(apps, _):
    # noinspection PyPep8Naming
    User = apps.get_model('game_engine', 'User')
    for row in User.objects.all():
        row.authentication_token = game_engine.models.hex_token()
        row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('game_engine', '0018_alter_matchresult_match_events'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='authentication_token',
            field=models.CharField(max_length=36, unique=False),
        ),
        migrations.RunPython(gen_tokens, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='authentication_token',
            field=models.CharField(default=game_engine.models.hex_token, editable=False, max_length=36, unique=True),
        ),
    ]
