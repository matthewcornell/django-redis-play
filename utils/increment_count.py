import click
import django


# set up django. must be done before loading models. NB: requires DJANGO_SETTINGS_MODULE to be set
django.setup()

from forecast_app.models import Counter


@click.command()
def increment_counter_app():
    count, last_update = Counter.get_count_and_last_update()
    Counter.increment_count()
    click.echo("* incremented: {}@{} -> {}@{}".format(count, last_update, *Counter.get_count_and_last_update()))


if __name__ == '__main__':
    increment_counter_app()
