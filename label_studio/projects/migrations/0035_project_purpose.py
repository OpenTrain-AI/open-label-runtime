from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0034_project_annotator_evaluation_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="purpose",
            field=models.CharField(
                blank=True,
                choices=[
                    ("screening", "Screening assessment"),
                    ("production", "Production labeling"),
                ],
                default=None,
                help_text="How this project is used on OpenTrain: screening assessment or production labeling",
                max_length=32,
                null=True,
                verbose_name="purpose",
            ),
        ),
    ]
