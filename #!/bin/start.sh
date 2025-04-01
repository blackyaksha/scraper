#!/bin/bash

# Install Chrome & Chromedriver
apt-get update
apt-get install -y google-chrome-stable chromium-chromedriver

# Start the Flask app with Gunicorn
gunicorn -w 1 -b 0.0.0.0:$PORT app:app
