@echo off
REM ===================================================================
REM  Work IQ MCP — one-click setup for WorkBuddy
REM
REM  What it does:
REM    1. checks Python
REM    2. signs you in to Microsoft 365 (browser, PKCE - once only)
REM    3. registers the connector in WorkBuddy's mcp.json
REM
REM  You must be signed in with YOUR OWN work account.
REM  After the first sign-in everything is silent - the browser never
REM  opens again and consent is never re-requested.
REM ===================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Work IQ MCP Setup

set "HERE=%~dp0"
cd /d "%HERE%"

echo.
echo ================================================================
echo   Work IQ MCP  -  WorkBuddy Setup
echo ================================================================
echo.

REM --- 1. Locate Python -------------------------------------------------
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
  echo [X] No Python 3 found. Install Python 3.9+ and run this file again.
  pause
  exit /b 1
)
echo [1/3] Python OK
"%PY%" -c "import msal" 2>nul
if errorlevel 1 (
  echo        Installing the Microsoft authentication library, MSAL...
  "%PY%" -m pip install msal
  if errorlevel 1 (
    echo [X] Could not install MSAL. Check Python/pip and your network.
    pause
    exit /b 1
  )
)
"%PY%" -c "import msal" 2>nul
if errorlevel 1 (
  echo [X] MSAL is still unavailable after installation.
  pause
  exit /b 1
)
echo        MSAL OK
echo.

REM --- 2. Sign in (browser, once) ---------------------------------------
echo [2/3] Signing in to Microsoft 365...
echo        (a browser window will open - sign in with YOUR OWN account)
echo.
"%PY%" "%HERE%signin.py" --check
if errorlevel 1 (
  echo.
  echo [!] Sign-in did not complete. Common causes:
  echo     - You do not have access to Work IQ in this tenant.
  echo       Ask your IT admin to check the Work IQ app assignment.
  echo     - The browser login was cancelled or timed out.
  echo       Run this file again.
  echo.
  pause
  exit /b 2
)
echo.

REM --- 3. Register ------------------------------------------------------
echo [3/3] Registering the connector...
"%PY%" "%HERE%install.py"
if errorlevel 1 (
  echo.
  echo [!] Registration failed.
  pause
  exit /b 3
)
echo.
echo ================================================================
echo   Done. Now finish in the WorkBuddy app:
echo     1. Fully quit WorkBuddy (tray icon -> Quit), then reopen
echo     2. Connectors -> Custom Connectors (top right)
echo     3. Find 'work-iq' -> Trust  ->  status becomes Enabled
echo     4. Open a NEW chat and ask:
echo        List all available tools under the work-iq connector
echo ================================================================
echo.
pause
