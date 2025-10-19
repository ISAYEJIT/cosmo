from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
import asyncio
import requests
from utils.proxy_utils import proxy_manager, make_request_with_proxy
from utils.translation import translate_space_weather_text
from ..models import SpaceWeatherAlert, TypeTRadioAlert, TypeKGeomagneticAlert, TypeEElectronAlert, TypeAForecastAlert
from ..views.noaa_views import parse_alert_message, save_alert_to_db


def check_admin_password(user):
    """Проверка доступа к админ-панели"""
    return True  # Временно разрешаем всем для простоты


@user_passes_test(check_admin_password)
def admin_alerts_view(request):
    """Админская страница для управления алертами"""
    
    # Проверка пароля для доступа к админ-панели
    if request.method == 'POST' and request.POST.get('action') == 'check_password':
        entered_password = request.POST.get('admin_password', '')
        if entered_password == '12345':
            request.session['admin_authenticated'] = True
            return redirect('admin_alerts')
        else:
            from django.contrib import messages
            messages.error(request, '❌ Неверный пароль! Доступ запрещен.')
            return redirect('admin_alerts')
    
    # Если не аутентифицирован, показываем форму ввода пароля
    if not request.session.get('admin_authenticated', False):
        return render(request, 'admin_password.html', {
            'page_title': 'Доступ к админ-панели'
        })
    
    # Подсчет алертов во всех таблицах
    total_alerts = (
        SpaceWeatherAlert.objects.count() +
        TypeTRadioAlert.objects.count() +
        TypeKGeomagneticAlert.objects.count() +
        TypeEElectronAlert.objects.count() +
        TypeAForecastAlert.objects.count()
    )
    
    # Активные алерты (с учетом valid_to где применимо)
    now = timezone.now()
    active_alerts = (
        SpaceWeatherAlert.objects.filter(valid_to__gte=now).count() +
        TypeKGeomagneticAlert.objects.filter(valid_to__gte=now).count()
    )
    
    # Недавние алерты (за последнюю неделю)
    week_ago = now - timezone.timedelta(days=7)
    recent_alerts = (
        SpaceWeatherAlert.objects.filter(created_at__gte=week_ago).count() +
        TypeTRadioAlert.objects.filter(created_at__gte=week_ago).count() +
        TypeKGeomagneticAlert.objects.filter(created_at__gte=week_ago).count() +
        TypeEElectronAlert.objects.filter(created_at__gte=week_ago).count() +
        TypeAForecastAlert.objects.filter(created_at__gte=week_ago).count()
    )
    
    stats = {
        'total_alerts': total_alerts,
        'active_alerts': active_alerts,
        'recent_alerts': recent_alerts,
    }
    
    # Получение объединенного списка алертов для пагинации
    from itertools import chain
    from operator import attrgetter
    
    t_alerts = list(TypeTRadioAlert.objects.all())
    k_alerts = list(TypeKGeomagneticAlert.objects.all()) 
    e_alerts = list(TypeEElectronAlert.objects.all())
    a_alerts = list(TypeAForecastAlert.objects.all())
    old_alerts = list(SpaceWeatherAlert.objects.all())
    
    # Объединяем и сортируем по времени
    all_alerts = list(chain(t_alerts, k_alerts, e_alerts, a_alerts, old_alerts))
    all_alerts.sort(key=attrgetter('issue_time'), reverse=True)
    
    # Пагинация объединенного списка
    alerts_list = all_alerts
    paginator = Paginator(alerts_list, 20)  # 20 алертов на страницу
    page_number = request.GET.get('page')
    alerts = paginator.get_page(page_number)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'logout_admin':
            request.session['admin_authenticated'] = False
            from django.contrib import messages
            messages.success(request, '✅ Вы успешно вышли из админ-панели.')
            return redirect('admin_alerts')
        
        elif action == 'load_alerts':
            return load_alerts_from_api(request)
        elif action == 'clear_alerts':
            # Проверяем пароль для очистки базы данных
            clear_password = request.POST.get('clear_password', '')
            if clear_password != 'CLEAR_DB_2024':
                from django.contrib import messages
                messages.error(request, '❌ Неверный пароль для очистки базы данных!')
                return redirect('admin_alerts')
            
            # Подсчитываем и удаляем из всех таблиц
            deleted_count = (
                SpaceWeatherAlert.objects.count() +
                TypeTRadioAlert.objects.count() +
                TypeKGeomagneticAlert.objects.count() +
                TypeEElectronAlert.objects.count() +
                TypeAForecastAlert.objects.count()
            )
            
            SpaceWeatherAlert.objects.all().delete()
            TypeTRadioAlert.objects.all().delete()
            TypeKGeomagneticAlert.objects.all().delete()
            TypeEElectronAlert.objects.all().delete()
            TypeAForecastAlert.objects.all().delete()
            
            messages.success(request, f'🗑️ Удалено {deleted_count} алертов из всех таблиц базы данных.')
            return redirect('admin_alerts')
        elif action == 'delete_alert':
            alert_id = request.POST.get('alert_id')
            try:
                alert = SpaceWeatherAlert.objects.get(id=alert_id)
                alert.delete()
                messages.success(request, 'Алерт успешно удален.')
            except SpaceWeatherAlert.DoesNotExist:
                messages.error(request, 'Алерт не найден.')
            return redirect('admin_alerts')
    
    context = {
        'alerts': alerts,
        'stats': stats,
        'page_title': 'Админ-панель: Управление алертами'
    }
    
    return render(request, 'admin_alerts.html', context)


