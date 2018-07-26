import logging

import boto3
import django_rq
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect

from forecast_app.models import Counter


logger = logging.getLogger(__name__)

UPLOAD_BUCKET_NAME = 'mc.zoltarapp.sandbox'


def index(request):
    count, last_update = Counter.get_count_and_last_update()
    queue = django_rq.get_queue()  # name='default'
    conn = django_rq.get_connection()  # name='default'
    return render(request,
                  'index.html',
                  context={'count': count,
                           'last_update': last_update,
                           'queue': queue,
                           'conn': conn})


def increment_counter(request, **kwargs):
    if kwargs['is_rq']:
        django_rq.enqueue(Counter.increment_count)  # name='default'
    else:
        Counter.increment_count()
    return redirect('index')


def clear_rq(request):
    queue = django_rq.get_queue()  # name='default'
    queue.empty()
    return redirect('index')


def upload_forecast(request):
    """
    Accepts a file uploaded to this app by the user and then saves it in an S3 bucket.

    The key used for the uploaded file is xx
    """
    if 'data_file' not in request.FILES:  # user submitted without specifying a file to upload
        return HttpResponse("No file selected to upload")

    data_file = request.FILES['data_file']  # InMemoryUploadedFile or TemporaryUploadedFile
    logger.debug("data_file={!r}".format(data_file))

    s3 = boto3.client('s3')
    # todo use chunks? for chunk in data_file.chunks(): print(chunk)
    s3.upload_fileobj(data_file, UPLOAD_BUCKET_NAME, 'mykey')  # todo use UploadFileTask pk as key. data_file.name

    messages.success(request, 'Uploaded the file to S3.')
    return redirect('index')
