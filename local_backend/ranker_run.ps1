# Starts the local ranker sidecar (port 8012). Requires ..\.venv-train
# (created by eval/finetune setup — torch cu128 + transformers 5.x).
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HOME = "$PSScriptRoot\hf-cache"
Set-Location $PSScriptRoot
& ..\.venv-train\Scripts\python.exe -m uvicorn ranker_service:app --host 127.0.0.1 --port 8012
