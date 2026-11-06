@echo off
REM ===================================================================
REM  Work IQ MCP bridge launcher for WorkBuddy
REM  Speaks MCP over stdio, forwards to the Work IQ hosted endpoint,
REM  renewing the OAuth token silently from the MSAL token cache.
REM ===================================================================
setlocal
set "HERE=%~dp0"

REM --- Locate a Python 3 interpreter -------------------------------------
REM Prefer the venv that the m365-buddy skill already created.
set "PY="
if exist "%USERPROFILE%\.buddy-365\venv\Scripts\python.exe" (
  set "PY=%USERPROFILE%\.buddy-365\venv\Scripts\python.exe"
)
if not defined PY (
  for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PY set "PY=%%i"
  )
)
if not defined PY (
  for /f "delims=" %%i in ('where py 2^>nul') do (
    if not defined PY set "PY=%%i"
  )
)
if not defined PY (
  echo [work-iq] No Python interpreter found. Install Python 3.9+ and retry. 1>&2
  exit /b 1
)

set "BRIDGE=%HERE%workiq_bridge.py"
if not exist "%BRIDGE%" (
  echo [work-iq] Bridge script not found: %BRIDGE% 1>&2
  exit /b 1
)

REM The MSAL cache lives in %USERPROFILE%\.workbuddy\workiq by default.
if not exist "%USERPROFILE%\.workbuddy\workiq\msal_token_cache.bin" (
  echo [work-iq] No cached session found - run setup.cmd once to sign in. 1>&2
)

"%PY%" "%BRIDGE%"
