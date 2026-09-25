# Start the F1X8 local backend on http://127.0.0.1:8010
# (8000 is taken by another local model server on this machine)
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PATH = "$PSScriptRoot\.venv\Scripts;$env:PATH"
& .\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8010
