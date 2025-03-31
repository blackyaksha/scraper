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

# ✅ Flask Web App
app = Flask(__name__)
CORS(app)

# Get port from environment variable or default to 5000
port = int(os.environ.get("PORT", 5000))

SENSOR_DATA_FILE = "sensor_data.json"
CSV_FILE_PATH = "sensor_data.csv"

# ✅ Sensor Categories
SENSOR_CATEGORIES = {
    "rain_gauge": [
        "QCPU", "Masambong", "Batasan Hills", "Ugong Norte", "Ramon Magsaysay HS",
        "UP Village", "Dona Imelda", "Kaligayahan", "Emilio Jacinto Sr HS", "Payatas ES",
        "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit", "Libis",
        "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa",
        "Brgy Fairview (REC)", "Brgy Baesa Hall", "Brgy N.S Amoranto Hall", "Brgy Valencia Hall"
    ],
    "flood_sensors": [
        "North Fairview", "Batasan-San Mateo", "Bahay Toro", "Sta Cruz", "San Bartolome"
    ],
    "street_flood_sensors": [
        "N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street",
        "Christine Street", "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit",
        "Libis", "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa"
    ],
    "flood_risk_index": [
        "N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street",
        "Christine Street", "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit",
        "Libis", "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa"
    ],
    "earthquake_sensors": ["QCDRRMO", "QCDRRMO REC"]
}

# ✅ Function to Scrape All Data from iRiseUP Website
def scrape_sensor_data():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    try:
        # Use ChromeDriverManager for reliable ChromeDriver installation
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        # Initialize Chrome driver with ChromeDriverManager
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        
    except Exception as e:
        print(f"Failed to initialize Chrome driver with ChromeDriverManager: {e}")
        print("Attempting to use system Chrome and ChromeDriver...")
        
        try:
            # Get Chrome and ChromeDriver paths from environment variables
            chrome_path = os.environ.get('CHROME_PATH', '/usr/bin/google-chrome')
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver')
            
            # Verify Chrome exists
            if not os.path.exists(chrome_path):
                print(f"Chrome not found at {chrome_path}, checking alternative locations...")
                # Try to find Chrome in common locations
                possible_paths = [
                    '/usr/bin/google-chrome',
                    '/usr/bin/google-chrome-stable',
                    '/usr/local/bin/google-chrome',
                    '/usr/local/bin/google-chrome-stable'
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        chrome_path = path
                        print(f"Found Chrome at {path}")
                        break
                else:
                    raise FileNotFoundError("Chrome not found in any common locations")
                
            # Verify ChromeDriver exists
            if not os.path.exists(chromedriver_path):
                print(f"ChromeDriver not found at {chromedriver_path}, checking alternative locations...")
                # Try to find ChromeDriver in common locations
                possible_paths = [
                    '/usr/local/bin/chromedriver',
                    '/usr/bin/chromedriver',
                    '/opt/chromedriver'
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        chromedriver_path = path
                        print(f"Found ChromeDriver at {path}")
                        break
                else:
                    raise FileNotFoundError("ChromeDriver not found in any common locations")
            
            # Set Chrome binary location
            options.binary_location = chrome_path
            
            # Create service with specific ChromeDriver path
            service = Service(executable_path=chromedriver_path)
            
            # Initialize Chrome driver
            driver = webdriver.Chrome(service=service, options=options)
            
        except Exception as system_error:
            print(f"Failed to initialize Chrome driver with system Chrome: {system_error}")
            raise

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

        # ✅ Save Data to CSV
        save_csv(sensor_data)

        # ✅ Convert CSV to JSON
        convert_csv_to_json()

        print("✅ Sensor data updated successfully.")

    except Exception as e:
        print(f"❌ Scraping Failed: {e}")

    finally:
        driver.quit()

# ✅ Save Data to CSV (Including All Columns)
def save_csv(sensor_data):
    df = pd.DataFrame(sensor_data)
    df.to_csv(CSV_FILE_PATH, index=False)
    print("✅ CSV file saved successfully with all sensor data.")

# ✅ Convert CSV to JSON with All Data (Updated to distinguish Street Flood Sensors & Flood Risk Index)
def convert_csv_to_json():
    df = pd.read_csv(CSV_FILE_PATH)

    categorized_data = {category: [] for category in SENSOR_CATEGORIES}  

    for _, row in df.iterrows():
        sensor_name = row["SENSOR NAME"]
        current_value = row["CURRENT"]
        normal_value = row["NORMAL LEVEL"] if "NORMAL LEVEL" in df.columns else "N/A"
        description = row["DESCRIPTION"] if "DESCRIPTION" in df.columns else "N/A"

        sensor_entry = {
            "SENSOR NAME": sensor_name,
            "CURRENT": current_value,
        }

        # ✅ Check if "m" is in `CURRENT` value → Street Flood Sensor
        if "m" in str(current_value):
            category = "street_flood_sensors"
            sensor_entry["NORMAL LEVEL"] = normal_value
            sensor_entry["DESCRIPTION"] = description
        else:
            category = "flood_risk_index"

        # ✅ Append to correct category
        if sensor_name in SENSOR_CATEGORIES[category]:
            categorized_data[category].append(sensor_entry)

    # ✅ Add other categories (Rain Gauge, Flood Sensors, Earthquake Sensors)
    for category, sensors in SENSOR_CATEGORIES.items():
        if category not in ["street_flood_sensors", "flood_risk_index"]:  # ✅ Already handled above
            for sensor_name in sensors:
                matching_sensor = df[df["SENSOR NAME"].str.casefold() == sensor_name.casefold()]
                if not matching_sensor.empty:
                    normal_value = matching_sensor.iloc[0]["NORMAL LEVEL"] if "NORMAL LEVEL" in df.columns else "N/A"
                    current_value = matching_sensor.iloc[0]["CURRENT"]
                    description = matching_sensor.iloc[0]["DESCRIPTION"] if "DESCRIPTION" in df.columns else "N/A"

                    sensor_entry = {
                        "SENSOR NAME": sensor_name,
                        "CURRENT": current_value,
                    }

                    if category in ["flood_sensors"]:
                        sensor_entry["NORMAL LEVEL"] = normal_value
                        sensor_entry["DESCRIPTION"] = description

                    categorized_data[category].append(sensor_entry)
                else:
                    # ✅ Default empty structure
                    sensor_entry = {
                        "SENSOR NAME": sensor_name,
                        "CURRENT": "0.0m" if category == "street_flood_sensors" else 0.0,
                    }

                    if category in ["flood_sensors"]:
                        sensor_entry["NORMAL LEVEL"] = "N/A"
                        sensor_entry["DESCRIPTION"] = "N/A"

                    categorized_data[category].append(sensor_entry)

    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(categorized_data, f, indent=4)

    print("✅ JSON data structured correctly with Street Flood Sensor Check.")

# ✅ Flask API Route
@app.route("/api/sensor-data", methods=["GET"])
def get_sensor_data():
    try:
        with open(SENSOR_DATA_FILE, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "No valid data available yet"}), 404

# ✅ Background Scraping Thread
def start_auto_scraper():
    while True:
        print("🔄 Running data scraper...")
        scrape_sensor_data()
        print("⏳ Waiting 60 seconds before the next scrape...")
        time.sleep(60)

# ✅ Run Flask App
if __name__ == "__main__":
    scraper_thread = threading.Thread(target=start_auto_scraper, daemon=True)
    scraper_thread.start()

    print(f"🚀 Flask API running on port {port}")
    app.run(host="0.0.0.0", port=port)
