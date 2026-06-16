#!/bin/bash
echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt

echo "Building executable with PyInstaller..."
pyinstaller --name CephOverseer --windowed --noconfirm main.py

echo "Build complete! Check the dist/ directory."
