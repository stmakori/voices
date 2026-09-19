from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Voices', '0011_gbvreport_submitted_by'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='author_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='authored_articles', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='blog',
            name='author_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='authored_blogs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='blog',
            name='category',
            field=models.CharField(choices=[('education', 'Education'), ('prevention', 'Prevention'), ('support', 'Support Services'), ('legal', 'Legal Rights'), ('awareness', 'Awareness'), ('other', 'Other')], default='other', max_length=20),
        ),
        migrations.AddField(
            model_name='resource',
            name='latitude',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='resource',
            name='longitude',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
