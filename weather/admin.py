from django.contrib import admin
from .models import SpaceWeatherAlert, AlertComment


@admin.register(SpaceWeatherAlert)
class SpaceWeatherAlertAdmin(admin.ModelAdmin):
    list_display = ('message_code', 'serial_number', 'warning_type', 'noaa_scale', 'issue_time', 'is_active', 'severity_level')
    list_filter = ('noaa_scale', 'warning_condition', 'is_processed', 'issue_time')
    search_fields = ('message_code', 'serial_number', 'warning_type', 'full_message')
    readonly_fields = ('created_at', 'is_active', 'severity_level')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('message_code', 'serial_number', 'issue_time')
        }),
        ('Предупреждение', {
            'fields': ('warning_type', 'warning_condition', 'noaa_scale')
        }),
        ('Период действия', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('Содержание', {
            'fields': ('full_message', 'potential_impacts')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'is_processed', 'is_active', 'severity_level')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(AlertComment)
class AlertCommentAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'alert_identifier', 'content_type', 'created_at', 'content_preview')
    list_filter = ('created_at', 'content_type')
    search_fields = ('author_name', 'content')
    readonly_fields = ('created_at', 'alert_identifier')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Предварительный просмотр'
    
    def alert_identifier(self, obj):
        return obj.alert_identifier
    alert_identifier.short_description = 'Предупреждение'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')
