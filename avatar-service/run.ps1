# Launch the SyncTalk avatar service. OWNER: Member 1. See plan.md §6.6.
#
#   conda activate synctalk
#   .\run.ps1
#
# Reads .env if present, falls back to the defaults below.

$ErrorActionPreference = "Stop"

$defaults = @{
    SYNCTALK_CHECKPOINT = "./checkpoint/final_v2/59.pth"
    SYNCTALK_DATASET    = "C:/Users/sahil/Dropbox/PC/Documents/projects/Fydp_v2/SyncTalk_2D/dataset/redwan"
    SYNCTALK_MODE       = "ave"
    SYNCTALK_HOST       = "0.0.0.0"
    SYNCTALK_PORT       = "5001"
    SYNCTALK_OUT_SIZE   = "0"
}

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$') {
            $defaults[$Matches[1]] = $Matches[2]
        }
    }
}

$ckpt    = $defaults["SYNCTALK_CHECKPOINT"]
$dataset = $defaults["SYNCTALK_DATASET"]

if (-not (Test-Path $ckpt)) {
    Write-Error "Checkpoint not found: $ckpt"
}
foreach ($sub in @("full_body_img", "landmarks")) {
    if (-not (Test-Path (Join-Path $dataset $sub))) {
        Write-Error "Dataset is missing $sub : $dataset`nSee avatar-service/README.md."
    }
}

Write-Host "checkpoint : $ckpt"
Write-Host "dataset    : $dataset"
Write-Host "listening  : http://$($defaults['SYNCTALK_HOST']):$($defaults['SYNCTALK_PORT'])"
Write-Host ""

python avatar_server_ws.py `
    --checkpoint $ckpt `
    --dataset $dataset `
    --mode $defaults["SYNCTALK_MODE"] `
    --host $defaults["SYNCTALK_HOST"] `
    --port $defaults["SYNCTALK_PORT"] `
    --out_size $defaults["SYNCTALK_OUT_SIZE"]
