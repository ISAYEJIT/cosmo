from django.urls import path
from .views import main_views
from .views.noaa_views import noaa_detailed, alert_detail, add_comment, delete_comment
from .views.settings_views import settings_view, test_connection, proxy_status_api, admin_alerts_view

urlpatterns = [
    path('', main_views.home, name='home'),
    path('noaa-detailed/', noaa_detailed, name='noaa_detailed'),
    path('alert/<int:alert_id>/', alert_detail, name='alert_detail'),
    path('alert/<int:alert_id>/comment/', add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', delete_comment, name='delete_comment'),
    path('settings/', settings_view, name='settings'),
    path('test-connection/', test_connection, name='test_connection'),
    path('api/proxy-status/', proxy_status_api, name='proxy_status_api'),
    path('alerts-admin/', admin_alerts_view, name='admin_alerts'),
]
