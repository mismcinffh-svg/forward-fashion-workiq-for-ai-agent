@echo off
REM AI-agent entry point: no pause and no manual technical commands.
setlocal
set "HERE=%~dp0"
set "PY="
if exist "%USERPROFILE%\.buddy-365\venv\Scripts\python.exe" set "PY=%USERPROFILE%\.buddy-365\venv\Scripts\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
if not defined PY for /f "delims=" %%i in ('where py 2^>nul') do if not defined PY set "PY=%%i"
if not defined PY (
  echo [X] Python 3.9+ was not found. The AI agent must install or locate Python first. 1>&2
  exit /b 2
)
"%PY%" -u "%HERE%agent_setup.py" %*
exit /b %errorlevel%
