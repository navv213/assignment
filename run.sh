#!/bin/bash
set -e
echo "Setting up Lyftr AI Scraper..."

cd "$(dirname "$0")"  # Ensure we're in project root

# Use python3 (not python3.10) for Mac compatibility
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
playwright install --with-deps chromium

echo "✅ Server ready on http://localhost:8000"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
