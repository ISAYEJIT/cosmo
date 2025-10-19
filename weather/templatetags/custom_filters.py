from django import template
import json
from utils.translation import translate_space_weather_text

register = template.Library()

@register.filter
def pprint(value):
    """Красивое форматирование JSON данных"""
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)

@register.filter
def translate(value):
    """Переводит текст с английского на русский"""
    if not value:
        return value
    try:
        return translate_space_weather_text(value)
    except Exception:
        return value

@register.filter
def forecast_color(forecast_data):
    """
    Определяет цвет для прогноза на основе вероятностей и уровней бурь
    
    Логика:
    - Желтый: G1 или R1-R2 выше 50%
    - Красный: G3+ или R1-R2 выше 70%
    - Зеленый: все остальное (по умолчанию)
    """
    if not forecast_data:
        return 'level-0'  # Зеленый по умолчанию
    
    try:
        # Проверяем геомагнитные бури (G)
        g_scale = forecast_data.get('G', {}).get('Scale', '0')
        g_scale_int = int(g_scale) if g_scale.isdigit() else 0
        
        # Проверяем радиоблэкауты (R)
        r_minor_prob = forecast_data.get('R', {}).get('MinorProb', 0)
        r_major_prob = forecast_data.get('R', {}).get('MajorProb', 0)
        
        # Преобразуем проценты в числа
        if isinstance(r_minor_prob, str):
            r_minor_prob = int(r_minor_prob) if r_minor_prob.isdigit() else 0
        if isinstance(r_major_prob, str):
            r_major_prob = int(r_major_prob) if r_major_prob.isdigit() else 0
        
        # Красный цвет: G3+ или R1-R2 выше 70%
        if g_scale_int >= 3 or r_minor_prob > 70:
            return 'level-red'
        
        # Желтый цвет: G1 или R1-R2 выше 50%
        if g_scale_int >= 1 or r_minor_prob > 50:
            return 'level-yellow'
        
        # Зеленый цвет по умолчанию
        return 'level-0'
        
    except (ValueError, TypeError, AttributeError):
        return 'level-0'  # Зеленый по умолчанию при ошибке

@register.filter
def test_forecast_color(forecast_data):
    """
    Тестовая функция для принудительного отображения цветов
    """
    if not forecast_data:
        return 'level-0'
    
    # Принудительно возвращаем желтый цвет для тестирования
    if 'today' in str(forecast_data).lower():
        return 'level-yellow'
    elif 'tomorrow' in str(forecast_data).lower():
        return 'level-red'
    else:
        return 'level-0'