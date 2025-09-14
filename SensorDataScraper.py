import json
import time
import threading
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, List, Any
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENSOR_DATA_FILE = os.path.join("/tmp", "sensor_data.json")
CSV_FILE_PATH = os.path.join("/tmp", "sensor_data.csv")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Flood Data Scraper API")

SENSOR_CATEGORIES = {
    "rain_gauge": [
        "QCPU", "Masambong", "Batasan Hills", "Ugong Norte", "Ramon Magsaysay HS",
        "UP Village", "Dona Imelda", "Kaligayahan", "Emilio Jacinto Sr HS", "Payatas ES",
        "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit", "Libis",
        "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa",
        "Balingasa High School", "Toro Hills Elementary School", "Quezon City University San Francisco Campus",
        "Maharlika Brgy Hall", "Bagong Silangan Evacuation Center", "Dona Juana Elementary School",
        "Quirino High School", "Old Balara Elementary School", "Pansol Kaingin 1 Brgy Satellite Office",
        "Jose P Laurel Senior High School", "Pinyahan Multipurose Hall", "Sikatuna Brgy Hall",
        "Kalusugan Brgy Hall", "Laging Handa Barangay Hall", "Amoranto Sport Complex", "Maligaya High School",
        "San Agustin Brgy Hall", "Jose Maria Panganiban Senior High School", "North Fairview Elementary School",
        "Sauyo Elementary School", "New Era Brgy Hall", "Ismael Mathay Senior High School"
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

def setup_chrome_driver():
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(30)
    return driver

def wait_for_page_load(driver, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1} to load page: {url}")
            driver.get(url)
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
    return False

def scrape_sensor_data():
    driver = None
    try:
        logger.info("Initializing Chrome WebDriver...")
        driver = setup_chrome_driver()
        url = "https://web.iriseup.ph/sensor_networks"
        logger.info(f"🌍 Fetching data from: {url}")
        if not wait_for_page_load(driver, url):
            raise TimeoutError("Failed to load page after multiple attempts")

        sensor_data = []
        table = driver.find_element(By.CSS_SELECTOR, "table")
        rows = table.find_elements(By.TAG_NAME, "tr")

        # Build header map dynamically
        header_cells = rows[0].find_elements(By.TAG_NAME, "th")
        header_map = {cell.text.strip().lower(): idx for idx, cell in enumerate(header_cells)}
        logger.info(f"Detected table headers: {header_map}")

        for row in rows[1:]:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 1:
                continue

            sensor_name = cols[header_map.get("sensor name", 0)].text.strip()
            current_value = cols[header_map.get("current", 1)].text.strip()
            normal_value = cols[header_map.get("normal", "")].text.strip() if "normal" in header_map else "N/A"
            obs_time = cols[header_map.get("obs time", "")].text.strip() if "obs time" in header_map else "N/A"
            description = cols[header_map.get("description", "")].text.strip() if "description" in header_map else "N/A"

            sensor_data.append({
                "SENSOR NAME": sensor_name,
                "CURRENT": current_value,
                "NORMAL LEVEL": normal_value,
                "OBS TIME": obs_time,
                "DESCRIPTION": description
            })

        if not sensor_data:
            raise ValueError("No sensor data extracted. Check website structure.")

        logger.info(f"✅ Successfully scraped {len(sensor_data)} sensor records")
        save_csv(sensor_data)
        convert_csv_to_json()
        logger.info("✅ Sensor data updated successfully")
    except Exception as e:
        logger.error(f"❌ Scraping Failed: {str(e)}")
        raise
    finally:
        if driver:
            driver.quit()

def save_csv(sensor_data):
    df = pd.DataFrame(sensor_data)
    df.to_csv(CSV_FILE_PATH, index=False)
    print("✅ CSV file saved successfully.")

def convert_csv_to_json():
    df = pd.read_csv(CSV_FILE_PATH)
    categorized_data = {category: [] for category in SENSOR_CATEGORIES}

    for _, row in df.iterrows():
        sensor_name = row["SENSOR NAME"]
        current_value = row["CURRENT"]
        normal_value = row.get("NORMAL LEVEL", "N/A")
        description = row.get("DESCRIPTION", "N/A")

        if sensor_name in SENSOR_CATEGORIES["rain_gauge"]:
            categorized_data["rain_gauge"].append({
                "SENSOR NAME": sensor_name,
                "CURRENT": current_value
            })
        elif sensor_name in SENSOR_CATEGORIES["street_flood_sensors"]:
            categorized_data["street_flood_sensors"].append({
                "SENSOR NAME": sensor_name,
                "CURRENT": current_value,
                "NORMAL LEVEL": normal_value,
                "DESCRIPTION": description
            })
        elif sensor_name in SENSOR_CATEGORIES["flood_risk_index"]:
            categorized_data["flood_risk_index"].append({
                "SENSOR NAME": sensor_name,
                "CURRENT": current_value
            })
        elif sensor_name in SENSOR_CATEGORIES["flood_sensors"]:
            categorized_data["flood_sensors"].append({
                "SENSOR NAME": sensor_name,
                "CURRENT": current_value,
                "NORMAL LEVEL": normal_value,
                "DESCRIPTION": description
            })
        elif sensor_name in SENSOR_CATEGORIES["earthquake_sensors"]:
            categorized_data["earthquake_sensors"].append({
                "SENSOR NAME": sensor_name,
                "CURRENT": current_value
            })

    # Fill missing sensors
    for category, sensors in SENSOR_CATEGORIES.items():
        for sensor_name in sensors:
            if all(sensor["SENSOR NAME"] != sensor_name for sensor in categorized_data[category]):
                default_entry = {"SENSOR NAME": sensor_name, "CURRENT": "0.0" if category == "rain_gauge" else 0.0}
                if category in ["flood_sensors", "street_flood_sensors"]:
                    default_entry["NORMAL LEVEL"] = "N/A"
                    default_entry["DESCRIPTION"] = "N/A"
                categorized_data[category].append(default_entry)

    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(categorized_data, f, indent=4)
    print("✅ JSON data structured correctly.")

@app.get("/api/sensor-data", response_model=Dict[str, List[Dict[str, Any]]])
async def get_sensor_data():
    try:
        with open(SENSOR_DATA_FILE, "r") as f:
            data = json.load(f)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        print("Warning: sensor_data.json not found or invalid, returning empty data.")
        return {key: [] for key in SENSOR_CATEGORIES.keys()}

def start_auto_scraper():
    while True:
        print("🔄 Running data scraper...")
        try:
            scrape_sensor_data()
        except Exception as e:
            logger.error(f"Error in background scraper: {e}")
        print("⏳ Waiting 60 seconds before the next scrape...")
        time.sleep(60)

# Initial scrape on startup
try:
    if not os.path.exists(SENSOR_DATA_FILE):
        print("Sensor data file not found, running initial scrape...")
        scrape_sensor_data()
except Exception as e:
    print(f"Error running initial data scrape: {e}")

# Start background scraper thread
scraper_thread = threading.Thread(target=start_auto_scraper, daemon=True)
scraper_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("SensorDataScraper:app", host="0.0.0.0", port=10000, reload=False)
