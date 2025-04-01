#!/bin/bash

echo "Updating package lists..."
apt-get update

echo "Installing dependencies..."
apt-get install -y wget unzip curl

echo "Installing Google Chrome..."
wget -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
dpkg -i /tmp/chrome.deb || apt-get -fy install  # Fix dependencies

echo "Installing Chromedriver..."
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d'.' -f1)
wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${CHROME_VERSION}.0.0/chromedriver_linux64.zip
unzip /tmp/chromedriver.zip -d /usr/local/bin/
chmod +x /usr/local/bin/chromedriver

echo "Starting Flask API..."
gunicorn -w 1 -b 0.0.0.0:$PORT app:app
