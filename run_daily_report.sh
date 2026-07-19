#!/bin/bash
# Wrapper pour cron : active le venv et lance daily_report.py
cd /Users/ilhameouhaddou/Desktop/Agent_PA-1
source .venv/bin/activate
python daily_report.py >> daily_report.log 2>&1
