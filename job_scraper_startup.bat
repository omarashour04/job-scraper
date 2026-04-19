@echo off
REM ============================================================
REM  job_scraper_startup.bat
REM
REM  INSTALLATION:
REM    1. Edit SCRAPER_DIR below to the full path of job_scraper\
REM    2. Press Win+R, type:  shell:startup   → opens Startup folder
REM    3. Copy THIS .bat file into that Startup folder
REM    4. Restart or log out/in — the scraper will run automatically
REM
REM  The scraper runs minimised in the background.
REM  Results are written to:  job_tracker.xlsx  (in SCRAPER_DIR)
REM  Logs are written to:     scraper.log       (in SCRAPER_DIR)
REM ============================================================

REM ── EDIT THIS PATH to match where you placed job_scraper\ ──
set SCRAPER_DIR=C:\Users\%USERNAME%\Desktop\job_scraper

REM ── Optional: path to python.exe if not on PATH ───────────
REM set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe
set PYTHON=python

REM ── Wait 60 seconds after login to let network connect ────
timeout /t 60 /nobreak >nul

REM ── Run the scraper minimised (--quick skips LinkedIn to avoid bans) ──
start "Job Scraper" /min %PYTHON% "%SCRAPER_DIR%\main.py" --quick

REM ── To run with LinkedIn too, replace the line above with: ──
REM start "Job Scraper" /min %PYTHON% "%SCRAPER_DIR%\main.py"
