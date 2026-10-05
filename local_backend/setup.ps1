# One-time setup for the F1X8 local backend. Idempotent — safe to re-run.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. venv
if (-not (Test-Path .venv)) {
    Write-Host "Creating venv..." -ForegroundColor Cyan
    py -3.12 -m venv .venv
}
$pip = ".\.venv\Scripts\python.exe -m pip"

# 2. CUDA torch for RTX 5090 (sm_120 needs the cu128 wheels)
Write-Host "Installing torch (cu128)..." -ForegroundColor Cyan
Invoke-Expression "$pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128"

# 3. Everything else
Write-Host "Installing requirements..." -ForegroundColor Cyan
Invoke-Expression "$pip install -r requirements.txt"

# 4. decord (video reader for qwen-vl-utils). No py3.12 wheel on some setups —
#    perception degrades gracefully without it, so failure here is non-fatal.
try { Invoke-Expression "$pip install decord" } catch { Write-Warning "decord install failed - video perception may be degraded" }

# 5. TASED-Net repo at the path saliency_module.py expects (/content/TASED-Net on D:)
if (-not (Test-Path "D:\content\TASED-Net")) {
    Write-Host "Cloning TASED-Net..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force "D:\content" | Out-Null
    git clone https://github.com/MichiganCOG/TASED-Net "D:\content\TASED-Net"
}

# 6. TASED weights (video saliency). Public checkpoint from the TASED-Net authors.
if (-not (Test-Path "weights\TASED_updated.pt")) {
    Write-Host "Downloading TASED weights via gdown..." -ForegroundColor Cyan
    Invoke-Expression "$pip install gdown"
    # Official checkpoint linked from the TASED-Net README (MichiganCOG/TASED-Net)
    & .\.venv\Scripts\gdown.exe --fuzzy "https://drive.google.com/file/d/1y4KSTm-e7kP84k0IyVI-rRtmYZkrC-wL/view" -O "weights\TASED_updated.pt"
}

# 7. AAM saliency (ICML 2026) — upgrade over OpenCV/TASED; app.py auto-enables
#    it (F1X8_SALIENCY=aam) when the repo + weights are present.
if (-not (Test-Path "D:\content\Attend-to-Anything")) {
    Write-Host "Cloning Attend-to-Anything (AAM)..." -ForegroundColor Cyan
    git clone --depth 1 https://github.com/wz-zhao/Attend-to-Anything "D:\content\Attend-to-Anything"
}
Invoke-Expression "$pip install easydict einops loguru open_clip_torch wav2clip"
if (-not (Test-Path "weights\AAM.pth")) {
    Write-Host "Downloading AAM checkpoint via gdown (1.7 GB)..." -ForegroundColor Cyan
    # Official checkpoint linked from the AAM README (wz-zhao/Attend-to-Anything)
    & .\.venv\Scripts\python.exe -m gdown "1ttIONm6Mzx2n5d1cqRXrq95hHbYT32Bt" -O "weights\AAM.pth"
}

Write-Host "Setup complete. Start the server with .\run.ps1" -ForegroundColor Green
