from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class BaseSpaceWeatherAlert(models.Model):
    """Базовая модель для всех типов алертов"""
    message_code = models.CharField(max_length=20, help_text="Space Weather Message Code")
    serial_number = models.CharField(max_length=10, help_text="Serial Number")
    issue_time = models.DateTimeField(help_text="Issue Time UTC")
    warning_type = models.CharField(max_length=200, help_text="Тип предупреждения")
    full_message = models.TextField(help_text="Полный текст предупреждения")
    created_at = models.DateTimeField(default=timezone.now, help_text="Время создания записи")
    is_processed = models.BooleanField(default=True, help_text="Обработано ли предупреждение")
    
    class Meta:
        abstract = True
        ordering = ['-issue_time']


class TypeTRadioAlert(BaseSpaceWeatherAlert):
    """T* - Type II Radio Emission Alerts"""
    begin_time = models.DateTimeField(null=True, blank=True, help_text="Время начала события")
    estimated_velocity = models.CharField(max_length=100, null=True, blank=True, help_text="Оценочная скорость")
    description = models.TextField(null=True, blank=True, help_text="Описание события")
    
    class Meta:
        verbose_name = "Алерт радиоизлучения типа II"
        verbose_name_plural = "Алерты радиоизлучения типа II"
        unique_together = ['message_code', 'serial_number', 'issue_time']


class TypeKGeomagneticAlert(BaseSpaceWeatherAlert):
    """K* - K-index Events"""
    valid_from = models.DateTimeField(null=True, blank=True, help_text="Valid From UTC")
    valid_to = models.DateTimeField(null=True, blank=True, help_text="Valid To UTC")
    begin_time = models.DateTimeField(null=True, blank=True, help_text="Время начала события")
    warning_condition = models.CharField(max_length=50, null=True, blank=True, help_text="Warning Condition")
    noaa_scale = models.CharField(max_length=20, null=True, blank=True, help_text="NOAA Scale")
    potential_impacts = models.TextField(null=True, blank=True, help_text="Потенциальные воздействия")
    
    class Meta:
        verbose_name = "Геомагнитный алерт K-индекса"
        verbose_name_plural = "Геомагнитные алерты K-индекса"
        unique_together = ['message_code', 'serial_number', 'issue_time']


class TypeEElectronAlert(BaseSpaceWeatherAlert):
    """E* - Electron Flux Events"""
    begin_time = models.DateTimeField(null=True, blank=True, help_text="Время начала события")
    maximum_flux = models.CharField(max_length=100, null=True, blank=True, help_text="Максимальный поток")
    potential_impacts = models.TextField(null=True, blank=True, help_text="Потенциальные воздействия")
    
    class Meta:
        verbose_name = "Алерт потока электронов"
        verbose_name_plural = "Алерты потока электронов"
        unique_together = ['message_code', 'serial_number', 'issue_time']


class TypeAForecastAlert(BaseSpaceWeatherAlert):
    """A* - Storm Watch/Forecast"""
    forecast_data = models.TextField(null=True, blank=True, help_text="Данные прогноза")
    potential_impacts = models.TextField(null=True, blank=True, help_text="Потенциальные воздействия")
    
    class Meta:
        verbose_name = "Прогноз геомагнитных бурь"
        verbose_name_plural = "Прогнозы геомагнитных бурь"
        unique_together = ['message_code', 'serial_number', 'issue_time']


