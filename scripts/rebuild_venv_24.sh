#!/bin/bash
# Task 24: rebuild zemest backend venv after another sandbox reset,
# with the CVE-fix + Huey/APScheduler requirements batch.
set -x
cd /home/z/my-project/repos/zemest
python3 -m venv .venv
.venv/bin/pip install --upgrade pip wheel setuptools 2>&1
.venv/bin/pip install -r requirements.txt 2>&1
# Pin bcrypt below 5.x (passlib 1.7.4 crashes with bcrypt 5)
.venv/bin/pip install "bcrypt==4.1.3" 2>&1
echo "===INSTALL DONE rc=$?==="
.venv/bin/python -c "import fastapi, starlette, jose, huey, apscheduler, icalendar, multipart, jinja2, dotenv, aiosmtplib, sqladmin, litellm; print('fastapi', fastapi.__version__); print('starlette', starlette.__version__); print('jose', jose.__version__); print('huey OK'); print('apscheduler', apscheduler.version if hasattr(apscheduler,'version') else 'ok')"
echo "===ALL DONE==="
