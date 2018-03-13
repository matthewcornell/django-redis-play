import django_rq
from django.shortcuts import render, redirect

from forecast_app.models import Counter


def index(request):
    count, last_update = Counter.get_count_and_last_update()
    queue = django_rq.get_queue('default')
    conn = django_rq.get_connection('default')
    return render(request,
                  'index.html',
                  context={'count': count,
                           'last_update': last_update,
                           'queue': queue,
                           'conn': conn})


def increment_counter(request, **kwargs):
    if kwargs['is_rq']:
        return increment_counter_rq(request)
    else:
        return increment_counter_immediate(request)


def increment_counter_immediate(request):
    Counter.increment_count()
    return redirect('index')


def increment_counter_rq(request):
    django_rq.enqueue(Counter.increment_count)
    return redirect('index')
