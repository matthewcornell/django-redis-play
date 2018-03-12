import time

from django.db import models


class Counter(models.Model):
    """
    A simple model that's used as a singleton.
    """
    count = models.IntegerField(help_text="The current count.", default=0)
    last_update = models.DateTimeField(help_text="Last time the counter was updated.", auto_now=True)

    def __repr__(self):
        return str((self.pk, self.count, self.last_update))

    @classmethod
    def get_count_and_last_update(cls):
        singleton = cls._get_singleton_record()
        return singleton.count, singleton.last_update


    @classmethod
    def increment_count(cls):
        singleton = cls._get_singleton_record()
        print("increment_count(): singleton={}".format(singleton))
        time.sleep(2)  # simulate long-running function
        print("  back awake".format())
        singleton.count += 1  # last_update handled by auto_nows
        singleton.save()
        print("  done".format())


    @classmethod
    def _get_singleton_record(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
