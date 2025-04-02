const express = require("express");
const cors = require("cors");
const fs = require("fs");
const puppeteer = require("puppeteer");

const app = express();
const PORT = 5000;

app.use(cors());

const SENSOR_DATA_FILE = "sensor_data.json";

async function scrapeSensorData() {
    console.log("🌍 Fetching data from Streamlit...");
    
    let browser;
    try {
        browser = await puppeteer.launch({
            headless: "new",
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || puppeteer.executablePath(),
            args: ["--no-sandbox", "--disable-setuid-sandbox"]
        });

        const page = await browser.newPage();
        await page.goto("https://app.iriseup.ph/sensor_networks", { waitUntil: "networkidle2" });

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

        if (!sensorData.length) {
            console.error("❌ No sensor data extracted!");
            return;
        }

        console.log("✅ Scraped Data:", sensorData);
        saveJSON(sensorData);

    } catch (error) {
        console.error("❌ Puppeteer failed to launch:", error);
    } finally {
        if (browser) await browser.close();
    }
}

function saveJSON(sensorData) {
    fs.writeFileSync(SENSOR_DATA_FILE, JSON.stringify(sensorData, null, 4));
    console.log("✅ Sensor data saved to JSON.");
}

app.get("/api/sensor-data", (req, res) => {
    if (fs.existsSync(SENSOR_DATA_FILE)) {
        res.sendFile(__dirname + "/" + SENSOR_DATA_FILE);
    } else {
        res.status(404).json({ error: "No data available yet" });
    }
});

setInterval(scrapeSensorData, 60000);

app.listen(PORT, () => {
    console.log(`🚀 Server running at http://127.0.0.1:${PORT}/`);
    scrapeSensorData();
});
