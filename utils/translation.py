"""
Модуль для автоматического перевода с английского на русский язык
Использует Google Translate API для высококачественного перевода
"""

from deep_translator import GoogleTranslator
import time
import re


class AutoTranslator:
    """Автоматический переводчик на основе Google Translate"""
    
    def __init__(self):
        self.translator = GoogleTranslator(source='en', target='ru')
        self.cache = {} 
        self.last_request_time = 0
        self.min_delay = 0.1  # Минимальная задержка между запросами
        
        # Специальные термины, которые не нужно переводить
        self.preserve_terms = {
            'UTC', 'GMT', 'GPS', 'NASA', 'NOAA', 'API', 'SWPC',
            'G1', 'G2', 'G3', 'G4', 'G5',
            'R1', 'R2', 'R3', 'R4', 'R5',
            'S1', 'S2', 'S3', 'S4', 'S5',
            'Kp', 'Ap', 'Dst', 'F10.7', 'CME', 'SEP', 'GLE', 'SSC', 'IMF'
        }
    
    def _rate_limit(self):
        """Контроль частоты запросов к API"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_delay:
            time.sleep(self.min_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _preserve_special_terms(self, text):
        """Защищает специальные термины от перевода"""
        preserved = {}
        modified_text = text
        
        for i, term in enumerate(self.preserve_terms):
            if term in text:
                placeholder = f"__PRESERVE_{i}__"
                preserved[placeholder] = term
                modified_text = modified_text.replace(term, placeholder)
        
        return modified_text, preserved
    
    def _restore_special_terms(self, text, preserved):
        """Восстанавливает специальные термины после перевода"""
        for placeholder, original_term in preserved.items():
            text = text.replace(placeholder, original_term)
        return text
    
    def translate_text(self, text):
        """
        Переводит текст с английского на русский используя Google Translate
        
        Args:
            text (str): Исходный текст на английском
            
        Returns:
            str: Переведенный текст
        """
        if not text or not isinstance(text, str):
            return text
        
        # Удаляем лишние пробелы и переносы
        text = text.strip()
        if not text:
            return text
        
        # Проверяем кэш
        if text in self.cache:
            return self.cache[text]
        
        try:
            # Защищаем специальные термины
            protected_text, preserved_terms = self._preserve_special_terms(text)
            
            # Контролируем частоту запросов
            self._rate_limit()
            
            # Переводим текст
            translated = self.translator.translate(protected_text)
            
            # Восстанавливаем специальные термины
            translated = self._restore_special_terms(translated, preserved_terms)
            
            # Сохраняем в кэш
            self.cache[text] = translated
            
            return translated
            
        except Exception as e:
            print(f"Ошибка перевода: {e}")
            # В случае ошибки возвращаем оригинальный текст
            return text
    
    def translate_alert_fields(self, alert_data):
        """
        Переводит основные поля алерта
        
        Args:
            alert_data (dict): Словарь с данными алерта
            
        Returns:
            dict: Словарь с переведенными полями
        """
        if not isinstance(alert_data, dict):
            return alert_data
        
        translated_data = alert_data.copy()
        
        # Переводим основные поля
        fields_to_translate = [
            'warning_type',
            'warning_condition', 
            'noaa_scale',
            'potential_impacts',
            'summary',
            'description',
            'forecast_data',
            'estimated_velocity'
        ]
        
        for field in fields_to_translate:
            if field in translated_data and translated_data[field]:
                translated_data[field] = self.translate_text(translated_data[field])
        
        return translated_data
    
    def clear_cache(self):
        """Очищает кэш переводов"""
        self.cache.clear()
    
    def get_cache_size(self):
        """Возвращает размер кэша"""
        return len(self.cache)
    
    def set_delay(self, delay):
        """Устанавливает задержку между запросами"""
        self.min_delay = max(0, float(delay))


# Глобальный экземпляр переводчика
translator = AutoTranslator()


def translate_space_weather_text(text):
    """
    Быстрая функция для перевода текста космической погоды
    
    Args:
        text (str): Исходный текст
        
    Returns:
        str: Переведенный текст
    """
    return translator.translate_text(text)


def translate_alert_data(alert_data):
    """
    Быстрая функция для перевода данных алерта
    
    Args:
        alert_data (dict): Данные алерта
        
    Returns:
        dict: Переведенные данные алерта
    """
    return translator.translate_alert_fields(alert_data)


def clear_translation_cache():
    """Очищает кэш переводов"""
    translator.clear_cache()


def get_translation_cache_info():
    """Возвращает информацию о кэше переводов"""
    return {
        'cache_size': translator.get_cache_size(),
        'min_delay': translator.min_delay
    }
