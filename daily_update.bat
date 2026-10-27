
@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo NSE Stock Engine - Historical Recovery
echo ==========================================

REM Set recovery window: 30 days ending yesterday.
for /f %%D in ('powershell -NoProfile -Command "(Get-Date).AddDays(-30).ToString('yyyy-MM-dd')"') do set "START_DATE=%%D"
for /f %%D in ('powershell -NoProfile -Command "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') do set "END_DATE=%%D"

echo Recovery window: %START_DATE% to %END_DATE%
echo Today's date is intentionally excluded.
echo.

echo [1/2] Recover missing or incomplete price dates...
python -m app.cli backfill --start %START_DATE% --end %END_DATE%
if errorlevel 1 goto :error

echo.
echo [2/2] Recalculate indicators and analyze...
python scripts\daily_update_processing.py --start %START_DATE% --end %END_DATE%
if errorlevel 1 goto :error

echo.
echo NSE historical recovery completed successfully.
exit /b 0

:error
echo.
echo ERROR: Update failed. Check the output above.
exit /b 1
