from django.shortcuts import render
from django.http import JsonResponse
import asyncio
import re
from datetime import datetime
from django.utils import timezone
from datetime import timezone as dt_timezone
from django.utils.dateparse import parse_datetime
from utils.proxy_utils import make_request_with_proxy
from utils.translation import translate_space_weather_text, translate_alert_data
from ..models import SpaceWeatherAlert, TypeTRadioAlert, TypeKGeomagneticAlert, TypeEElectronAlert, TypeAForecastAlert, AlertComment
from django.contrib.contenttypes.models import ContentType


def translate_condition_text(text):
    """Переводит английские значения на русский"""
    translations = {
        'none': 'нет',
        'minor': 'слабые',
        'moderate': 'умеренные',
        'strong': 'сильные',
        'severe': 'очень сильные',
        'extreme': 'экстремальные'
    }
    return translations.get(text.lower() if text else '', text)


def translate_alert_text(text):
    """Переводит текст алертов на русский язык"""
    if not text:
        return text
    
    translations = {
        # Основные термины
        'Type II Radio Emission': 'Радиоизлучение типа II',
        'coronal mass ejection': 'корональный выброс массы',
        'flare event': 'вспышечное событие',
        'eruptions on the sun': 'извержения на Солнце',
        'typically indicate': 'обычно указывают',
        'is associated with': 'связано с',
        'occur in association with': 'происходят в связи с',
        'Geomagnetic K-index': 'Геомагнитный K-индекс',
        'expected': 'ожидается',
        'Area of impact primarily poleward of': 'Область воздействия преимущественно севернее',
        'degrees Geomagnetic Latitude': 'градусов геомагнитной широты',
        
        # Потенциальные воздействия
        'Potential Impacts': 'Потенциальные воздействия',
        'Induced Currents': 'Наведенные токи',
        'Weak power grid fluctuations can occur': 'Могут возникнуть слабые колебания энергосистемы',
        'power grid fluctuations can occur': 'могут возникнуть колебания энергосистемы',
        'Voltage corrections may be required': 'Может потребоваться коррекция напряжения',
        'spacecraft charging': 'зарядка космических аппаратов',
        'increased drag on low Earth-orbiting satellites': 'увеличенное сопротивление для низкоорбитальных спутников',
        'satellite orientation irregularities': 'нарушения ориентации спутников',
        'surface charging': 'поверхностная зарядка',
        'Aurora': 'Полярное сияние',
        'aurora': 'полярное сияние',
        'may be visible at high latitudes': 'может быть видно в высоких широтах',
        'visible at high latitudes': 'видно в высоких широтах',
        'such as Canada and Alaska': 'таких как Канада и Аляска',
        'HF radio': 'КВ радио',
        'radio communications': 'радиосвязь',
        'GPS navigation': 'GPS навигация',
        'navigation problems': 'проблемы навигации',
        'blackout': 'блэкаут',
        'blackouts': 'блэкауты',
        'power systems': 'энергосистемы',
        'transformer damage': 'повреждение трансформаторов',
        'pipeline currents': 'токи в трубопроводах',
        'may experience': 'может испытывать',
        'possible': 'возможно',
        'likely': 'вероятно',
        'Minor': 'незначительные',
        'minor': 'незначительные',
        'Moderate': 'умеренные',
        'moderate': 'умеренные',
        'Strong': 'сильные',
        'strong': 'сильные',
        'Severe': 'очень сильные',
        'severe': 'очень сильные',
        'Extreme': 'экстремальные',
        'extreme': 'экстремальные'
    }
    
    translated = text
    for english, russian in translations.items():
        translated = translated.replace(english, russian)
    
    return translated