def load_alerts_from_api(request):
    """Загружает алерты из NOAA API"""
    try:
        # Загружаем данные из API
        response = requests.get('https://services.swpc.noaa.gov/products/alerts.json', timeout=10)
        response.raise_for_status()
        alerts_data = response.json()
        
        loaded_count = 0
        skipped_count = 0
        errors = []
        
        for alert_data in alerts_data:
            try:
                message = alert_data.get('message', '')
                if message:
                    parsed_data = parse_alert_message(alert_data)  # Передаем весь объект, а не только message
                    if parsed_data:
                        # Добавляем данные из API (issue_datetime)
                        if 'issue_datetime' in alert_data:
                            try:
                                # Парсим timestamp из API
                                issue_dt = datetime.strptime(alert_data['issue_datetime'], '%Y-%m-%d %H:%M:%S.%f')
                                parsed_data['issue_time_from_api'] = timezone.make_aware(issue_dt, timezone.utc)
                            except:
                                pass
                        
                        # Проверяем, существует ли уже такой алерт во всех таблицах
                        message_code = parsed_data.get('message_code', '')
                        serial_number = parsed_data.get('serial_number', '')
                        
                        existing_alert = (
                            SpaceWeatherAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                            TypeTRadioAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                            TypeKGeomagneticAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                            TypeEElectronAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                            TypeAForecastAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists()
                        )
                        
                        if existing_alert:
                            skipped_count += 1
                            continue
                        
                        # Перевод будет выполнен автоматически в save_alert_to_db
                        
                        # Сохраняем в базу (только новые)
                        saved_alert = save_alert_to_db(parsed_data)
                        if saved_alert:
                            loaded_count += 1
                    else:
                        # Если парсинг не удался, сохраняем как есть с минимальными данными
                        try:
                            # Используем базовую информацию из API
                            product_id = alert_data.get('product_id', 'UNKNOWN')
                            issue_datetime = alert_data.get('issue_datetime', '')
                            
                            # Парсим время
                            issue_time = timezone.now()
                            if issue_datetime:
                                try:
                                    issue_time = datetime.strptime(issue_datetime, '%Y-%m-%d %H:%M:%S.%f')
                                    issue_time = timezone.make_aware(issue_time, timezone.utc)
                                except:
                                    pass
                            
                            # Создаем уникальный код на основе product_id и времени
                            message_code = product_id
                            serial_number = str(int(issue_time.timestamp()))
                            
                            # Проверяем дубликат во всех таблицах
                            existing = (
                                SpaceWeatherAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                                TypeTRadioAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                                TypeKGeomagneticAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                                TypeEElectronAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists() or
                                TypeAForecastAlert.objects.filter(message_code=message_code, serial_number=serial_number).exists()
                            )
                            
                            if existing:
                                skipped_count += 1
                                continue
                            
                            # Переводим сообщение для warning_type
                            translated_message = translate_space_weather_text(message[:200] + '...' if len(message) > 200 else message)
                            
                            # Создаем алерт
                            alert = SpaceWeatherAlert.objects.create(
                                message_code=message_code,
                                serial_number=serial_number,
                                issue_time=issue_time,
                                warning_type=translated_message,
                                full_message=message,
                                warning_condition='API Import',
                                noaa_scale='Неизвестно',
                                potential_impacts='Требует ручного анализа',
                            )
                            
                            if alert:
                                loaded_count += 1
                                
                        except Exception as e2:
                            errors.append(f"Ошибка создания базового алерта: {str(e2)}")
                else:
                    errors.append("Пустое сообщение в алерте")
                    
            except Exception as e:
                errors.append(f"Ошибка обработки алерта: {str(e)}")
        
        # Формируем сообщения
        total_processed = len(alerts_data)
        
        if loaded_count > 0:
            messages.success(request, f'✅ Успешно загружено {loaded_count} новых алертов из NOAA API.')
        
        if skipped_count > 0:
            messages.info(request, f'ℹ️ Пропущено {skipped_count} алертов (уже существуют в базе).')
            
        if loaded_count == 0 and skipped_count == 0 and total_processed > 0:
            messages.warning(request, f'⚠️ Обработано {total_processed} алертов из API, но новых не найдено.')
        elif total_processed == 0:
            messages.warning(request, '⚠️ API не вернул никаких алертов.')
            
        if errors:
            error_msg = f'❌ Возникло {len(errors)} ошибок при обработке:\n' + '\n'.join(errors[:5])
            if len(errors) > 5:
                error_msg += f'\n... и еще {len(errors) - 5} ошибок'
            messages.error(request, error_msg)
            
        # Отладочная информация
        if total_processed > 0:
            messages.info(request, f'📊 Статистика: обработано {total_processed}, загружено {loaded_count}, пропущено {skipped_count}, ошибок {len(errors)}')
            
    except requests.RequestException as e:
        messages.error(request, f'🌐 Ошибка подключения к NOAA API: {str(e)}')
    except Exception as e:
        messages.error(request, f'💥 Неожиданная ошибка: {str(e)}')
    
    return redirect('admin_alerts')


