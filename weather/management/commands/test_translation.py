from django.core.management.base import BaseCommand
from utils.translation import translate_alert_data, translate_space_weather_text

class Command(BaseCommand):
    help = 'Тестирование системы автоматического перевода'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Тестирование системы автоматического перевода...")
        self.stdout.write("=" * 60)
        
        # Тест 1: Перевод отдельного текста
        self.stdout.write("\n📝 Тест 1: Перевод отдельного текста")
        test_text = "Geomagnetic K-index of 5 expected"
        try:
            translated = translate_space_weather_text(test_text)
            self.stdout.write(f"Оригинал: {test_text}")
            self.stdout.write(f"Перевод:  {translated}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка перевода: {e}"))
        
        # Тест 2: Перевод данных алерта
        self.stdout.write("\n📊 Тест 2: Перевод данных алерта")
        test_alert = {
            'message_code': 'WARK04',
            'serial_number': '001',
            'warning_type': 'Geomagnetic K-index of 5 expected',
            'warning_condition': 'Minor',
            'noaa_scale': 'G1 - Minor',
            'potential_impacts': 'Weak power grid fluctuations can occur. Minor impact on satellite operations possible.',
            'description': 'Type II Radio Emission typically indicate eruptions on the sun',
            'forecast_data': 'Highest Storm Level Predicted by Day: Nov 15: G1 (Minor)',
            'estimated_velocity': '500 km/s estimated velocity'
        }
        
        self.stdout.write("Оригинальные данные:")
        for key, value in test_alert.items():
            if isinstance(value, str) and value:
                self.stdout.write(f"  {key}: {value}")
        
        try:
            translated_alert = translate_alert_data(test_alert)
            
            self.stdout.write("\nПереведенные данные:")
            for key, value in translated_alert.items():
                if isinstance(value, str) and value:
                    self.stdout.write(f"  {key}: {value}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка перевода алерта: {e}"))
        
        # Тест 3: Проверка сохранения специальных терминов
        self.stdout.write("\n🔒 Тест 3: Сохранение специальных терминов")
        test_with_terms = "NOAA Scale G2 - Moderate geomagnetic storm with GPS navigation problems"
        try:
            translated_terms = translate_space_weather_text(test_with_terms)
            self.stdout.write(f"Оригинал: {test_with_terms}")
            self.stdout.write(f"Перевод:  {translated_terms}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка перевода терминов: {e}"))
        
        self.stdout.write("\n✅ Тестирование завершено!")
        self.stdout.write("=" * 60)
