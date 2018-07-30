# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-07-30 16:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Counter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('count', models.IntegerField(default=0, help_text='The current count.')),
                ('last_update', models.DateTimeField(auto_now=True, help_text='Last time the counter was updated.')),
            ],
        ),
        migrations.CreateModel(
            name='UploadFileJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When the file was uploaded.')),
                ('filename', models.CharField(help_text='Original name of the uploaded file.', max_length=200)),
                ('status', models.IntegerField(choices=[(0, 'PENDING'), (1, 'S3_FILE_UPLOADED'), (2, 'QUEUED'), (3, 'S3_FILE_DOWNLOADED'), (4, 'FORECAST_LOADED'), (6, 'FAILED_S3_FILE_UPLOAD'), (7, 'FAILED_ENQUEUE'), (8, 'FAILED_PROCESS_FILE')], default=0)),
                ('is_deleted', models.BooleanField(default=False)),
            ],
        ),
    ]
