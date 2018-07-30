from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^inc_web/$', views.increment_counter, {'is_rq': False}, name='increment-counter-web'),
    url(r'^inc_rq/$', views.increment_counter, {'is_rq': True}, name='increment-counter-rq'),
    url(r'^empty_rq/$', views.empty_rq, name='empty-rq'),

    url(r'^upload_file/$', views.upload_file, name='upload-file'),
    url(r'^delete_file_jobs/$', views.delete_file_jobs, name='delete-file-jobs'),

    url(r'^s3_buckets/$', views.list_s3_buckets, name='s3-bucket'),

]
