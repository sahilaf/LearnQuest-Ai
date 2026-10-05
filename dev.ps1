# Start LearnQuest - avatar service, backend and frontend - with one command.
#
#   .\dev.ps1              everything, including the Alapon avatar (needs the GPU)
#   .\dev.ps1 -NoAvatar    backend + frontend only; the tutor shows "avatar offline"
#
# Each service logs to .logs\<name>.log. Ctrl+C stops all of them.
#
# Already running something on 5001, 8000 or 5173? That service is left alone
# and reused, so you can restart just one piece by stopping it and re-running.

param(
    [switch]$NoAvatar,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$logs = Join-Path $root ".logs"
New-Item -ItemType Directory -Force $logs | Out-Null

function Say($text, $color = "Gray") { Write-Host $text -ForegroundColor $color }

# Both address families: Vite listens on ::1 only, uvicorn on 127.0.0.1 only.
function Test-Port($port) {
    foreach ($addr in @("127.0.0.1", "::1")) {
        $client = New-Object Net.Sockets.TcpClient([Net.IPAddress]::Parse($addr).AddressFamily)
        # A refused connect takes ~2s on Windows; nothing local needs 300ms.
        try {
            $pending = $client.BeginConnect($addr, $port, $null, $null)
            if ($pending.AsyncWaitHandle.WaitOne(300) -and $client.Connected) { return $true }
        } catch { } finally { $client.Close() }
    }
    return $false
}

# 127.0.0.1, never "localhost": Windows PowerShell tries ::1 first and waits out
# the whole timeout there before the IPv4-only servers are ever asked.
function Get-Health($url) {
    try { return Invoke-RestMethod -Uri $url -TimeoutSec 2 } catch { return $null }
}

# The synctalk conda env's python, without needing `conda activate` first.
function Find-SynctalkPython {
    if ($env:SYNCTALK_PYTHON -and (Test-Path $env:SYNCTALK_PYTHON)) { return $env:SYNCTALK_PYTHON }
    $candidates = @(
        "$env:USERPROFILE\anaconda3\envs\synctalk\python.exe",
        "$env:USERPROFILE\miniconda3\envs\synctalk\python.exe",
        "$env:ProgramData\anaconda3\envs\synctalk\python.exe",
        "$env:ProgramData\miniconda3\envs\synctalk\python.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    return $null
}

$started = @()   # @{ Name; Process; Log }

function Start-DevService($name, $file, $arguments, $dir) {
    $log = Join-Path $logs "$name.log"
    $err = Join-Path $logs "$name.err.log"
    $proc = Start-Process -FilePath $file -ArgumentList $arguments -WorkingDirectory $dir `
        -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden -PassThru
    $script:started += @{ Name = $name; Process = $proc; Log = $log; Err = $err }
    Say "  started $name (pid $($proc.Id))  ->  .logs\$name.log"
}

function Show-Tail($svc) {
    foreach ($f in @($svc.Log, $svc.Err)) {
        if (Test-Path $f) { Get-Content $f -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Say "    $_" "DarkGray" } }
    }
}

# --- Pre-flight ------------------------------------------------------------
$backendPy = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $backendPy)) {
    Say "Backend venv missing. Create it once:" "Red"
    Say "  cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Say "Frontend dependencies missing. Run once:  cd frontend; npm install" "Red"
    exit 1
}

$avatar = -not $NoAvatar
if ($avatar) {
    $synctalkPy = Find-SynctalkPython
    if (-not $synctalkPy) {
        Say "No 'synctalk' conda env found - starting without the avatar." "Yellow"
        Say "  (set SYNCTALK_PYTHON to its python.exe, or pass -NoAvatar to silence this)" "DarkGray"
        $avatar = $false
    }
}
if ($avatar) {
    $battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
    if ($battery -and $battery.BatteryStatus -eq 1) {
        Say "On battery: the GPU throttles and the avatar's mouth will be choppy. Plug in for demos." "Yellow"
    }
}

Say ""
Say "Starting LearnQuest..." "Cyan"

# --- Avatar service (slowest to boot, so first) ----------------------------
if ($avatar) {
    if (Test-Port 5001) {
        Say "  avatar   already running on :5001 - reusing it"
    } else {
        # Put the env's DLLs (CUDA, ffmpeg) on PATH, as `conda activate` would.
        $envDir = Split-Path $synctalkPy
        $env:PATH = "$envDir;$envDir\Library\bin;$envDir\Scripts;$env:PATH"
        $env:PYTHONIOENCODING = "utf-8"
        $env:PYTHONUNBUFFERED = "1"
        Start-DevService "avatar" "powershell.exe" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "run.ps1") (Join-Path $root "avatar-service")
    }
}

# --- Backend ---------------------------------------------------------------
if (Test-Port 8000) {
    Say "  backend  already running on :8000 - reusing it"
} else {
    # An empty AVATAR_SERVICE_URL overrides backend/.env, so the app reports
    # "avatar offline" immediately instead of probing a service that is not there.
    if (-not $avatar) { $env:AVATAR_SERVICE_URL = "" }
    Start-DevService "backend" $backendPy @("-m", "uvicorn", "app.main:app", "--reload", "--port", "8000") (Join-Path $root "backend")
}

# --- Frontend --------------------------------------------------------------
if (Test-Port 5173) {
    Say "  frontend already running on :5173 - reusing it"
} else {
    Start-DevService "frontend" "npm.cmd" @("run", "dev", "--", "--port", "5173", "--strictPort") (Join-Path $root "frontend")
}

# --- Wait until each one is really up --------------------------------------
Say ""
$ready = @{ backend = $false; frontend = $false; avatar = (-not $avatar) }
$browserOpened = $NoBrowser
$t0 = Get-Date

try {
    while ($true) {
        foreach ($svc in $started) {
            if ($svc.Process.HasExited -and -not $svc.Reported) {
                $svc.Reported = $true
                Say "  $($svc.Name) stopped (exit code $($svc.Process.ExitCode)). Last log lines:" "Red"
                Show-Tail $svc
            }
        }

        if (-not $ready.backend -and (Get-Health "http://127.0.0.1:8000/api/health")) {
            $ready.backend = $true
            Say "  backend  ready   http://localhost:8000/docs" "Green"
        }
        if (-not $ready.frontend -and (Test-Port 5173)) {
            $ready.frontend = $true
            Say "  frontend ready   http://localhost:5173" "Green"
        }
        if (-not $ready.avatar) {
            $health = Get-Health "http://127.0.0.1:5001/health"
            if ($health -and $health.models_loaded -and $health.idle_cache.ready) {
                $ready.avatar = $true
                Say "  avatar   ready   Alapon on $($health.device), $($health.image_size)" "Green"
            }
        }

        if ($ready.backend -and $ready.frontend -and -not $browserOpened) {
            $browserOpened = $true
            Start-Process "http://localhost:5173/"
            if (-not $ready.avatar) {
                Say "  (avatar still loading - about 2 minutes; the tutor page shows it once ready, reload if needed)" "DarkGray"
            }
        }
        if ($ready.backend -and $ready.frontend -and $ready.avatar -and -not $announced) {
            $announced = $true
            Say ""
            Say "Everything is up ($([int]((Get-Date) - $t0).TotalSeconds)s). Logs in .logs\  -  Ctrl+C to stop all." "Cyan"
        }

        if ($started.Count -gt 0 -and -not ($started | Where-Object { -not $_.Process.HasExited })) {
            Say "All services have stopped." "Red"
            break
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    # Runs on Ctrl+C too. /T takes the children with it: uvicorn's reloader,
    # npm's node, run.ps1's python.
    if ($started.Count) { Say ""; Say "Stopping..." "Cyan" }
    foreach ($svc in $started) {
        if (-not $svc.Process.HasExited) {
            & taskkill.exe /PID $svc.Process.Id /T /F 2>&1 | Out-Null
            Say "  stopped $($svc.Name)"
        }
    }
}
