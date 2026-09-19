from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('Voices', '0010_educationstory_remove_resource_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='gbvreport',
            name='submitted_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gbv_reports', to=settings.AUTH_USER_MODEL),
        ),
    ]
