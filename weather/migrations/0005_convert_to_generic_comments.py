# Generated manually for converting AlertComment to use GenericForeignKey

from django.db import migrations, models
import django.db.models.deletion
from django.contrib.contenttypes.models import ContentType


def convert_existing_comments(apps, schema_editor):
    """Конвертируем существующие комментарии в GenericForeignKey формат"""
    AlertComment = apps.get_model('weather', 'AlertComment')
    SpaceWeatherAlert = apps.get_model('weather', 'SpaceWeatherAlert')
    
    # Получаем ContentType для SpaceWeatherAlert
    try:
        content_type = ContentType.objects.get_for_model(SpaceWeatherAlert)
        
        # Обновляем все существующие комментарии
        for comment in AlertComment.objects.all():
            if hasattr(comment, 'alert_id') and comment.alert_id:
                comment.content_type = content_type
                comment.object_id = comment.alert_id
                comment.save()
    except Exception as e:
        print(f"Error converting comments: {e}")


def reverse_convert_comments(apps, schema_editor):
    """Обратная операция - не нужна, так как мы переходим от ForeignKey к GenericForeignKey"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('weather', '0004_alertcomment'),
    ]

    operations = [
        # Добавляем новые поля для GenericForeignKey
        migrations.AddField(
            model_name='alertcomment',
            name='content_type',
            field=models.ForeignKey(
                help_text='Тип предупреждения',
                null=True,  # Временно разрешаем null
                on_delete=django.db.models.deletion.CASCADE,
                to='contenttypes.contenttype'
            ),
        ),
        migrations.AddField(
            model_name='alertcomment',
            name='object_id',
            field=models.PositiveIntegerField(
                help_text='ID предупреждения',
                null=True  # Временно разрешаем null
            ),
        ),
        
        # Конвертируем существующие данные
        migrations.RunPython(convert_existing_comments, reverse_convert_comments),
        
        # Делаем поля обязательными
        migrations.AlterField(
            model_name='alertcomment',
            name='content_type',
            field=models.ForeignKey(
                help_text='Тип предупреждения',
                on_delete=django.db.models.deletion.CASCADE,
                to='contenttypes.contenttype'
            ),
        ),
        migrations.AlterField(
            model_name='alertcomment',
            name='object_id',
            field=models.PositiveIntegerField(help_text='ID предупреждения'),
        ),
        
        # Удаляем старое поле ForeignKey
        migrations.RemoveField(
            model_name='alertcomment',
            name='alert',
        ),
        
        # Добавляем индекс для производительности
        migrations.AddIndex(
            model_name='alertcomment',
            index=models.Index(
                fields=['content_type', 'object_id'],
                name='weather_alertcomment_content_type_object_id_idx'
            ),
        ),
    ]
