import logging

import boto3
import django_rq
from django.contrib import messages
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.shortcuts import render, redirect

from forecast_app.models import Counter, UploadFileJob


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
                           'conn': conn,
                           'upload_file_jobs': UploadFileJob.objects.all()}
                  )


#
# counter-related functions
#

def increment_counter(request, **kwargs):
    if kwargs['is_rq']:
        django_rq.enqueue(Counter.increment_count)  # name="default"
        messages.success(request, "Incremented the count - enqueued.")
    else:
        Counter.increment_count()
        messages.success(request, "Incremented the count - immediate.")
    return redirect('index')


#
# RQ-related functions
#

def empty_rq(request):
    queue = django_rq.get_queue()  # name='default'
    queue.empty()
    messages.success(request, "Emptied the queue.")
    return redirect('index')


#
# file upload-related functions
#

def delete_file_jobs(request):
    UploadFileJob.objects.all().delete()
    messages.success(request, "Deleted all UploadFileJobs.")
    return redirect('index')


def upload_file(request):
    """
    Accepts a file uploaded to this app by the user and then saves it in an S3 bucket.
    The S3 object key used for the uploaded file is a UploadFileJob's pk that is created to represent this job.
    The RQ Job.id used is also the UploadFileJob's pk.

    todo use chunks? for chunk in data_file.chunks(): print(chunk)
    """
    if 'data_file' not in request.FILES:  # user submitted without specifying a file to upload
        messages.error(request, "No file selected to upload.")
        return redirect('index')

    data_file = request.FILES['data_file']  # InMemoryUploadedFile or TemporaryUploadedFile
    logger.debug("data_file={!r}".format(data_file))

    # upload the file to S3
    upload_file_job = UploadFileJob.objects.create(filename=data_file.name)  # todo status=PENDING
    try:
        s3 = boto3.client('s3')
        s3.upload_fileobj(data_file, UPLOAD_BUCKET_NAME, upload_file_job.s3_key())
        # upload_file_job.status = UPLOADED
        messages.success(request, "Uploaded the file to S3. upload_file_job={}".format(upload_file_job))
    except Exception as exc:
        messages.error(request, "Error uploading file to storage: {}".format(exc))
        return redirect('index')

    # upload worked, so enqueue a worker
    try:
        rq_job = django_rq.enqueue(UploadFileJob.process_uploaded_file, upload_file_job.pk,
                                   job_id=upload_file_job.s3_key())  # name="default"
        # upload_file_job.status = ENQUEUED
        messages.success(request, "Enqueued the job: {}".format(rq_job))
    except Exception as exc:
        messages.error(request, "Error enqueuing job: {}".format(exc))
        return redirect('index')

    # done
    return redirect('index')


#
# todo xx try to separate concerns: should UploadFileJob know about RQ and S3?
#

def s3_key(self):
    return str(self.pk)


# try to delete the corresponding S3 object
@receiver(pre_delete, sender=UploadFileJob)
def delete_s3_obj_for_upload_file_job(sender, instance, using, **kwargs):
    logger.debug("delete_s3_obj_for_upload_file_job(): started. upload_file_job={}".format(instance))
