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

// Function to scrape sensor data with retry mechanism
async function scrapeSensorData(attempts = 3) {
    console.log("🌍 Fetching data from Streamlit...");

    let browser;
    try {
        browser = await puppeteer.launch({
            headless: "new", // Change to false for debugging
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || puppeteer.executablePath(),
            args: ["--no-sandbox", "--disable-setuid-sandbox"],
            userDataDir: './.puppeteer_data'
        });

        const page = await browser.newPage();

        // Retry logic
        for (let i = 0; i < attempts; i++) {
            try {
                await page.goto("https://app.iriseup.ph/sensor_networks", { 
                    waitUntil: "networkidle2",
                    timeout: 60000 // Increased timeout to 60s
                });
                break; // Success, exit loop
            } catch (error) {
                console.warn(`⚠️ Retry attempt (${i + 1}/${attempts}) due to timeout.`);
                if (i === attempts - 1) throw error; // Fail after last attempt
            }
        }

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
        console.error("❌ Puppeteer failed:", error);
    } finally {
        if (browser) await browser.close();  // Ensure browser is closed after scraping
    }
}

// Save scraped data to a JSON file
function saveJSON(sensorData) {
    fs.writeFileSync(SENSOR_DATA_FILE, JSON.stringify(sensorData, null, 4));
    console.log("✅ Sensor data saved to JSON.");
}

// API route to serve sensor data
app.get("/api/sensor-data", (req, res) => {
    if (fs.existsSync(SENSOR_DATA_FILE)) {
        res.sendFile(__dirname + "/" + SENSOR_DATA_FILE);
    } else {
        res.status(404).json({ error: "No data available yet" });
    }
});

// Run the scraper every 60 seconds
setInterval(() => scrapeSensorData(), 60000);

// Start Express server and initial scraping
app.listen(PORT, () => {
    console.log(`🚀 Server running at http://127.0.0.1:${PORT}/`);
    scrapeSensorData();  // Initial scrape on startup
});
