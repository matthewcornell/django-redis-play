from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^inc_web/$', views.increment_counter, {'is_rq': False}, name='increment-counter-web'),
    url(r'^inc_rq/$', views.increment_counter, {'is_rq': True}, name='increment-counter-rq'),
    url(r'^clear_rq/$', views.clear_rq, name='clear-rq'),
    url(r'^upload/$', views.upload_forecast, name='upload-forecast'),

]
