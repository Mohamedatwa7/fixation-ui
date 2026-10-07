# Registers the monthly ranker retrain as a Windows scheduled task.
# Runs 1st of each month, 03:00 — off-hours for the shared 5090.
# (schtasks, not New-ScheduledTaskTrigger: PS 5.1 has no -Monthly trigger.)
$wrapper = "D:\F1X8\eval\finetune\run_retrain.cmd"
@"
@echo off
cd /d D:\F1X8
set PYTHONIOENCODING=utf-8
set HF_HOME=D:\F1X8\local_backend\hf-cache
D:\F1X8\.venv-train\Scripts\python.exe eval\finetune\retrain_monthly.py > eval\finetune\out_samsung\retrain_last.log 2>&1
"@ | Out-File -FilePath $wrapper -Encoding ascii
schtasks /Create /F /TN "F1X8 ranker retrain" /TR $wrapper /SC MONTHLY /D 1 /ST 03:00
Write-Host "Registered: F1X8 ranker retrain (monthly, 1st @ 03:00)"
