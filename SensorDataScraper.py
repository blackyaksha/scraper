import json
import time
import threading
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict, List, Any
import logging
import os

# === Paths ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENSOR_DATA_FILE = os.path.join(BASE_DIR, "sensor_data.json")
CSV_FILE_PATH = os.path.join(BASE_DIR, "sensor_data.csv")

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# === FastAPI App ===
app = FastAPI(title="Flood Data Scraper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Categories ===
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

# === Chrome Driver Setup (Global, reused) ===
driver = None

def setup_chrome_driver():
    global driver
    if driver is not None:
        return driver
    try:
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/chromium"
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--ignore-certificate-errors")

        service = Service("/usr/bin/chromedriver")  # Use system-installed
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(30)
        logger.info("✅ Chrome WebDriver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
        raise

def scrape_sensor_data():
    d = setup_chrome_driver()
    try:
        url = "https://web.iriseup.ph/sensor_networks"
        logger.info(f"🌍 Fetching data from: {url}")
        d.get(url)
        WebDriverWait(d, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )

        sensor_data = []
        rows = d.find_elements(By.CSS_SELECTOR, "table tbody tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                sensor_data.append({
                    "SENSOR NAME": cols[0].text.strip(),
                    "OBS TIME": cols[1].text.strip(),
                    "NORMAL LEVEL": cols[2].text.strip(),
                    "CURRENT": cols[3].text.strip(),
                    "DESCRIPTION": cols[4].text.strip() if len(cols) > 4 else "N/A"
                })

        if not sensor_data:
            raise ValueError("No sensor data extracted. Website structure may have changed.")

        save_csv(sensor_data)
        convert_csv_to_json()
        logger.info(f"✅ Scraped {len(sensor_data)} sensor records")
    except Exception as e:
        logger.error(f"❌ Scraping failed: {str(e)}")

def save_csv(sensor_data):
    df = pd.DataFrame(sensor_data)
    df.to_csv(CSV_FILE_PATH, index=False)
    logger.info("✅ CSV file saved successfully.")

def convert_csv_to_json():
    df = pd.read_csv(CSV_FILE_PATH)
    categorized_data = {category: [] for category in SENSOR_CATEGORIES}

    for _, row in df.iterrows():
        sensor_name = row["SENSOR NAME"]
        current_value = row["CURRENT"]
        normal_value = row.get("NORMAL LEVEL", "N/A")
        description = row.get("DESCRIPTION", "N/A")

        sensor_entry = {"SENSOR NAME": sensor_name, "CURRENT": current_value}

        if "m" in str(current_value):
            category = "street_flood_sensors"
            sensor_entry["NORMAL LEVEL"] = normal_value
            sensor_entry["DESCRIPTION"] = description
        else:
            category = "flood_risk_index"

        if sensor_name in SENSOR_CATEGORIES.get(category, []):
            categorized_data[category].append(sensor_entry)

    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(categorized_data, f, indent=4)
    logger.info("✅ JSON file updated successfully.")

@app.get("/api/sensor-data", response_model=Dict[str, List[Dict[str, Any]]])
async def get_sensor_data():
    try:
        with open(SENSOR_DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        logger.warning("⚠️ sensor_data.json not found or invalid, returning empty data.")
        return {key: [] for key in SENSOR_CATEGORIES.keys()}

# === Background Scraper ===
def start_auto_scraper():
    while True:
        logger.info("🔄 Running scheduled scrape...")
        scrape_sensor_data()
        logger.info("⏳ Sleeping 10 minutes...")
        time.sleep(600)  # every 10 minutes

# Ensure sensor_data.json exists at startup
try:
    if not os.path.exists(SENSOR_DATA_FILE):
        logger.info("Sensor data file not found, running initial scrape...")
        scrape_sensor_data()
except Exception as e:
    logger.error(f"Error during initial scrape: {e}")

# Start background scraper
scraper_thread = threading.Thread(target=start_auto_scraper, daemon=True)
scraper_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("SensorDataScraper:app", host="0.0.0.0", port=10000, reload=False)
