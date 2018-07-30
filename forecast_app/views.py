import logging

import boto3
import django_rq
from django.contrib import messages
from django.shortcuts import render, redirect

from forecast_app.models import Counter, UploadFileJob
from forecast_app.models.upload_file_job import S3_UPLOAD_BUCKET_NAME


logger = logging.getLogger(__name__)


def index(request):
    count, last_update = Counter.get_count_and_last_update()
    queue = django_rq.get_queue()  # name='default'
    conn = django_rq.get_connection()  # name='default'
    return render(request,
                  'index.html',
                  context={'count': count,
                           'updated_at': last_update,
                           'queue': queue,
                           'conn': conn,
                           'upload_file_jobs': UploadFileJob.objects.all(),
                           }
                  )


def list_s3_bucket_info(request):
    s3_objects = []
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(S3_UPLOAD_BUCKET_NAME)
    for s3_object in bucket.objects.all():
        s3_objects.append(s3_object)
    return render(request, 's3.html', context={'s3_objects': s3_objects})


#
# utilities
#

def save_message_and_log_debug(request, message, is_failure=False):
    if not is_failure:
        logger.debug(message)
        messages.success(request, message)
    else:
        logger.error(message)
        messages.error(request, message)


#
# counter-related functions
#

def increment_counter(request, **kwargs):
    if kwargs['is_rq']:
        django_rq.enqueue(Counter.increment_count)  # name="default"
        save_message_and_log_debug(request, "increment_counter(): Incremented the count - enqueued.")
    else:
        Counter.increment_count()
        save_message_and_log_debug(request, "increment_counter(): Incremented the count - immediate.")
    return redirect('index')


#
# RQ-related functions
#

def empty_rq(request):
    queue = django_rq.get_queue()  # name='default'
    queue.empty()
    save_message_and_log_debug(request, "empty_rq(): Emptied the queue.")
    return redirect('index')


#
# file upload-related functions
#

MAX_UPLOAD_FILE_SIZE = 5E+06


def delete_file_jobs(request):
    save_message_and_log_debug(request, "delete_file_jobs(): Deleting all UploadFileJobs")
    UploadFileJob.objects.all().delete()  # pre_delete() signal deletes corresponding S3 object (the uploaded file)
    save_message_and_log_debug(request, "delete_file_jobs(): Done")
    return redirect('index')


def upload_file(request):
    """
    Accepts a file uploaded to this app by the user and then saves it in an S3 bucket.
    The S3 object key used for the uploaded file is a UploadFileJob's pk that is created to represent this job.
    The RQ Job.id used is also the UploadFileJob's pk.

    todo use chunks? for chunk in data_file.chunks(): print(chunk)
    """
    if 'data_file' not in request.FILES:  # user submitted without specifying a file to upload
        save_message_and_log_debug(request, "upload_file(): No file selected to upload.", is_failure=True)
        return redirect('index')

    data_file = request.FILES['data_file']  # InMemoryUploadedFile or TemporaryUploadedFile
    logger.debug("upload_file(): Got data_file: name={!r}, size={}, content_type={}"
                 .format(data_file.name, data_file.size, data_file.content_type))
    if data_file.size > MAX_UPLOAD_FILE_SIZE:
        save_message_and_log_debug(request, "upload_file(): File was too large. size={}, max={}."
                                   .format(data_file.size, MAX_UPLOAD_FILE_SIZE),
                                   is_failure=True)
        return redirect('index')

    # create the UploadFileJob
    try:
        upload_file_job = UploadFileJob.objects.create(filename=data_file.name)  # status = PENDING
        save_message_and_log_debug(request, "upload_file(): Created the UploadFileJob: {}".format(upload_file_job))
    except Exception as exc:
        save_message_and_log_debug(request, "upload_file(): Error creating the UploadFileJob: {}".format(exc),
                                   is_failure=True)
        return redirect('index')

    # upload the file to S3
    try:
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(S3_UPLOAD_BUCKET_NAME)
        bucket.put_object(Key=upload_file_job.s3_key(), Body=data_file)

        upload_file_job.status = UploadFileJob.S3_FILE_UPLOADED
        upload_file_job.save()
        save_message_and_log_debug(request, "upload_file(): Uploaded the file to S3: {}, {}. upload_file_job={}"
                                   .format(S3_UPLOAD_BUCKET_NAME, upload_file_job.s3_key(), upload_file_job))
    except Exception as exc:
        failure_message = "upload_file(): FAILED_S3_FILE_UPLOAD: Error uploading file to S3: {}. upload_file_job={}" \
            .format(exc, upload_file_job)
        upload_file_job.is_failed = True
        upload_file_job.failure_message = failure_message
        upload_file_job.save()
        save_message_and_log_debug(request, failure_message, is_failure=True)
        return redirect('index')

    # enqueue a worker
    try:
        rq_job = django_rq.enqueue(UploadFileJob.process_uploaded_file, upload_file_job.pk,
                                   job_id=upload_file_job.rq_job_id())  # name="default"
        upload_file_job.status = UploadFileJob.QUEUED
        upload_file_job.save()
        save_message_and_log_debug(request, "upload_file(): Enqueued the job: {}. upload_file_job={}"
                                   .format(rq_job, upload_file_job))
    except Exception as exc:
        failure_message = "upload_file(): FAILED_ENQUEUE: Error enqueuing the job: {}. upload_file_job={}" \
            .format(exc, upload_file_job)
        upload_file_job.is_failed = True
        upload_file_job.failure_message = failure_message
        upload_file_job.save()
        upload_file_job.delete_s3_object()  # NB: in current thread
        save_message_and_log_debug(request, failure_message, is_failure=True)
        return redirect('index')

    logger.debug("upload_file(): Done")
    return redirect('index')
