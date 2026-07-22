#!/bin/bash
# NiceGUI lit PORT depuis l'env (défini par Azure) et bind sur 0.0.0.0 côté script.
export PORT="${PORT:-8000}"
python mail_manager/nicegui_app.py
