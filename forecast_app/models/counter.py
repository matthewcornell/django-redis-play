import logging
import time

from django.db import models


logger = logging.getLogger(__name__)


def basic_str(obj):
    """
    Handy for writing quick and dirty __str__() implementations.
    """
    return obj.__class__.__name__ + ': ' + obj.__repr__()


class Counter(models.Model):
    """
    A simple model that's used as a singleton.
    """
    count = models.IntegerField(help_text="The current count.", default=0)

    # auto_now: Automatically set the field to now every time the object is saved.
    last_update = models.DateTimeField(help_text="Last time the counter was updated.", auto_now=True)


    def __repr__(self):
        return str((self.pk, self.count, self.last_update))


    def __str__(self):  # todo
        return basic_str(self)


    @classmethod
    def get_count_and_last_update(cls):
        singleton = cls._get_singleton_record()
        return singleton.count, singleton.last_update


    @classmethod
    def increment_count(cls):
        """
        enqueue() helper function. simulates a long-running operation
        """
        singleton = cls._get_singleton_record()
        logger.debug("increment_count(): started. singleton={}".format(singleton))
        time.sleep(2)
        logger.debug("increment_count(): back awake".format())
        singleton.count += 1
        singleton.save()  # updates updated_at via auto_now
        logger.debug("increment_count(): done. singleton={}".format(singleton))


    @classmethod
    def _get_singleton_record(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
