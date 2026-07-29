@echo off
rem Weekly F1X8 ranker retrain (registered in Windows Task Scheduler).
cd /d "D:\AI Agent\fixation-ui"
python eval\finetune\weekly_retrain.py >> eval\finetune\data\weekly_log.txt 2>&1
