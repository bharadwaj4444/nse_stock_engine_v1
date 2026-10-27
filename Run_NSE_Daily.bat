
@echo off
setlocal

cd /d C:\prg\python\nse_stock_engine_v1

echo ==========================================
echo NSE Stock Engine - Daily Data and Analysis
echo Started: %DATE% %TIME%
echo ==========================================

echo.
echo [1/3] Downloading and processing latest market data...
python -m app.cli daily
if errorlevel 1 goto failed

echo.
echo [2/3] Finding the latest available trading date...
for /f "usebackq delims=" %%D in (`python -c "from app.ttm import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('SELECT MAX(trade_date) FROM daily_prices')).scalar()); c.close()"`) do set "ANALYZE_DATE=%%D"

if not defined ANALYZE_DATE (
    echo ERROR: Could not determine the latest trading date.
    goto failed
)

echo Latest available date: %ANALYZE_DATE%

echo.
echo [3/3] Running analysis...
python -m app.cli analyze --date %ANALYZE_DATE%
if errorlevel 1 goto failed

echo.
echo ==========================================
echo Daily run completed successfully.
echo Analysis date: %ANALYZE_DATE%
echo Finished: %DATE% %TIME%
echo ==========================================
goto end

:failed
echo.
echo ERROR: A step failed. Check the output above.
echo The batch file stopped to avoid continuing blindly.

:end
pause
endlocal
