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
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, List, Any
import logging
import os

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SENSOR_DATA_FILE = os.path.join(BASE_DIR, "sensor_data.json")
CSV_FILE_PATH = os.path.join(BASE_DIR, "sensor_data.csv")

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Flood Data Scraper API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SENSOR_CATEGORIES = {
    "rain_gauge": ["QCPU", "Masambong", "Batasan Hills", "Ugong Norte"],
    "flood_sensors": ["North Fairview", "Batasan-San Mateo", "Bahay Toro"],
    "street_flood_sensors": ["N.S. Amoranto Street", "New Greenland"],
    "flood_risk_index": ["N.S. Amoranto Street", "New Greenland"],
    "earthquake_sensors": ["QCDRRMO", "QCDRRMO REC"]
}

# ✅ Optimized Chrome setup
def setup_chrome_driver():
    """Setup Chrome WebDriver with reduced memory usage"""
    try:
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/chromium"

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

        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors=yes")
        chrome_options.add_argument("--allow-insecure-localhost")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(20)
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Chrome WebDriver: {str(e)}")
        raise

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
            raise TimeoutError("Failed to load page")

        sensor_data = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
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
            raise ValueError("No sensor data extracted.")

        logger.info(f"✅ Scraped {len(sensor_data)} sensor records")
        save_csv(sensor_data)
        convert_csv_to_json()
    except Exception as e:
        logger.error(f"❌ Scraping Failed: {str(e)}")
        raise
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing WebDriver: {str(e)}")

def save_csv(sensor_data):
    pd.DataFrame(sensor_data).to_csv(CSV_FILE_PATH, index=False)
    logger.info("✅ CSV saved")

def convert_csv_to_json():
    df = pd.read_csv(CSV_FILE_PATH)
    categorized_data = {category: [] for category in SENSOR_CATEGORIES}
    for _, row in df.iterrows():
        sensor_name = row["SENSOR NAME"]
        current_value = row["CURRENT"]
        categorized_data["flood_risk_index"].append({
            "SENSOR NAME": sensor_name,
            "CURRENT": current_value,
        })
    with open(SENSOR_DATA_FILE, "w") as f:
        json.dump(categorized_data, f, indent=4)
    logger.info("✅ JSON saved")

@app.get("/api/sensor-data", response_model=Dict[str, List[Dict[str, Any]]])
async def get_sensor_data():
    try:
        with open(SENSOR_DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {key: [] for key in SENSOR_CATEGORIES.keys()}

# ✅ Ensure JSON exists *after* functions
try:
    if not os.path.exists(SENSOR_DATA_FILE):
        print("Sensor data file not found, running initial scrape...")
        scrape_sensor_data()
except Exception as e:
    print(f"Error running initial data scrape: {e}")

def start_auto_scraper():
    while True:
        print("🔄 Running data scraper...")
        try:
            scrape_sensor_data()
        except Exception as e:
            logger.error(f"Error in background scraper: {e}")
        print("⏳ Waiting 60 seconds...")
        time.sleep(60)

scraper_thread = threading.Thread(target=start_auto_scraper, daemon=True)
scraper_thread.start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("SensorDataScraper:app", host="0.0.0.0", port=10000, reload=False)
