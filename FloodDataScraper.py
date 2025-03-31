import json
import time
import threading
import pandas as pd
import csv
from flask import Flask, jsonify, send_file
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from flask_cors import CORS
import os
import shutil

# ✅ Flask Web App
app = Flask(__name__)
CORS(app)

SENSOR_DATA_FILE = "sensor_data.json"
CSV_FILE_PATH = "sensor_data.csv"

# ✅ Configure Chromedriver Binary Path
CHROME_BINARY_PATH = "/usr/bin/chromium-browser"

# ✅ Function to Scrape Data
def scrape_sensor_data():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = CHROME_BINARY_PATH  # ✅ Set Chrome binary path

    chromedriver_path = shutil.which("chromedriver")
    driver = webdriver.Chrome(executable_path=chromedriver_path, options=options)

    try:
        url = "https://app.iriseup.ph/sensor_networks"
        print(f"🌍 Fetching data from: {url}")
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )

        sensor_data = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")

            if len(cols) >= 5:
                sensor_name = cols[0].text.strip()
                location = cols[1].text.strip()
                current_level = cols[3].text.strip()
                normal_level = cols[2].text.strip()
                description = cols[4].text.strip() if len(cols) > 4 else "N/A"

                sensor_data.append({
                    "SENSOR NAME": sensor_name,
                    "OBS TIME": location,
                    "NORMAL LEVEL": normal_level,
                    "CURRENT": current_level,
                    "DESCRIPTION": description
                })

        if not sensor_data:
            raise ValueError("No sensor data extracted. Check website structure.")

        print("✅ Scraped Sensor Data:", sensor_data)
        save_csv(sensor_data)
        convert_csv_to_json()
        print("✅ Sensor data updated successfully.")
    except Exception as e:
        print(f"❌ Scraping Failed: {e}")
    finally:
        driver.quit()

# ✅ Save Data to CSV
def save_csv(sensor_data):
    df = pd.DataFrame(sensor_data)
    df.to_csv(CSV_FILE_PATH, index=False)
    print("✅ CSV file saved successfully.")

# ✅ Convert CSV to JSON
def convert_csv_to_json():
    df = pd.read_csv(CSV_FILE_PATH)
    categorized_data = {"sensors": df.to_dict(orient="records")}
    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(categorized_data, f, indent=4)
    print("✅ JSON data structured correctly.")

# ✅ Flask API Route
@app.route("/api/sensor-data", methods=["GET"])
def get_sensor_data():
    try:
        with open(SENSOR_DATA_FILE, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "No valid data available yet"}), 404

# ✅ Background Scraper
def start_auto_scraper():
    while True:
        print("🔄 Running data scraper...")
        scrape_sensor_data()
        print("⏳ Waiting 60 seconds before next scrape...")
        time.sleep(60)

# ✅ Run Flask App
if __name__ == "__main__":
    scraper_thread = threading.Thread(target=start_auto_scraper, daemon=True)
    scraper_thread.start()
    print("🚀 Flask API running at http://0.0.0.0:5000/")
    app.run(debug=True, host="0.0.0.0", port=5000)
