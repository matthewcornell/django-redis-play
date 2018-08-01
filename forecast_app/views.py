import logging
import time
from io import SEEK_END

import boto3
import django_rq
from django.contrib import messages
from django.shortcuts import render, redirect

from forecast_app.models import Counter, UploadFileJob
from forecast_app.models.upload_file_job import S3_UPLOAD_BUCKET_NAME, upload_file_job_s3_file


logger = logging.getLogger(__name__)


def index(request):
    count, last_update = Counter.get_count_and_last_update()
    queue = django_rq.get_queue()  # name='default'
    conn = django_rq.get_connection()  # name='default'
    # todo xx maybe show if queue is busy?
    return render(request,
                  'index.html',
                  context={'count': count,
                           'updated_at': last_update,
                           'queue': queue,
                           'conn': conn,
                           'upload_file_jobs': UploadFileJob.objects.all().order_by('-updated_at'),
                           }
                  )


def list_s3_bucket_info(request):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(S3_UPLOAD_BUCKET_NAME)
    s3_objects = []
    for s3_object in bucket.objects.all():
        s3_objects.append(s3_object)
    return render(request, 's3.html', context={'s3_objects': s3_objects})


#
# S3-related functions
#

def empty_s3_bucket(request):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(S3_UPLOAD_BUCKET_NAME)
    for s3_object in bucket.objects.all():
        s3_object.delete()
    save_message_and_log_debug(request, "empty_s3_bucket(): All objects deleted.")
    return redirect('s3-bucket')


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


def upload_file(request):  # no-op implementation for testing
    return _upload_file(request, input_json_for_request__noop, process_upload_file_job__noop)


def _upload_file(request, input_json_for_request_fcn, process_upload_file_job_fcn):
    """
    Accepts a file uploaded to this app by the user, saves it in an S3 bucket, then enqueues process_upload_file_job_fcn
    to process the file by an RQ worker.
    :param input_json_for_request_fcn: a function of one arg (request) that returns a dict used to initialize the new
        UploadFileJob's input_json
    :param process_upload_file_job_fcn: a function of one arg (upload_file_job_pk) that is passed to
        django_rq.enqueue(). NB: It MUST use this wrapper in order to work have access to the file that was uploaded to
        S3:
            with upload_file_job_s3_file() as s3_file_fp: ...
        NB: If it needs to save upload_file_job.output_json, make sure to call save(), e.g.,
            upload_file_job.output_json = {'forecast_pk': new_forecast.pk}
            upload_file_job.save()
    """
    if 'data_file' not in request.FILES:  # user submitted without specifying a file to upload
        save_message_and_log_debug(request, "upload_file(): No file selected to upload.", is_failure=True)
        return redirect('index')

    data_file = request.FILES['data_file']  # UploadedFile (InMemoryUploadedFile or TemporaryUploadedFile)
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
        upload_file_job.input_json = input_json_for_request_fcn(request)
        upload_file_job.save()
        save_message_and_log_debug(request, "upload_forecast_file(): 1/3 Created the UploadFileJob: {}"
                                   .format(upload_file_job))
    except Exception as exc:
        save_message_and_log_debug(request, "upload_forecast_file(): Error creating the UploadFileJob: {}".format(exc),
                                   is_failure=True)
        return redirect('index')

    # upload the file to S3
    try:
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(S3_UPLOAD_BUCKET_NAME)
        # todo use chunks? for chunk in data_file.chunks(): print(chunk):
        bucket.put_object(Key=upload_file_job.s3_key(), Body=data_file)
        upload_file_job.status = UploadFileJob.S3_FILE_UPLOADED
        upload_file_job.save()
        save_message_and_log_debug(request, "upload_file(): 2/3 Uploaded the file to S3: {}, {}. upload_file_job={}"
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
        rq_job = django_rq.enqueue(process_upload_file_job_fcn, upload_file_job.pk,
                                   job_id=upload_file_job.rq_job_id())  # name="default"
        upload_file_job.status = UploadFileJob.QUEUED
        upload_file_job.save()
        save_message_and_log_debug(request, "upload_file(): 3/3 Enqueued the job: {}. upload_file_job={}"
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


#
# no-op RQ enqueue() helper functions for testing
#

def input_json_for_request__noop(request):
    logger.debug("input_json_for_request__noop(): request={}".format(request))
    return None  # no input_json


def process_upload_file_job__noop(upload_file_job_pk):
    logger.debug("process_upload_file_job__noop(): Loading forecast. upload_file_job_pk={}".format(upload_file_job_pk))
    with upload_file_job_s3_file(upload_file_job_pk) as (upload_file_job, s3_file_fp):
        # show that we can access the file's data
        file_size = s3_file_fp.seek(0, SEEK_END)
        s3_file_fp.seek(0)
        lines = s3_file_fp.readlines()
        logger.debug("process_upload_file_job__noop(): upload_file_job={}.\n\t-> from s3_file_fp: {}, {}, {}"
                     .format(upload_file_job, file_size, len(lines), repr(lines[0])))

        # simulate a long-running operation
        time.sleep(5)


#
# app-specific RQ enqueue() helper functions: ForecastModel.load_forecast()
#

# def input_json_for_request__forecast(request):
#     # >> todo extract and save app-specific inputs, e.g.,
#     return {'model_pk': request['model_pk'],
#             'timezero_date': request['timezero_date'],
#             'data_version_date': request['data_version_date']}


# def process_upload_file_job__forecast(upload_file_job_pk):
#     upload_file_job = get_object_or_404(UploadFileJob, pk=upload_file_job_pk)
#     with upload_file_job_s3_file(upload_file_job_pk) as s3_file_fp:
#         forecast_model_pk = upload_file_job.input_json['model_pk']  # todo 'timezero_date', 'data_version_date', etc.
#         forecast_model = get_object_or_404(ForecastModel, pk=forecast_model_pk)
#         # todo csv_file_path, time_zero, file_name=None, validation_template=None, forecast_bin_map=None:
#         new_forecast = forecast_model.load_forecast(s3_file_fp, ...)
#         upload_file_job.output_json = {'forecast_pk': new_forecast.pk}
#         upload_file_job.save()
