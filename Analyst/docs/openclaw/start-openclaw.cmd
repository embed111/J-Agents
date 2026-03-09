@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "GATEWAY_HOST=127.0.0.1"
set "GATEWAY_PORT=18789"
set "DASHBOARD_URL=http://%GATEWAY_HOST%:%GATEWAY_PORT%/"
set "OPENCLAW_CMD="
set "DRY_RUN=0"

if /I "%~1"=="--dry-run" set "DRY_RUN=1"

title OpenClaw Launcher
echo [OpenClaw] Launcher starting...

call :find_openclaw
if not defined OPENCLAW_CMD (
  echo [ERROR] openclaw command not found.
  echo [TIP] Run npm install -g openclaw first.
  echo [TIP] Common path: %%APPDATA%%\npm\openclaw.cmd
  pause
  exit /b 1
)

echo [INFO] CLI: "%OPENCLAW_CMD%"

call :is_gateway_ready
if %errorlevel% EQU 0 (
  echo [INFO] Gateway is already running. Opening Dashboard...
  if "%DRY_RUN%"=="1" (
    echo [DRY-RUN] Would open: %DASHBOARD_URL%
    exit /b 0
  )
  start "" "%DASHBOARD_URL%"
  exit /b 0
)

echo [INFO] Gateway is not running. Starting it now...
if "%DRY_RUN%"=="1" (
  echo [DRY-RUN] Would run: "%OPENCLAW_CMD%" gateway
  echo [DRY-RUN] Would wait for port %GATEWAY_PORT% then open: %DASHBOARD_URL%
  exit /b 0
)

start "OpenClaw Gateway" cmd /k ""%OPENCLAW_CMD%" gateway"

set /a WAIT_SECONDS=30
for /L %%I in (1,1,%WAIT_SECONDS%) do (
  call :is_gateway_ready
  if !errorlevel! EQU 0 (
    echo [INFO] Gateway is ready. Opening Dashboard...
    start "" "%DASHBOARD_URL%"
    exit /b 0
  )
  echo [WAIT] Gateway starting... %%I/%WAIT_SECONDS%
  >nul timeout /t 1 /nobreak
)

echo [ERROR] Gateway was not ready within %WAIT_SECONDS% seconds.
echo [TIP] Check the "OpenClaw Gateway" window for details.
echo [TIP] Logs are usually in %%LOCALAPPDATA%%\Temp\openclaw\
pause
exit /b 1

:find_openclaw
for /f "delims=" %%I in ('where openclaw.cmd 2^>nul') do (
  if not defined OPENCLAW_CMD set "OPENCLAW_CMD=%%~fI"
)

if not defined OPENCLAW_CMD if exist "%APPDATA%\npm\openclaw.cmd" (
  set "OPENCLAW_CMD=%APPDATA%\npm\openclaw.cmd"
)

if not defined OPENCLAW_CMD if exist "%USERPROFILE%\AppData\Roaming\npm\openclaw.cmd" (
  set "OPENCLAW_CMD=%USERPROFILE%\AppData\Roaming\npm\openclaw.cmd"
)

if not defined OPENCLAW_CMD (
  for /f "delims=" %%I in ('npm prefix -g 2^>nul') do (
    if exist "%%~fI\openclaw.cmd" set "OPENCLAW_CMD=%%~fI\openclaw.cmd"
  )
)
exit /b 0

:is_gateway_ready
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$client = New-Object System.Net.Sockets.TcpClient; try { $ar = $client.BeginConnect('%GATEWAY_HOST%', %GATEWAY_PORT%, $null, $null); if (-not $ar.AsyncWaitHandle.WaitOne(400)) { exit 1 }; $client.EndConnect($ar); exit 0 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>nul
exit /b %errorlevel%
