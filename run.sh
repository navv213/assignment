#!/bin/bash
set -e
echo "Setting up Lyftr AI Scraper..."

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

echo "Starting server on http://localhost:8000"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
