import logging

from django.db import models
from django.shortcuts import get_object_or_404

from forecast_app.models.counter import basic_str


logger = logging.getLogger(__name__)


class UploadFileJob(models.Model):
    """
    Holds information about user file uploads. Accessed by worker jobs when processing those files.
    """
    created_at = models.DateTimeField(help_text="When the file was uploaded.", auto_now_add=True)

    filename = models.CharField(max_length=200, help_text="Original name of the uploaded file.")


    # model_pk = models.IntegerField()  # placeholder for: forecast_model = models.ForeignKey(ForecastModel, ...)

    # timezero_date = models.DateField(help_text="A date that a target is relative to.")

    # data_version_date = models.DateField(
    #     null=True, blank=True,
    #     help_text="The optional database date at which models should work with for the timezero_date.")  # nullable

    # user = models.ForeignKey(User, blank=True, null=True, help_text="The User who submitted the task",
    #                          on_delete=models.SET_NULL)

    # todo enqueued_at, state, result, etc.

    def __repr__(self):
        return str((self.pk, self.created_at, self.filename))


    def __str__(self):  # todo
        return basic_str(self)


    @classmethod
    def process_uploaded_file(cls, upload_file_job_pk):
        """
        enqueue() helper function. processes the passed UploadFileJob's pk
        """
        upload_file_job = get_object_or_404(UploadFileJob, pk=upload_file_job_pk)
        logger.debug("process_uploaded_file(): started. upload_file_job={}".format(upload_file_job))

        # todo xx 6. worker processes the next job:
        # - (updates state after each step:)
        # - get the corresponding task's pk from meta data
        # - download the file content from S3
        # - load it into the database
        # - set task result JSON