class SpaceWeatherAlert(models.Model):
    """Модель для хранения предупреждений космической погоды от NOAA"""
    
    # Основные поля из алерта
    message_code = models.CharField(max_length=20, help_text="Space Weather Message Code")
    serial_number = models.CharField(max_length=10, help_text="Serial Number")
    issue_time = models.DateTimeField(help_text="Issue Time UTC")
    
    # Содержание предупреждения
    warning_type = models.CharField(max_length=100, help_text="Тип предупреждения")
    valid_from = models.DateTimeField(null=True, blank=True, help_text="Valid From UTC")
    valid_to = models.DateTimeField(null=True, blank=True, help_text="Valid To UTC")
    warning_condition = models.CharField(max_length=50, null=True, blank=True, help_text="Warning Condition")
    
    # NOAA Scale
    noaa_scale = models.CharField(max_length=20, null=True, blank=True, help_text="NOAA Scale (например, G2 - Moderate)")
    
    # Полный текст и воздействия
    full_message = models.TextField(help_text="Полный текст предупреждения")
    potential_impacts = models.TextField(null=True, blank=True, help_text="Потенциальные воздействия")
    description = models.TextField(null=True, blank=True, help_text="Описание события (переведенное)")
    
    # Дополнительные поля для детальной информации
    begin_time = models.DateTimeField(null=True, blank=True, help_text="Время начала события")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Время окончания события")
    maximum_time = models.DateTimeField(null=True, blank=True, help_text="Время максимума события")
    estimated_velocity = models.CharField(max_length=100, null=True, blank=True, help_text="Оценочная скорость")
    
    # Специфические поля для разных типов алертов
    maximum_flux = models.CharField(max_length=100, null=True, blank=True, help_text="Максимальный поток (для ALTEF3)")
    forecast_data = models.TextField(null=True, blank=True, help_text="Данные прогноза (для WATA20)")
    
    # Метаданные
    created_at = models.DateTimeField(default=timezone.now, help_text="Время создания записи")
    is_processed = models.BooleanField(default=True, help_text="Обработано ли предупреждение")
    
    class Meta:
        ordering = ['-issue_time']
        verbose_name = "Предупреждение космической погоды"
        verbose_name_plural = "Предупреждения космической погоды"
        unique_together = ['message_code', 'serial_number', 'issue_time']
    
    def __str__(self):
        return f"{self.message_code}-{self.serial_number}: {self.warning_type} ({self.issue_time})"
    
    @property
    def is_active(self):
        """Проверка, активно ли предупреждение"""
        now = timezone.now()
        if self.valid_to:
            valid_to_aware = self.valid_to
            if timezone.is_naive(valid_to_aware):
                valid_to_aware = timezone.make_aware(valid_to_aware, timezone.utc)
            return now <= valid_to_aware
        return True
    
    @property
    def severity_level(self):
        """Уровень серьезности по NOAA Scale"""
        if not self.noaa_scale:
            return 0
        if 'G1' in self.noaa_scale or 'R1' in self.noaa_scale or 'S1' in self.noaa_scale:
            return 1
        elif 'G2' in self.noaa_scale or 'R2' in self.noaa_scale or 'S2' in self.noaa_scale:
            return 2
        elif 'G3' in self.noaa_scale or 'R3' in self.noaa_scale or 'S3' in self.noaa_scale:
            return 3
        elif 'G4' in self.noaa_scale or 'R4' in self.noaa_scale or 'S4' in self.noaa_scale:
            return 4
        elif 'G5' in self.noaa_scale or 'R5' in self.noaa_scale or 'S5' in self.noaa_scale:
            return 5
        return 0


class AlertComment(models.Model):
    """Модель для комментариев к предупреждениям космической погоды"""
    
    # Полиморфная связь с любыми типами алертов
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, help_text="Тип предупреждения")
    object_id = models.PositiveIntegerField(help_text="ID предупреждения")
    alert = GenericForeignKey('content_type', 'object_id')
    
    author_name = models.CharField(max_length=100, help_text="Имя автора комментария")
    content = models.TextField(max_length=1000, help_text="Текст комментария")
    created_at = models.DateTimeField(default=timezone.now, help_text="Время создания комментария")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Комментарий к предупреждению"
        verbose_name_plural = "Комментарии к предупреждениям"
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        alert_code = getattr(self.alert, 'message_code', 'N/A')
        alert_serial = getattr(self.alert, 'serial_number', 'N/A')
        return f"Комментарий от {self.author_name} к {alert_code}-{alert_serial}"
    
    @property
    def alert_identifier(self):
        """Возвращает идентификатор алерта в формате код-серийный_номер"""
        if hasattr(self.alert, 'message_code') and hasattr(self.alert, 'serial_number'):
            return f"{self.alert.message_code}-{self.alert.serial_number}"
        return f"Alert #{self.object_id}"