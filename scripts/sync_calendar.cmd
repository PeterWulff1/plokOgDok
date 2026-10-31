@echo off
rem Daily calendar sync, run by Windows Task Scheduler (see docs/decisions.md, 2026-10-31).
rem Output is appended to data\logs\calendar-sync.log.
cd /d "%~dp0.."
if not exist data\logs mkdir data\logs
uv run python -m scraper.fetch_calendar >> data\logs\calendar-sync.log 2>&1
