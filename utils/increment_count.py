import click
import django


# set up django. must be done before loading models. NB: requires DJANGO_SETTINGS_MODULE to be set
import django_rq


django.setup()

from forecast_app.models import Counter


@click.command()
def increment_counter_app():
    count, last_update = Counter.get_count_and_last_update()
    job = django_rq.enqueue(Counter.increment_count)
    click.echo("* increment_counter_app(): start: count={}, last_update={}. job={}".format(count, last_update, job))


if __name__ == '__main__':
    increment_counter_app()
