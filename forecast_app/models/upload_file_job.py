import logging
import tempfile
import time
from io import SEEK_END

import boto3
from django.db import models
from django.db.models import BooleanField
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.shortcuts import get_object_or_404

from forecast_app.models.counter import basic_str


logger = logging.getLogger(__name__)

S3_UPLOAD_BUCKET_NAME = 'mc.zoltarapp.sandbox'


class UploadFileJob(models.Model):
    """
    Holds information about user file uploads. Accessed by worker jobs when processing those files.
    """
    #
    # general task-related fields
    #

    PENDING = 0
    S3_FILE_UPLOADED = 1
    QUEUED = 2
    S3_FILE_DOWNLOADED = 3
    SUCCESS = 4

    STATUS_CHOICES = (
        (PENDING, 'PENDING'),
        (S3_FILE_UPLOADED, 'S3_FILE_UPLOADED'),
        (QUEUED, 'QUEUED'),
        (S3_FILE_DOWNLOADED, 'S3_FILE_DOWNLOADED'),
        (SUCCESS, 'SUCCESS'),
    )
    status = models.IntegerField(default=PENDING, choices=STATUS_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)  # when this instance was created. basically the submit date

    updated_at = models.DateTimeField(auto_now=True)  # time of last save(). basically last time status changed

    is_failed = BooleanField(default=False)

    failure_message = models.CharField(max_length=2000)  # non-empty if is_failed

    filename = models.CharField(max_length=200)  # original name of the uploaded file


    #
    # user-related fields
    #

    # user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)  # user who submitted


    #
    # app-specific fields
    #

    # model_pk = models.IntegerField()  # placeholder for: forecast_model = models.ForeignKey(ForecastModel, ...)

    # timezero_date = models.DateField(help_text="A date that a target is relative to.")

    # data_version_date = models.DateField(
    #     null=True, blank=True,
    #     help_text="The optional database date at which models should work with for the timezero_date.")  # nullable

    # new_forecast_pk (FK, NULL)  # aka the result


    # >> todo xx abstract this class
    # class Meta:
    #     abstract = True


    def __repr__(self):
        return str((self.pk, self.created_at, self.updated_at, self.filename, self.status_as_str(),
                    self.is_failed, self.failure_message))


    def __str__(self):  # todo
        return basic_str(self)


    def status_as_str(self):
        for status_int, status_name in self.STATUS_CHOICES:
            if self.status == status_int:
                return status_name

        return None


    def elapsed_time(self):
        return self.updated_at - self.created_at


    #
    # service-specific keys/ids
    #
    # todo should UploadFileJob know about RQ and S3? maybe some kind of adapter to separate concerns
    #

    def s3_key(self):
        """
        :return: the S3 key in S3_UPLOAD_BUCKET_NAME corresponding to me
        """
        return str(self.pk)


    def rq_job_id(self):
        """
        :return: the RQ job id corresponding to me
        """
        return str(self.pk)


    def delete_s3_object(self):
        """
        Deletes the S3 object corresponding to me. note that we do not log delete failures in the instance. This is b/c
        failing to delete a temporary file is not a failure to process an uploaded file. Though it's not clear when
        delete would fail but everything preceding it would succeed...

        Apps can infer this condition by looking for non-deleted S3 objects whose status != SUCCESS .
        """
        try:
            logger.debug("delete_s3_object(): Started: {}".format(self))
            s3 = boto3.resource('s3')
            s3.Object(S3_UPLOAD_BUCKET_NAME, self.s3_key()).delete()
            logger.debug("delete_s3_object(): Done: {}".format(self))
        except Exception as exc:
            logger.debug("delete_s3_object(): Failed: {}, {}".format(exc, self))


    @classmethod
    def process_uploaded_file(cls, upload_file_job_pk):
        """
        enqueue() helper function. processes the passed UploadFileJob's pk: downloads the corresponding S3 file, loads
        it into the database via load_forecast(), deletes the S3 file, and sets the job's status.
        """
        upload_file_job = get_object_or_404(UploadFileJob, pk=upload_file_job_pk)
        logger.debug("process_uploaded_file(): Started. upload_file_job={}".format(upload_file_job))
        with tempfile.TemporaryFile() as temp_fp:
            try:
                logger.debug("process_uploaded_file(): Downloading from S3: {}, {}. upload_file_job={}"
                             .format(S3_UPLOAD_BUCKET_NAME, upload_file_job.s3_key(), upload_file_job))
                s3 = boto3.client('s3')  # using client here instead of higher-level resource b/c want to save to a fp
                s3.download_fileobj(S3_UPLOAD_BUCKET_NAME, upload_file_job.s3_key(), temp_fp)
                upload_file_job.status = UploadFileJob.S3_FILE_DOWNLOADED
                upload_file_job.save()

                # >> todo xx abstract this, e.g., upload_file_job.process_s3_file()
                logger.debug("process_uploaded_file(): Loading forecast. upload_file_job={}".format(upload_file_job))
                time.sleep(5)  # simulates a long-running operation
                # file_size = temp_fp.seek(0, SEEK_END)
                # temp_fp.seek(0)
                # lines = temp_fp.readlines()
                # new_forecast = load_forecast()  # todo the actual work :-)
                # upload_file_job.new_forecast_pk = new_forecast.pk
                # upload_file_job.save()

                upload_file_job.status = UploadFileJob.SUCCESS  # yay!
                upload_file_job.save()
                logger.debug("process_uploaded_file(): Done. upload_file_job={}".format(upload_file_job))
            except Exception as exc:
                failure_message = "process_uploaded_file(): FAILED_PROCESS_FILE: Error: {}. upload_file_job={}" \
                    .format(exc, upload_file_job)
                upload_file_job.is_failed = True
                upload_file_job.failure_message = failure_message
                upload_file_job.save()
                logger.debug(failure_message)
            finally:
                upload_file_job.delete_s3_object()  # NB: in current thread


@receiver(pre_delete, sender=UploadFileJob)
def delete_s3_obj_for_upload_file_job(sender, instance, using, **kwargs):
    instance.delete_s3_object()  # try to delete the corresponding S3 object
