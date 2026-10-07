@echo off
cd /d D:\F1X8
set PYTHONIOENCODING=utf-8
set HF_HOME=D:\F1X8\local_backend\hf-cache
D:\F1X8\.venv-train\Scripts\python.exe eval\finetune\retrain_monthly.py > eval\finetune\out_samsung\retrain_last.log 2>&1