def parse_type_t_radio(message):
    """Парсер для T* - Type II Radio Emission"""
    parsed = {}
    alert_match = re.search(r'ALERT:\s*([^\r\n]+)', message)
    if alert_match:
        parsed['warning_type'] = alert_match.group(1).strip()
    
    begin_match = re.search(r'Begin Time:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if begin_match:
        try:
            parsed['begin_time'] = timezone.make_aware(datetime.strptime(begin_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            parsed['begin_time'] = None
    
    velocity_match = re.search(r'Estimated Velocity:\s*([^\r\n]+)', message)
    if velocity_match:
        parsed['estimated_velocity'] = velocity_match.group(1).strip()
    
    desc_match = re.search(r'Description:\s*([^\r\n]+(?:\r?\n[^\r\n]+)*)', message, re.MULTILINE)
    if desc_match:
        parsed['description'] = desc_match.group(1).strip()
    
    return parsed


def parse_type_k_geomagnetic(message):
    """Парсер для K* - K-index Events"""
    parsed = {}
    
    alert_match = re.search(r'(ALERT|WARNING|EXTENDED WARNING):\s*([^\r\n]+)', message)
    if alert_match:
        parsed['warning_type'] = f"{alert_match.group(1)}: {alert_match.group(2).strip()}"
    
    valid_from_match = re.search(r'Valid From:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if valid_from_match:
        try:
            parsed['valid_from'] = timezone.make_aware(datetime.strptime(valid_from_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    valid_to_match = re.search(r'Valid (To|Until):\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if valid_to_match:
        try:
            parsed['valid_to'] = timezone.make_aware(datetime.strptime(valid_to_match.group(2), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    threshold_match = re.search(r'Threshold Reached:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if threshold_match:
        try:
            parsed['begin_time'] = timezone.make_aware(datetime.strptime(threshold_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    condition_match = re.search(r'Warning Condition:\s*([^\r\n]+)', message)
    if condition_match:
        parsed['warning_condition'] = condition_match.group(1).strip()
    
    scale_match = re.search(r'NOAA Scale:\s*([^\r\n]+)', message)
    if scale_match:
        parsed['noaa_scale'] = scale_match.group(1).strip()
    
    impacts_match = re.search(r'Potential Impacts:(.*?)(?=\r?\n\r?\n|$)', message, re.DOTALL)
    if impacts_match:
        impacts_text = impacts_match.group(1).strip()
        # Сохраняем как есть, перевод будет выполнен в save_alert_to_db
        parsed['potential_impacts'] = impacts_text
    
    return parsed


def parse_type_e_electron(message):
    """Парсер для E* - Electron Flux Events"""
    parsed = {}
    
    alert_match = re.search(r'(ALERT|CONTINUED ALERT):\s*([^\r\n]+)', message)
    if alert_match:
        parsed['warning_type'] = f"{alert_match.group(1)}: {alert_match.group(2).strip()}"
    
    begin_match = re.search(r'Begin Time:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if begin_match:
        try:
            parsed['begin_time'] = timezone.make_aware(datetime.strptime(begin_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    threshold_match = re.search(r'Threshold Reached:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if threshold_match:
        try:
            parsed['begin_time'] = timezone.make_aware(datetime.strptime(threshold_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    flux_match = re.search(r'Yesterday Maximum 2MeV Flux:\s*([^\r\n]+)', message)
    if flux_match:
        parsed['maximum_flux'] = flux_match.group(1).strip()
    
    impacts_match = re.search(r'Potential Impacts:(.*?)(?=\r?\n\r?\n|$)', message, re.DOTALL)
    if impacts_match:
        impacts_text = impacts_match.group(1).strip()
        # Сохраняем как есть, перевод будет выполнен в save_alert_to_db
        parsed['potential_impacts'] = impacts_text
    
    return parsed


def parse_type_a_forecast(message):
    """Парсер для A* - Storm Watch/Forecast"""
    parsed = {}
    
    watch_match = re.search(r'WATCH:\s*([^\r\n]+)', message)
    if watch_match:
        parsed['warning_type'] = watch_match.group(1).strip()
    
    forecast_match = re.search(r'Highest Storm Level Predicted by Day:(.*?)(?=THIS SUPERSEDES|NOAA Space|$)', message, re.DOTALL)
    if forecast_match:
        parsed['forecast_data'] = forecast_match.group(1).strip()
    
    impacts_match = re.search(r'Potential Impacts:(.*?)(?=\r?\n\r?\n|$)', message, re.DOTALL)
    if impacts_match:
        impacts_text = impacts_match.group(1).strip()
        # Сохраняем как есть, перевод будет выполнен в save_alert_to_db
        parsed['potential_impacts'] = impacts_text
    
    return parsed


def parse_type_w_watch(message):
    """Парсер для W* - Watch/Alert"""
    parsed = {}
    
    # Ищем различные типы предупреждений
    alert_match = re.search(r'(ALERT|WARNING|WATCH|EXTENDED WARNING):\s*([^\r\n]+)', message)
    if alert_match:
        parsed['warning_type'] = f"{alert_match.group(1)}: {alert_match.group(2).strip()}"
    
    # Время действия
    valid_from_match = re.search(r'Valid From:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if valid_from_match:
        try:
            parsed['valid_from'] = timezone.make_aware(datetime.strptime(valid_from_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    valid_to_match = re.search(r'Valid (To|Until):\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if valid_to_match:
        try:
            parsed['valid_to'] = timezone.make_aware(datetime.strptime(valid_to_match.group(2), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    # NOAA Scale
    scale_match = re.search(r'NOAA Scale:\s*([^\r\n]+)', message)
    if scale_match:
        parsed['noaa_scale'] = scale_match.group(1).strip()
    
    # Потенциальные воздействия
    impacts_match = re.search(r'Potential Impacts:(.*?)(?=\r?\n\r?\n|$)', message, re.DOTALL)
    if impacts_match:
        impacts_text = impacts_match.group(1).strip()
        parsed['potential_impacts'] = impacts_text
    
    # Описание
    desc_match = re.search(r'Description:\s*([^\r\n]+(?:\r?\n[^\r\n]+)*)', message, re.MULTILINE)
    if desc_match:
        parsed['description'] = desc_match.group(1).strip()
    
    return parsed


def parse_unknown_type(message):
    """Универсальный парсер для неизвестных типов алертов"""
    parsed = {}
    
    # Ищем различные типы предупреждений
    alert_match = re.search(r'(ALERT|WARNING|WATCH|EXTENDED WARNING|CONTINUED ALERT):\s*([^\r\n]+)', message)
    if alert_match:
        parsed['warning_type'] = f"{alert_match.group(1)}: {alert_match.group(2).strip()}"
    
    # Время действия
    valid_from_match = re.search(r'Valid From:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if valid_from_match:
        try:
            parsed['valid_from'] = timezone.make_aware(datetime.strptime(valid_from_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    valid_to_match = re.search(r'Valid (To|Until):\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if valid_to_match:
        try:
            parsed['valid_to'] = timezone.make_aware(datetime.strptime(valid_to_match.group(2), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            pass
    
    # NOAA Scale
    scale_match = re.search(r'NOAA Scale:\s*([^\r\n]+)', message)
    if scale_match:
        parsed['noaa_scale'] = scale_match.group(1).strip()
    
    # Потенциальные воздействия
    impacts_match = re.search(r'Potential Impacts:(.*?)(?=\r?\n\r?\n|$)', message, re.DOTALL)
    if impacts_match:
        impacts_text = impacts_match.group(1).strip()
        parsed['potential_impacts'] = impacts_text
    
    # Описание
    desc_match = re.search(r'Description:\s*([^\r\n]+(?:\r?\n[^\r\n]+)*)', message, re.MULTILINE)
    if desc_match:
        parsed['description'] = desc_match.group(1).strip()
    
    return parsed


def parse_alert_message(alert_data):
    """Универсальный парсер с роутингом по первой букве кода"""
    if not isinstance(alert_data, dict):
        return None
    
    message = alert_data.get('message', '')
    if not message:
        return None
    
    parsed = {
        'product_id': alert_data.get('product_id', ''),
        'issue_datetime': alert_data.get('issue_datetime', ''),
        'raw_message': message
    }
    
    code_match = re.search(r'Space Weather Message Code:\s*([A-Z0-9]+)', message)
    if code_match:
        parsed['message_code'] = code_match.group(1)
        print(f"DEBUG: Found message_code: {code_match.group(1)}")
    else:
        print(f"DEBUG: No message_code found in message")
    
    serial_match = re.search(r'Serial Number:\s*(\d+)', message)
    if serial_match:
        parsed['serial_number'] = serial_match.group(1)
    
    issue_match = re.search(r'Issue Time:\s*([0-9]{4}\s+[A-Za-z]{3}\s+[0-9]{2}\s+[0-9]{4}\s+UTC)', message)
    if issue_match:
        try:
            parsed['issue_time'] = timezone.make_aware(datetime.strptime(issue_match.group(1), '%Y %b %d %H%M UTC'), dt_timezone.utc)
        except ValueError:
            parsed['issue_time'] = None
    
    # Роутинг по первой букве message_code
    first_letter = parsed.get('message_code', '')[0:1].upper()
    print(f"DEBUG: Routing with first_letter: {first_letter}")
    
    if first_letter == 'T':
        specific_data = parse_type_t_radio(message)
    elif first_letter == 'K':
        specific_data = parse_type_k_geomagnetic(message)
    elif first_letter == 'E':
        specific_data = parse_type_e_electron(message)
    elif first_letter == 'A':
        specific_data = parse_type_a_forecast(message)
    elif first_letter == 'W':
        specific_data = parse_type_w_watch(message)
    else:
        # Для неизвестных типов используем универсальный парсер
        specific_data = parse_unknown_type(message)
    
    parsed.update(specific_data)
    return parsed


def save_alert_to_db(parsed_alert):
    """Сохранение алерта в соответствующую таблицу по типу"""
    if not parsed_alert:
        return None
    
    # Определяем тип по первой букве message_code
    first_letter = parsed_alert.get('message_code', '')[0:1].upper()
    
    # Отладочная информация
    print(f"DEBUG: Saving alert with first_letter: {first_letter}, message_code: {parsed_alert.get('message_code', '')}")
    print(f"DEBUG: Full parsed_alert keys: {list(parsed_alert.keys())}")
    print(f"DEBUG: Product_id: {parsed_alert.get('product_id', '')}")
    print(f"DEBUG: Message_code: {parsed_alert.get('message_code', '')}")
    
    # Переводим текстовые поля с помощью translation.py
    translated_alert = translate_alert_data(parsed_alert)
    
    # Базовые данные для всех типов
    base_data = {
        'message_code': translated_alert.get('message_code', ''),
        'serial_number': translated_alert.get('serial_number', ''),
        'issue_time': translated_alert.get('issue_time'),
        'warning_type': translated_alert.get('warning_type', ''),
        'full_message': translated_alert.get('raw_message', '')
    }
    
    # Удаляем None значения из базовых данных
    base_data = {k: v for k, v in base_data.items() if v is not None}
    
    try:
        if first_letter == 'T':
            # T* - Type II Radio Emission
            existing = TypeTRadioAlert.objects.filter(**{k: v for k, v in base_data.items() if k in ['message_code', 'serial_number', 'issue_time']}).first()
            if existing:
                return existing
            
            alert_data = base_data.copy()
            alert_data.update({
                'begin_time': translated_alert.get('begin_time'),
                'estimated_velocity': translated_alert.get('estimated_velocity', ''),
                'description': translated_alert.get('description', '')
            })
            alert_data = {k: v for k, v in alert_data.items() if v is not None}
            return TypeTRadioAlert.objects.create(**alert_data)
            
        elif first_letter == 'K':
            # K* - K-index Events
            existing = TypeKGeomagneticAlert.objects.filter(**{k: v for k, v in base_data.items() if k in ['message_code', 'serial_number', 'issue_time']}).first()
            if existing:
                return existing
            
            alert_data = base_data.copy()
            alert_data.update({
                'valid_from': translated_alert.get('valid_from'),
                'valid_to': translated_alert.get('valid_to'),
                'begin_time': translated_alert.get('begin_time'),
                'warning_condition': translated_alert.get('warning_condition', ''),
                'noaa_scale': translated_alert.get('noaa_scale', ''),
                'potential_impacts': translated_alert.get('potential_impacts', '')
            })
            alert_data = {k: v for k, v in alert_data.items() if v is not None}
            return TypeKGeomagneticAlert.objects.create(**alert_data)
            
        elif first_letter == 'E':
            # E* - Electron Flux Events
            existing = TypeEElectronAlert.objects.filter(**{k: v for k, v in base_data.items() if k in ['message_code', 'serial_number', 'issue_time']}).first()
            if existing:
                return existing
            
            alert_data = base_data.copy()
            alert_data.update({
                'begin_time': translated_alert.get('begin_time'),
                'maximum_flux': translated_alert.get('maximum_flux', ''),
                'potential_impacts': translated_alert.get('potential_impacts', '')
            })
            alert_data = {k: v for k, v in alert_data.items() if v is not None}
            return TypeEElectronAlert.objects.create(**alert_data)
            
        elif first_letter == 'A':
            # A* - Storm Watch/Forecast
            existing = TypeAForecastAlert.objects.filter(**{k: v for k, v in base_data.items() if k in ['message_code', 'serial_number', 'issue_time']}).first()
            if existing:
                return existing
            
            alert_data = base_data.copy()
            alert_data.update({
                'forecast_data': translated_alert.get('forecast_data', ''),
                'potential_impacts': translated_alert.get('potential_impacts', '')
            })
            alert_data = {k: v for k, v in alert_data.items() if v is not None}
            return TypeAForecastAlert.objects.create(**alert_data)
            
        elif first_letter == 'W':
            # W* - Watch/Alert (сохраняем в основную таблицу с дополнительными полями)
            existing = SpaceWeatherAlert.objects.filter(**{k: v for k, v in base_data.items() if k in ['message_code', 'serial_number', 'issue_time']}).first()
            if existing:
                return existing
            
            alert_data = base_data.copy()
            alert_data.update({
                'valid_from': translated_alert.get('valid_from'),
                'valid_to': translated_alert.get('valid_to'),
                'begin_time': translated_alert.get('begin_time'),
                'end_time': translated_alert.get('end_time'),
                'warning_condition': translated_alert.get('warning_condition', ''),
                'noaa_scale': translated_alert.get('noaa_scale', ''),
                'potential_impacts': translated_alert.get('potential_impacts', ''),
                'description': translated_alert.get('description', ''),
                'estimated_velocity': translated_alert.get('estimated_velocity', ''),
                'maximum_flux': translated_alert.get('maximum_flux', ''),
                'forecast_data': translated_alert.get('forecast_data', '')
            })
            alert_data = {k: v for k, v in alert_data.items() if v is not None}
            return SpaceWeatherAlert.objects.create(**alert_data)
            
        else:
            # Неизвестный тип - сохраняем в старую таблицу
            existing = SpaceWeatherAlert.objects.filter(**{k: v for k, v in base_data.items() if k in ['message_code', 'serial_number', 'issue_time']}).first()
            if existing:
                return existing
            
            # Для неизвестных типов добавляем все возможные поля
            alert_data = base_data.copy()
            alert_data.update({
                'valid_from': translated_alert.get('valid_from'),
                'valid_to': translated_alert.get('valid_to'),
                'begin_time': translated_alert.get('begin_time'),
                'end_time': translated_alert.get('end_time'),
                'warning_condition': translated_alert.get('warning_condition', ''),
                'noaa_scale': translated_alert.get('noaa_scale', ''),
                'potential_impacts': translated_alert.get('potential_impacts', ''),
                'description': translated_alert.get('description', ''),
                'estimated_velocity': translated_alert.get('estimated_velocity', ''),
                'maximum_flux': translated_alert.get('maximum_flux', ''),
                'forecast_data': translated_alert.get('forecast_data', '')
            })
            alert_data = {k: v for k, v in alert_data.items() if v is not None}
            return SpaceWeatherAlert.objects.create(**alert_data)
            
    except Exception as e:
        return None


async def fetch_noaa_current_conditions():
    """Получение текущих условий космической погоды"""
    url = "https://services.swpc.noaa.gov/products/noaa-scales.json"
    status, data = await make_request_with_proxy(url)
    if status == 200 and (not isinstance(data, dict) or 'error' not in data):
        return {"source": "Current Conditions", "data": data, "status": "success"}
    message = data.get('message', f"API ошибка {status}") if isinstance(data, dict) else f"API ошибка {status}"
    return {"source": "Current Conditions", "data": {}, "status": "error", "message": message}


async def fetch_noaa_alerts():
    """Получение активных предупреждений"""
    url = "https://services.swpc.noaa.gov/products/alerts.json"
    status, data = await make_request_with_proxy(url)
    if status == 200 and isinstance(data, list):
        # Парсим алерты, но НЕ сохраняем в базу (это будет делаться отдельно в админке)
        parsed_alerts = []
        for alert_data in data:
            parsed_alert = parse_alert_message(alert_data)
            if parsed_alert:
                parsed_alerts.append(parsed_alert)
        
        return {"source": "Alerts", "data": data, "status": "success", "parsed_count": len(parsed_alerts)}
    return {"source": "Alerts", "data": [], "status": "error", "message": f"API ошибка {status}"}


async def fetch_noaa_solar_wind():
    """Получение данных солнечного ветра"""
    url = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
    status, data = await make_request_with_proxy(url)
    if status == 200 and isinstance(data, list) and len(data) > 1:
        rows = data[1:]
        last_rows = rows[-3:]
        result = [["time_tag","density","speed","temperature"]]
        for r in last_rows:
            if isinstance(r, list) and len(r) >= 4:
                result.append([str(r[0]), str(r[1]), str(r[2]), str(r[3])])
        return {"source": "Solar Wind", "data": result, "status": "success"}
    return {"source": "Solar Wind", "data": [], "status": "error", "message": f"API ошибка {status}"}


async def fetch_noaa_detailed_data():
    """Получение всех детальных данных NOAA SWPC"""
    tasks = [
        fetch_noaa_current_conditions(),
        fetch_noaa_alerts(),
        fetch_noaa_solar_wind()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Обработка результатов
    detailed_data = {}
    for result in results:
        if isinstance(result, dict) and result.get('status') == 'success':
            source = result['source']
            # Преобразуем ключи для безопасного использования в шаблонах
            if source == '3-Day Forecast':
                detailed_data['forecast'] = result['data']
            elif source == 'Current Conditions':
                # Преобразуем отрицательные ключи в безопасные имена
                conditions_data = result['data']
                if isinstance(conditions_data, dict):
                    # Создаем новый словарь с безопасными ключами и переводом
                    safe_conditions = {}
                    for key, value in conditions_data.items():
                        # Переводим текстовые значения
                        if isinstance(value, dict):
                            translated_value = value.copy()
                            for scale in ['R', 'S', 'G']:
                                if scale in translated_value and 'Text' in translated_value[scale]:
                                    translated_value[scale]['Text'] = translate_condition_text(translated_value[scale]['Text'])
                        else:
                            translated_value = value
                            
                        if key == '-1':
                            safe_conditions['past_24h'] = translated_value
                        elif key == '0':
                            safe_conditions['current'] = translated_value
                        elif key == '1':
                            safe_conditions['today_forecast'] = translated_value
                        elif key == '2':
                            safe_conditions['tomorrow_forecast'] = translated_value
                        elif key == '3':
                            safe_conditions['day_after_forecast'] = translated_value
                        else:
                            safe_conditions[key] = translated_value
                    detailed_data['current_conditions'] = safe_conditions
                else:
                    detailed_data['current_conditions'] = conditions_data
            elif source == 'Alerts':
                detailed_data['alerts'] = result['data']
            elif source == 'Summary':
                detailed_data['summary'] = result['data']
            elif source == 'Solar Wind':
                detailed_data['solar_wind'] = result['data']
        elif isinstance(result, Exception):
            detailed_data['error'] = str(result)
    
    # Алерты из БД будут добавлены в синхронной части
    
    return detailed_data


def noaa_detailed(request):
    """Детальная страница NOAA SWPC с полными метриками"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        noaa_data = loop.run_until_complete(fetch_noaa_detailed_data())
    finally:
        loop.close()
    
    # Добавляем алерты из всех таблиц БД с пагинацией
    from itertools import chain
    from operator import attrgetter
    from django.core.paginator import Paginator
    
    t_alerts = list(TypeTRadioAlert.objects.all())
    k_alerts = list(TypeKGeomagneticAlert.objects.all()) 
    e_alerts = list(TypeEElectronAlert.objects.all())
    a_alerts = list(TypeAForecastAlert.objects.all())
    old_alerts = list(SpaceWeatherAlert.objects.all())
    
    # Объединяем и сортируем по времени
    all_alerts = list(chain(t_alerts, k_alerts, e_alerts, a_alerts, old_alerts))
    all_alerts.sort(key=attrgetter('issue_time'), reverse=True)
    
    # Пагинация
    paginator = Paginator(all_alerts, 20)  # 20 алертов на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    noaa_data['db_alerts'] = page_obj
    
    context = {
        'title': 'NOAA Space Weather Prediction Center - Детальные метрики',
        'noaa_data': noaa_data,
        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return render(request, 'noaa_detailed.html', context)


def alert_detail(request, alert_id):
    """Детальная страница отдельного события"""
    alert = None
    alert_type = None
    
    # Ищем алерт во всех таблицах
    try:
        alert = SpaceWeatherAlert.objects.get(id=alert_id)
        alert_type = 'Legacy'
    except SpaceWeatherAlert.DoesNotExist:
        try:
            alert = TypeTRadioAlert.objects.get(id=alert_id)
            alert_type = 'T-Radio'
        except TypeTRadioAlert.DoesNotExist:
            try:
                alert = TypeKGeomagneticAlert.objects.get(id=alert_id)
                alert_type = 'K-Geomagnetic'
            except TypeKGeomagneticAlert.DoesNotExist:
                try:
                    alert = TypeEElectronAlert.objects.get(id=alert_id)
                    alert_type = 'E-Electron'
                except TypeEElectronAlert.DoesNotExist:
                    try:
                        alert = TypeAForecastAlert.objects.get(id=alert_id)
                        alert_type = 'A-Forecast'
                    except TypeAForecastAlert.DoesNotExist:
                        pass
    
    if alert:
        # Получаем комментарии для любого типа алерта через GenericForeignKey
        alert_content_type = ContentType.objects.get_for_model(alert)
        comments = AlertComment.objects.filter(
            content_type=alert_content_type,
            object_id=alert.id
        ).order_by('-created_at')
        
        # Создаем контекст с дополнительной информацией
        context = {
            'alert': alert,
            'alert_type': alert_type,
            'comments': comments,
            'comments_available': True,  # Теперь комментарии доступны для всех типов
            'page_title': f'Событие {alert.message_code}-{alert.serial_number}',
            'breadcrumbs': [
                {'title': 'NOAA Детально', 'url': 'noaa_detailed'},
                {'title': f'{alert.warning_type[:50]}...', 'url': ''},
            ]
        }
        
        return render(request, 'alert_detail.html', context)
    else:
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.error(request, 'Событие не найдено.')
        return redirect('noaa_detailed')


def add_comment(request, alert_id):
    """Добавление комментария к предупреждению"""
    if request.method == 'POST':
        try:
            # Находим алерт среди всех типов
            alert = None
            alert_type = None
            
            # Ищем алерт во всех таблицах
            try:
                alert = SpaceWeatherAlert.objects.get(id=alert_id)
                alert_type = 'Legacy'
            except SpaceWeatherAlert.DoesNotExist:
                try:
                    alert = TypeTRadioAlert.objects.get(id=alert_id)
                    alert_type = 'T-Radio'
                except TypeTRadioAlert.DoesNotExist:
                    try:
                        alert = TypeKGeomagneticAlert.objects.get(id=alert_id)
                        alert_type = 'K-Geomagnetic'
                    except TypeKGeomagneticAlert.DoesNotExist:
                        try:
                            alert = TypeEElectronAlert.objects.get(id=alert_id)
                            alert_type = 'E-Electron'
                        except TypeEElectronAlert.DoesNotExist:
                            try:
                                alert = TypeAForecastAlert.objects.get(id=alert_id)
                                alert_type = 'A-Forecast'
                            except TypeAForecastAlert.DoesNotExist:
                                pass
            
            if not alert:
                from django.contrib import messages
                messages.error(request, 'Событие не найдено.')
                return redirect('noaa_detailed')
            
            # Получаем данные из формы
            author_name = request.POST.get('author_name', '').strip()
            content = request.POST.get('content', '').strip()
            
            # Валидация
            if not author_name or not content:
                from django.contrib import messages
                messages.error(request, 'Пожалуйста, заполните все поля.')
                return redirect('alert_detail', alert_id=alert_id)
            
            if len(author_name) > 100:
                from django.contrib import messages
                messages.error(request, 'Имя не должно превышать 100 символов.')
                return redirect('alert_detail', alert_id=alert_id)
                
            if len(content) > 1000:
                from django.contrib import messages
                messages.error(request, 'Комментарий не должен превышать 1000 символов.')
                return redirect('alert_detail', alert_id=alert_id)
            
            # Создаем комментарий с использованием GenericForeignKey
            alert_content_type = ContentType.objects.get_for_model(alert)
            comment = AlertComment.objects.create(
                content_type=alert_content_type,
                object_id=alert.id,
                author_name=author_name,
                content=content
            )
            
            from django.contrib import messages
            messages.success(request, 'Комментарий успешно добавлен!')
            
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Ошибка при добавлении комментария: {str(e)}')
    
    from django.shortcuts import redirect
    return redirect('alert_detail', alert_id=alert_id)


def delete_comment(request, comment_id):
    """Удаление комментария"""
    if request.method == 'POST':
        try:
            comment = AlertComment.objects.get(id=comment_id)
            alert_id = comment.alert.id
            comment.delete()
            
            from django.contrib import messages
            messages.success(request, 'Комментарий успешно удален!')
            
            from django.shortcuts import redirect
            return redirect('alert_detail', alert_id=alert_id)
            
        except AlertComment.DoesNotExist:
            from django.contrib import messages
            messages.error(request, 'Комментарий не найден.')
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Ошибка при удалении комментария: {str(e)}')
    
    from django.shortcuts import redirect
    return redirect('noaa_detailed')


def test_all_alert_types_demo(request):
    """Демонстрация обработки всех типов алертов"""
    if request.method == 'POST':
        from django.contrib import messages
        
        # Тестовые данные для разных типов алертов
        test_alerts = [
            {
                'product_id': 'T001',
                'message_code': 'T001',
                'serial_number': '001',
                'issue_time': timezone.now(),
                'warning_type': 'Type II Radio Emission Alert',
                'description': 'Radio emission from solar event',
                'raw_message': 'Test T-type alert'
            },
            {
                'product_id': 'K002',
                'message_code': 'K002',
                'serial_number': '002',
                'issue_time': timezone.now(),
                'warning_type': 'Geomagnetic K-index Alert',
                'noaa_scale': 'G2',
                'raw_message': 'Test K-type alert'
            },
            {
                'product_id': 'W003',
                'message_code': 'W003',
                'serial_number': '003',
                'issue_time': timezone.now(),
                'warning_type': 'Watch Alert',
                'raw_message': 'Test W-type alert'
            },
            {
                'product_id': 'X004',
                'message_code': 'X004',
                'serial_number': '004',
                'issue_time': timezone.now(),
                'warning_type': 'Unknown Type Alert',
                'raw_message': 'Test unknown type alert'
            }
        ]
        
        created_count = 0
        for alert_data in test_alerts:
            try:
                saved_alert = save_alert_to_db(alert_data)
                if saved_alert:
                    created_count += 1
                    messages.success(request, f'✅ {alert_data["product_id"]}: {alert_data["warning_type"]} (ID: {saved_alert.id})')
            except Exception as e:
                messages.error(request, f'❌ Ошибка с {alert_data["product_id"]}: {str(e)}')
        
        messages.info(request, f'🎯 Создано {created_count} из {len(test_alerts)} тестовых алертов')
    
    from django.shortcuts import redirect
    return redirect('noaa_detailed')
