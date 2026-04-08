@echo off
cd /d "%~dp0.."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo Done. Run: python run.py --skip-admin-check
pause