def settings_view(request):
    """Страница настроек приложения"""
    if request.method == 'POST':
        # Обработка формы настроек
        proxy_enabled = request.POST.get('proxy_enabled') == 'on'
        
        # Сохранение настройки прокси
        proxy_manager.toggle_proxy(proxy_enabled)
        
        if proxy_enabled:
            messages.success(request, 'Прокси включен успешно!')
        else:
            messages.info(request, 'Прокси отключен.')
        
        return redirect('settings')
    
    # Получение текущих настроек
    proxy_enabled = proxy_manager.get_proxy_status()
    proxy_list = proxy_manager.load_proxy_list()
    proxy_count = len(proxy_list)
    
    # Получение последних алертов из всех таблиц
    from itertools import chain
    from operator import attrgetter
    
    t_alerts = list(TypeTRadioAlert.objects.all()[:5])
    k_alerts = list(TypeKGeomagneticAlert.objects.all()[:5]) 
    e_alerts = list(TypeEElectronAlert.objects.all()[:5])
    a_alerts = list(TypeAForecastAlert.objects.all()[:5])
    old_alerts = list(SpaceWeatherAlert.objects.all()[:5])
    
    # Объединяем и сортируем по времени
    all_alerts = list(chain(t_alerts, k_alerts, e_alerts, a_alerts, old_alerts))
    all_alerts.sort(key=attrgetter('issue_time'), reverse=True)
    recent_alerts = all_alerts[:10]
    
    context = {
        'title': 'Настройки',
        'proxy_enabled': proxy_enabled,
        'proxy_list': proxy_list,
        'proxy_count': proxy_count,
        'recent_alerts': recent_alerts,
    }
    
    return render(request, 'settings.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def test_connection(request):
    """Тестирование соединения через прокси"""
    test_url = "https://httpbin.org/ip"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        status, data = loop.run_until_complete(
            make_request_with_proxy(test_url, use_proxy=True)
        )
    finally:
        loop.close()

    if status == 200 and isinstance(data, dict) and 'origin' in data:
        return JsonResponse({
            'success': True,
            'message': f'Соединение успешно! IP: {data["origin"]}',
            'ip': data['origin']
        })

    return JsonResponse({
        'success': False,
        'error': f'Ошибка API: {status}',
        'details': str(data)
    })


def proxy_status_api(request):
    """API для получения статуса прокси"""
    proxy_enabled = proxy_manager.get_proxy_status()
    proxy_list = proxy_manager.load_proxy_list()
    
    return JsonResponse({
        'proxy_enabled': proxy_enabled,
        'proxy_count': len(proxy_list),
        'proxy_available': len(proxy_list) > 0
    })
