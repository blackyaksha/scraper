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

# === Paths for saving data ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENSOR_DATA_FILE = os.path.join(BASE_DIR, "sensor_data.json")
CSV_FILE_PATH = os.path.join(BASE_DIR, "sensor_data.csv")

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === FastAPI App ===
app = FastAPI(title="Flood Data Scraper API")

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Sensor Categories ===
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

# === Setup Chrome Driver ===
def setup_chrome_driver():
    """Setup Chrome WebDriver with reduced memory usage and system driver"""
    try:
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/chromium"

        # Lightweight headless setup
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--window-size=1920,1080")

        # SSL
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors=yes")

        # ✅ Use system ChromeDriver
        service = Service("/usr/bin/chromedriver")

        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(20)
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
        raise

# === Wait for Page Load ===
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

# === Scraping Logic ===
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
        logger.info(f"✅ Successfully scraped {len(sensor_data)} sensor records")
        save_csv(sensor_data)
        convert_csv_to_json()
        logger.info("✅ Sensor data updated successfully")
    except Exception as e:
        logger.error(f"❌ Scraping Failed: {str(e)}")
        raise
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")

# === Save CSV ===
def save_csv(sensor_data):
    df = pd.DataFrame(sensor_data)
    df.to_csv(CSV_FILE_PATH, index=False)
    print("✅ CSV file saved successfully.")

# === Convert CSV -> JSON ===
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
        if sensor_name in SENSOR_CATEGORIES[category]:
            categorized_data[category].append(sensor_entry)

    for category, sensors in SENSOR_CATEGORIES.items():
        if category not in ["street_flood_sensors", "flood_risk_index"]:
            for sensor_name in sensors:
                matching_sensor = df[df["SENSOR NAME"].str.casefold() == sensor_name.casefold()]
                if not matching_sensor.empty:
                    normal_value = matching_sensor.iloc[0].get("NORMAL LEVEL", "N/A")
                    current_value = matching_sensor.iloc[0]["CURRENT"]
                    description = matching_sensor.iloc[0].get("DESCRIPTION", "N/A")
                    sensor_entry = {"SENSOR NAME": sensor_name, "CURRENT": current_value}
                    if category in ["flood_sensors"]:
                        sensor_entry["NORMAL LEVEL"] = normal_value
                        sensor_entry["DESCRIPTION"] = description
                    categorized_data[category].append(sensor_entry)
                else:
                    sensor_entry = {"SENSOR NAME": sensor_name, "CURRENT": 0.0}
                    if category in ["flood_sensors"]:
                        sensor_entry["NORMAL LEVEL"] = "N/A"
                        sensor_entry["DESCRIPTION"] = "N/A"
                    categorized_data[category].append(sensor_entry)

    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(categorized_data, f, indent=4)
    print("✅ JSON data structured correctly.")

# === FastAPI Routes ===
@app.get("/")
async def root():
    return {"message": "Flood Sensor Scraper API is running 🚀"}

@app.get("/api/sensor-data", response_model=Dict[str, List[Dict[str, Any]]])
async def get_sensor_data():
    try:
        with open(SENSOR_DATA_FILE, "r") as f:
            data = json.load(f)
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        print("⚠️ sensor_data.json not found or invalid, returning empty data.")
        return {key: [] for key in SENSOR_CATEGORIES.keys()}

# === Background Scraper Thread ===
def start_auto_scraper():
    while True:
        print("🔄 Running data scraper...")
        try:
            scrape_sensor_data()
        except Exception as e:
            logger.error(f"Error in background scraper: {e}")
        print("⏳ Waiting 60 seconds before the next scrape...")
        time.sleep(60)

# === Initial Scrape (after functions are defined) ===
try:
    if not os.path.exists(SENSOR_DATA_FILE):
        print("Sensor data file not found, running initial scrape...")
        scrape_sensor_data()
except Exception as e:
    print(f"Error running initial data scrape: {e}")

# === Start background thread ===
scraper_thread = threading.Thread(target=start_auto_scraper, daemon=True)
scraper_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("SensorDataScraper:app", host="0.0.0.0", port=10000, reload=False)
