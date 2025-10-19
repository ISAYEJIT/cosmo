import os
import random
import aiohttp
try:
    from aiohttp_socks import ProxyConnector, ProxyType
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False
    ProxyConnector = None
    ProxyType = None


class ProxyManager:
    def __init__(self):
        self.proxy_file = 'proxy_list.txt'
        self.settings_file = 'proxy_settings.txt'
        self.proxy_enabled = self._load_proxy_status()
        
    def _load_proxy_status(self):
        """Загрузить статус прокси из файла"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    status = f.read().strip()
                    return status.lower() == 'true'
        except Exception:
            pass
        return False
    
    def _save_proxy_status(self):
        """Сохранить статус прокси в файл"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                f.write('true' if self.proxy_enabled else 'false')
        except Exception:
            pass
        
    def toggle_proxy(self, enabled=None):
        """Включить/выключить использование прокси"""
        if enabled is not None:
            self.proxy_enabled = enabled
        else:
            self.proxy_enabled = not self.proxy_enabled
        
        # Сохраняем состояние в файл
        self._save_proxy_status()
        return self.proxy_enabled
    
    def get_proxy_status(self):
        """Получить текущий статус прокси"""
        return self.proxy_enabled
    
    def load_proxy_list(self):
        """Загрузить список прокси из файла"""
        if not os.path.exists(self.proxy_file):
            return []
        
        proxy_list = []
        try:
            with open(self.proxy_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(':')
                        if len(parts) >= 2:
                            proxy_info = {
                                'host': parts[0],
                                'port': int(parts[1]),
                                'username': parts[2] if len(parts) > 2 else None,
                                'password': parts[3] if len(parts) > 3 else None
                            }
                            proxy_list.append(proxy_info)
        except Exception:
            pass
        
        return proxy_list
    
    def get_random_proxy(self):
        """Получить случайный прокси из списка"""
        proxy_list = self.load_proxy_list()
        if not proxy_list:
            return None
        return random.choice(proxy_list)
    
    def create_proxy_connector(self, proxy_info=None):
        """Создать коннектор с прокси"""
        if not SOCKS_AVAILABLE:
            return aiohttp.TCPConnector(verify_ssl=False)
        
        if not proxy_info:
            proxy_info = self.get_random_proxy()
        
        if not proxy_info:
            return aiohttp.TCPConnector(verify_ssl=False)
        
        try:
            # Используем только SOCKS4
            if proxy_info['username'] and proxy_info['password']:
                return ProxyConnector(
                    proxy_type=ProxyType.SOCKS4,
                    host=proxy_info['host'],
                    port=proxy_info['port'],
                    username=proxy_info['username'],
                    password=proxy_info['password']
                )
            else:
                return ProxyConnector(
                    proxy_type=ProxyType.SOCKS4,
                    host=proxy_info['host'],
                    port=proxy_info['port']
                )
        except Exception:
            return aiohttp.TCPConnector(verify_ssl=False)


# Глобальный экземпляр менеджера прокси
proxy_manager = ProxyManager()


async def make_request_with_proxy(url, use_proxy=None):
    """
    Универсальная функция для HTTP запросов с поддержкой прокси
    """
    timeout = aiohttp.ClientTimeout(total=15)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    async def try_request(session, url):
        """Попытка выполнить запрос с обработкой разных типов ответов"""
        async with session.get(url, headers=headers) as response:
            content_type = response.headers.get('content-type', '').lower()
            
            if response.status == 403:
                return response.status, {"error": "Access denied (403)", "message": "API заблокирован или требует авторизацию"}
            
            if response.status != 200:
                text = await response.text()
                return response.status, {"error": f"HTTP {response.status}", "message": text[:200]}
            
            # Проверяем тип контента
            if 'application/json' in content_type:
                try:
                    data = await response.json()
                    return response.status, data
                except Exception:
                    text = await response.text()
                    return response.status, {"error": "JSON parse error", "message": text[:200]}
            else:
                # Если не JSON, возвращаем как текст
                text = await response.text()
                return response.status, {"error": "Non-JSON response", "content_type": content_type, "message": text[:200]}
    
    # Определяем, использовать ли прокси
    should_use_proxy = use_proxy if use_proxy is not None else proxy_manager.get_proxy_status()
    
    # Сначала пробуем прямое подключение, если прокси отключен
    if not should_use_proxy:
        try:
            connector = aiohttp.TCPConnector(verify_ssl=False)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                return await try_request(session, url)
        except Exception as direct_error:
            return 500, {"error": "Connection failed", "message": str(direct_error)}
    
    # Пробуем через прокси
    try:
        connector = proxy_manager.create_proxy_connector()
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            return await try_request(session, url)
    except Exception as proxy_error:
        
        # Fallback на прямое подключение
        try:
            connector = aiohttp.TCPConnector(verify_ssl=False)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                return await try_request(session, url)
        except Exception:
            return 500, {"error": "Connection failed", "message": str(proxy_error)}
