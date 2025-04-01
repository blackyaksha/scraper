const express = require("express");
const cors = require("cors");
const fs = require("fs");
const puppeteer = require("puppeteer");

const app = express();
const PORT = 5000;

app.use(cors());

const SENSOR_DATA_FILE = "sensor_data.json";

// ✅ Sensor Categories
const SENSOR_CATEGORIES = {
    "rain_gauge": [
        "QCPU", "Masambong", "Batasan Hills", "Ugong Norte", "Ramon Magsaysay HS",
        "UP Village", "Dona Imelda", "Kaligayahan", "Emilio Jacinto Sr HS", "Payatas ES",
        "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit", "Libis",
        "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa",
        "Brgy Fairview (REC)", "Brgy Baesa Hall", "Brgy N.S Amoranto Hall", "Brgy Valencia Hall"
    ],
    "flood_sensors": ["North Fairview", "Batasan-San Mateo", "Bahay Toro", "Sta Cruz", "San Bartolome"],
    "street_flood_sensors": ["N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street", "Christine Street"],
    "flood_risk_index": ["N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street", "Christine Street"],
    "earthquake_sensors": ["QCDRRMO", "QCDRRMO REC"]
};

// ✅ Scrape Data with Puppeteer
async function scrapeSensorData() {
    console.log("🌍 Fetching data from Streamlit...");
    
    const browser = await puppeteer.launch({ headless: true }); // ✅ No pop-up browser
    const page = await browser.newPage();

    await page.goto("https://app.iriseup.ph/sensor_networks", { waitUntil: "networkidle2" });

    console.log("✅ Page Loaded. Waiting for table...");

    try {
        await page.waitForSelector("table tbody", { timeout: 10000 });
    } catch (error) {
        console.error("❌ Table not found! The website may have changed.");
        await browser.close();
        return;
    }

    // ✅ Extract data from table
    const sensorData = await page.evaluate(() => {
        return Array.from(document.querySelectorAll("table tbody tr")).map(row => {
            const cols = row.querySelectorAll("td");
            return {
                "SENSOR NAME": cols[0]?.innerText.trim() || "N/A",
                "OBS TIME": cols[1]?.innerText.trim() || "N/A",
                "NORMAL LEVEL": cols[2]?.innerText.trim() || "N/A",
                "CURRENT": cols[3]?.innerText.trim() || "N/A",
                "DESCRIPTION": cols[4]?.innerText.trim() || "N/A"
            };
        });
    });

    await browser.close();

    if (!sensorData.length) {
        console.error("❌ No sensor data extracted!");
        return;
    }

    console.log("✅ Scraped Data Updated.");
    saveJSON(sensorData);
}

// ✅ Save Scraped Data to JSON (Overwrites)
function saveJSON(sensorData) {
    const categorizedData = {
        rain_gauge: [],
        flood_sensors: [],
        street_flood_sensors: [],
        flood_risk_index: [],
        earthquake_sensors: []
    };

    for (const sensor of sensorData) {
        let category = "flood_risk_index";

        if (sensor["CURRENT"].includes("m")) {
            category = "street_flood_sensors";
        }

        for (const [key, sensors] of Object.entries(SENSOR_CATEGORIES)) {
            if (sensors.includes(sensor["SENSOR NAME"])) {
                category = key;
                break;
            }
        }

        categorizedData[category].push(sensor);
    }

    fs.writeFileSync(SENSOR_DATA_FILE, JSON.stringify(categorizedData, null, 4));
    console.log("✅ Sensor data saved (Overwritten) to JSON.");
}

// ✅ API Route to Get Sensor Data
app.get("/api/sensor-data", (req, res) => {
    if (fs.existsSync(SENSOR_DATA_FILE)) {
        res.sendFile(__dirname + "/" + SENSOR_DATA_FILE);
    } else {
        res.status(404).json({ error: "No data available yet" });
    }
});

// ✅ Auto Scrape Every 60 Seconds (Continuously Updates JSON)
setInterval(scrapeSensorData, 60000);

// ✅ Start Express Server
app.listen(PORT, () => {
    console.log(`🚀 Server running at http://127.0.0.1:${PORT}/`);
    scrapeSensorData(); // ✅ Start immediately
});