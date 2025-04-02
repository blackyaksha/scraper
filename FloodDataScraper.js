const express = require("express");
const cors = require("cors");
const fs = require("fs");
const puppeteer = require("puppeteer");

const app = express();
const PORT = 5000;

app.use(cors());

const SENSOR_DATA_FILE = "sensor_data.json";

// Function to scrape sensor data
async function scrapeSensorData() {
    console.log("🌍 Fetching data from Streamlit...");

    let browser;
    try {
        // Launch Puppeteer with custom executable path and cache configuration
        browser = await puppeteer.launch({
            headless: "new", // Running in headless mode
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || puppeteer.executablePath(), // Allow environment override
            args: ["--no-sandbox", "--disable-setuid-sandbox"], // Security settings for headless environment
            userDataDir: './.puppeteer_data', // Custom data directory for user data (caching etc.)
        });

        const page = await browser.newPage();
        await page.goto("https://app.iriseup.ph/sensor_networks", { waitUntil: "networkidle2" });

        // Extract sensor data from the page
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
        saveJSON(sensorData);  // Save the data to a file

    } catch (error) {
        console.error("❌ Puppeteer failed to launch:", error);
    } finally {
        if (browser) await browser.close();  // Ensure browser is closed after scraping
    }
}

// Save scraped data to a JSON file
function saveJSON(sensorData) {
    fs.writeFileSync(SENSOR_DATA_FILE, JSON.stringify(sensorData, null, 4));  // Overwrite file with new data
    console.log("✅ Sensor data saved to JSON.");
}

// API route to serve sensor data as a file
app.get("/api/sensor-data", (req, res) => {
    if (fs.existsSync(SENSOR_DATA_FILE)) {
        res.sendFile(__dirname + "/" + SENSOR_DATA_FILE);
    } else {
        res.status(404).json({ error: "No data available yet" });
    }
});

// Run the scraper every 60 seconds
setInterval(scrapeSensorData, 60000);

// Start Express server and initial scraping
app.listen(PORT, () => {
    console.log(`🚀 Server running at http://127.0.0.1:${PORT}/`);
    scrapeSensorData();  // Initial scrape on startup
});
