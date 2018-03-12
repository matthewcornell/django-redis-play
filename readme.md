A Simple Django app to demonstrate Redis Queue (RQ) integration, with deployment to Heroku.


# To run locally

1. Start Redis:
```$bash
redis-server
```

1. Start an rq worker:
```$bash
cd ~/IdeaProjects/django-redis-play
pipenv shell
export PATH="/Applications/Postgres.app/Contents/Versions/9.6/bin:${PATH}" ; export DJANGO_SETTINGS_MODULE=forecast_repo.settings.local_sqlite3 ; export PYTHONPATH=.
python3 manage.py rqworker
```

1. Optionally start `rq info`:
```$bash
cd ~/IdeaProjects/django-redis-play
pipenv shell
rq info --interval 1
```

1. start the web app:
```$bash
cd ~/IdeaProjects/django-redis-play
pipenv shell
python3 manage.py runserver --settings=forecast_repo.settings.local_sqlite3
```
