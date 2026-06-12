from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0011_user_custom_hotkeys'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='external_avatar_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Avatar hosted by an external identity provider; preferred over the uploaded avatar',
                max_length=1024,
                verbose_name='external avatar url',
            ),
        ),
    ]
