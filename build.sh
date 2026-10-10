#!/usr/bin/env bash
# Build step for Render (and any similar host). Runs on every deploy.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py createcachetable
# First-deploy conveniences; both are no-ops once done or when their variables aren't set.
python manage.py ensure_admin
if [ -n "${DEMO_OWNER_PASSWORD:-}" ]; then
  python manage.py seed_demo
fi
