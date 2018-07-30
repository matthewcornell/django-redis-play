A Simple Django app to demonstrate Redis Queue (RQ) integration, with deployment to Heroku.


# TODO

- explore whether the 'dev' user in the 'developers' group can do anything to any bucket or object:
  https://console.aws.amazon.com/iam/home?region=us-east-1#/groups/developers


# To run locally

1. Start Redis:
```$bash
redis-server
```

2. Start an rq worker:
```$bash
cd ~/IdeaProjects/django-redis-play
pipenv shell
export PATH="/Applications/Postgres.app/Contents/Versions/9.6/bin:${PATH}" ; export DJANGO_SETTINGS_MODULE=forecast_repo.settings.local_sqlite3 ; export PYTHONPATH=.
python3 manage.py rqworker
```

3. Optionally start monitor (`rq info` or `rqstats`):
```$bash
cd ~/IdeaProjects/django-redis-play
pipenv shell
rq info --interval 1

# alternatively:
export PATH="/Applications/Postgres.app/Contents/Versions/9.6/bin:${PATH}" ; export DJANGO_SETTINGS_MODULE=forecast_repo.settings.local_sqlite3 ; export PYTHONPATH=.
python3 manage.py rqstats --interval 1
```

4. Start the web app and then click 'Increment RQ' a few times
```$bash
cd ~/IdeaProjects/django-redis-play
pipenv shell
export PATH="/Applications/Postgres.app/Contents/Versions/9.6/bin:${PATH}" ; export DJANGO_SETTINGS_MODULE=forecast_repo.settings.local_sqlite3 ; export PYTHONPATH=.
export AWS_ACCESS_KEY_ID=<YOUR_ACCESS_KEY> ; export AWS_SECRET_ACCESS_KEY=<YOUR_SECRET_KEY>
python3 manage.py runserver --settings=forecast_repo.settings.local_sqlite3
```

5. Run increment_count.py a few times
```$bash
cd ~/IdeaProjects/django-redis-play
pipenv shell
export PATH="/Applications/Postgres.app/Contents/Versions/9.6/bin:${PATH}" ; export DJANGO_SETTINGS_MODULE=forecast_repo.settings.local_sqlite3 ; export PYTHONPATH=.
python3 utils/increment_count.py
```
