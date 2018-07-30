import logging
import tempfile
import time

import boto3
from django.db import models
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
    created_at = models.DateTimeField(help_text="When the file was uploaded.", auto_now_add=True)

    filename = models.CharField(max_length=200, help_text="Original name of the uploaded file.")

    PENDING = 0
    S3_FILE_UPLOADED = 1
    QUEUED = 2
    S3_FILE_DOWNLOADED = 3
    FORECAST_LOADED = 4

    FAILED_S3_FILE_UPLOAD = 6
    FAILED_ENQUEUE = 7
    FAILED_PROCESS_FILE = 8

    STATUS_CHOICES = (
        (PENDING, 'PENDING'),
        (S3_FILE_UPLOADED, 'S3_FILE_UPLOADED'),
        (QUEUED, 'QUEUED'),
        (S3_FILE_DOWNLOADED, 'S3_FILE_DOWNLOADED'),
        (FORECAST_LOADED, 'FORECAST_LOADED'),

        (FAILED_S3_FILE_UPLOAD, 'FAILED_S3_FILE_UPLOAD'),
        (FAILED_ENQUEUE, 'FAILED_ENQUEUE'),
        (FAILED_PROCESS_FILE, 'FAILED_PROCESS_FILE'),
    )
    status = models.IntegerField(default=PENDING, choices=STATUS_CHOICES)

    is_deleted = models.BooleanField(default=False)  # True if the S3 file was ever deleted by this app


    # model_pk = models.IntegerField()  # placeholder for: forecast_model = models.ForeignKey(ForecastModel, ...)

    # timezero_date = models.DateField(help_text="A date that a target is relative to.")

    # data_version_date = models.DateField(
    #     null=True, blank=True,
    #     help_text="The optional database date at which models should work with for the timezero_date.")  # nullable

    # user = models.ForeignKey(User, blank=True, null=True, help_text="The User who submitted the task",
    #                          on_delete=models.SET_NULL)

    # todo new_forecast_pk (FK, NULL), enqueued_at, etc.


    def __repr__(self):
        return str((self.pk, self.created_at, self.filename, self.status_as_str(), self.is_deleted))


    def __str__(self):  # todo
        return basic_str(self)


    def status_as_str(self):
        for status_int, status_name in self.STATUS_CHOICES:
            if self.status == status_int:
                return status_name

        return None


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
        Deletes the S3 object corresponding to me
        """
        try:
            logger.debug("delete_s3_object(): Started: {}".format(self))
            s3 = boto3.client('s3')
            s3.delete_object(Bucket=S3_UPLOAD_BUCKET_NAME, Key=self.s3_key())
            self.is_deleted = True
            self.save()
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
                s3 = boto3.client('s3')
                s3.download_fileobj(S3_UPLOAD_BUCKET_NAME, upload_file_job.s3_key(), temp_fp)
                upload_file_job.status = UploadFileJob.S3_FILE_DOWNLOADED
                upload_file_job.save()

                logger.debug("process_uploaded_file(): Loading forecast. upload_file_job={}".format(upload_file_job))
                time.sleep(10)  # simulates a long-running operation
                # new_forecast = load_forecast()  # todo
                # upload_file_job.new_forecast_pk = new_forecast.pk
                upload_file_job.status = UploadFileJob.FORECAST_LOADED  # yay!
                upload_file_job.save()

                logger.debug("process_uploaded_file(): Done. upload_file_job={}".format(upload_file_job))
            except Exception as exc:
                logger.debug("process_uploaded_file(): Error: {}. upload_file_job={}".format(exc, upload_file_job))
                upload_file_job.status = UploadFileJob.FAILED_PROCESS_FILE
                upload_file_job.save()
            finally:
                upload_file_job.delete_s3_object()  # NB: in current thread


# try to delete the corresponding S3 object
@receiver(pre_delete, sender=UploadFileJob)
def delete_s3_obj_for_upload_file_job(sender, instance, using, **kwargs):
    logger.debug("delete_s3_obj_for_upload_file_job(): Started. sender={}, instance={}, using={}, kwargs={}"
                 .format(sender, instance, using, kwargs))
    instance.delete_s3_object()
