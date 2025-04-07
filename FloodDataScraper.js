const express = require("express");
const cors = require("cors");
const fs = require("fs");
const puppeteer = require("puppeteer");

const app = express();
const PORT = 5000;

app.use(cors());

const { createClient } = require("@supabase/supabase-js");

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY; // Or anon key (less secure for writing)
const supabase = createClient(supabaseUrl, supabaseKey);

const SENSOR_DATA_FILE = "sensor_data.json";

// ✅ In-memory variable to store sensor data
let latestSensorData = [];

// ✅ Sensor Categories
const SENSOR_CATEGORIES = {
    rain_gauge: [
        "QCPU", "Masambong", "Batasan Hills", "Ugong Norte", "Ramon Magsaysay HS",
        "UP Village", "Dona Imelda", "Kaligayahan", "Emilio Jacinto Sr HS", "Payatas ES",
        "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit", "Libis",
        "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa", 
        "Balingasa High School", "Toro Hills Elementary School",
        "Quezon City University San Francisco Campus", "Maharlika Brgy Hall", "Bagong Silangan Evacuation Center",
        "Dona Juana Elementary School", "Quirino High School",
        "Old Balara Elementary School", "Pansol Kaingin 1 Brgy Satellite Office",
        "Jose P Laurel Senior High School", "Pinyahan Multipurose Hall", "Sikatuna Brgy Hall",
        "Kalusugan Brgy Hall", "Laging Handa Barangay Hall", "Amoranto Sport Complex",
        "Maligaya High School", "San Agustin Brgy Hall", "Jose Maria Panganiban Senior High School",
        "North Fairview Elementary School", "Sauyo Elementary School", "New Era Brgy Hall", "Ismael Mathay Senior High School",
        "Brgy Fairview (REC)", "Brgy Baesa Hall", "Brgy N.S Amoranto Hall", "Brgy Valencia Hall"
    ],
    flood_sensors: [
        "North Fairview", "Batasan-San Mateo", "Bahay Toro", "Sta Cruz", "San Bartolome"
    ],
    street_flood_sensors: [
        "N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street",
        "Christine Street", "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit",
        "Libis", "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa"
    ],
    flood_risk_index: [
        "N.S. Amoranto Street", "New Greenland", "Kalantiaw Street", "F. Calderon Street",
        "Christine Street", "Ramon Magsaysay Brgy Hall", "Phil-Am", "Holy Spirit",
        "Libis", "South Triangle", "Nagkaisang Nayon", "Tandang Sora", "Talipapa"
    ],
    earthquake_sensors: ["QCDRRMO", "QCDRRMO REC"]
};

// 🕷️ Scrape sensor data
async function scrapeSensorData(attempts = 3) {
    console.log("🌍 Fetching data from Streamlit...");

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: "new",
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || puppeteer.executablePath(),
            args: ["--no-sandbox", "--disable-setuid-sandbox"],
            userDataDir: './.puppeteer_data'
        });

        const page = await browser.newPage();

        for (let i = 0; i < attempts; i++) {
            try {
                await page.goto("https://app.iriseup.ph/sensor_networks", {
                    waitUntil: "networkidle2",
                    timeout: 60000
                });
                break;
            } catch (error) {
                console.warn(`⚠️ Retry attempt (${i + 1}/${attempts}) due to timeout.`);
                if (i === attempts - 1) throw error;
            }
        }

        const sensorData = await page.evaluate(() => {
            return Array.from(document.querySelectorAll("table tbody tr")).map(row => {
                const cols = row.querySelectorAll("td");
                return {
                    "SENSOR NAME": cols[0]?.innerText.trim() || "N/A",
                    "OBS TIME": cols[1]?.innerText.trim() || "N/A",
                    "NORMAL LEVEL": cols[2]?.innerText.trim() || "N/A",
                    "CURRENT": cols[3]?.innerText.trim() || "N/A",
                    "DESCRIPTION": cols[4]?.innerText.trim() || "N/A",
                };
            });
        });

        if (!sensorData.length) {
            console.error("❌ No sensor data extracted!");
            return;
        }

        console.log("✅ Scraped Data:", sensorData);
        saveToMemory(sensorData);  // ✅ Store in memory instead of file

    } catch (error) {
        console.error("❌ Puppeteer failed:", error);
    } finally {
        if (browser) await browser.close();
    }
}

// ✅ Store data in memory
async function saveToMemory(sensorData) {
    latestSensorData = sensorData;
    console.log("✅ Sensor data stored in memory.");

    // Insert to Supabase
    try {
        const { data, error } = await supabase
            .from("sensor_data")
            .insert(sensorData.map(item => ({
                sensor_name: item["SENSOR NAME"],
                obs_time: item["OBS TIME"],
                normal_level: item["NORMAL LEVEL"],
                current: item["CURRENT"],
                description: item["DESCRIPTION"]
            })));

        if (error) {
            console.error("❌ Supabase insert error:", error);
        } else {
            console.log(`✅ ${data.length} records inserted to Supabase.`);
        }
    } catch (err) {
        console.error("❌ Supabase error:", err);
    }
}

// ✅ API route that returns in-memory sensor data
app.get("/api/sensor-data", (req, res) => {
    if (latestSensorData.length > 0) {
        res.json(latestSensorData);
    } else {
        res.status(404).json({ error: "No data available yet" });
    }
});

// 🔁 Run scraper every 60s
setInterval(() => scrapeSensorData(), 60000);

// 🚀 Start server
app.listen(PORT, () => {
    console.log(`🚀 Server running at http://127.0.0.1:${PORT}/`);
    scrapeSensorData(); // Initial scrape
});
