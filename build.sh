#!/usr/bin/env bash
# Build step for Render (and any similar host). Runs on every deploy.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py createcachetable
