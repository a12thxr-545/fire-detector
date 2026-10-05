// =========================================================
// AI FIRE DETECTOR DASHBOARD CONTROL SCRIPT
// =========================================================

let sensorChart = null;
let firstChartLoad = true;

// =========================================================
// ELEMENT HELPER
// =========================================================

function get(id) {
    return document.getElementById(id);
}

// =========================================================
// ESCAPE HTML
// =========================================================

function escapeHTML(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// =========================================================
// THEME MANAGER
// =========================================================

function initTheme() {
    const savedTheme = localStorage.getItem("theme") || 
        (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    
    setTheme(savedTheme, false);

    const toggleBtn = get("themeToggleBtn");
    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
            const newTheme = currentTheme === "dark" ? "light" : "dark";
            setTheme(newTheme, true);
        });
    }

    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
        if (!localStorage.getItem("theme")) {
            setTheme(e.matches ? "dark" : "light", true);
        }
    });
}

function setTheme(theme, updateChart = true) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);

    if (updateChart && sensorChart) {
        updateChartThemeColors();
    }
}

function getChartThemeColors() {
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    return {
        textColor: isLight ? "#475569" : "#94a3b8",
        gridColor: isLight ? "rgba(0, 0, 0, 0.05)" : "rgba(255, 255, 255, 0.05)",
        tempColor: isLight ? "#0891b2" : "#06b6d4",
        legendColor: isLight ? "#334155" : "#d1d5db"
    };
}

function updateChartThemeColors() {
    if (!sensorChart) return;
    const colors = getChartThemeColors();
    const isSmall = window.innerWidth < 640;

    sensorChart.options.scales.x.ticks.color = colors.textColor;
    sensorChart.options.scales.x.ticks.maxTicksLimit = isSmall ? 4 : 8;
    sensorChart.options.scales.x.grid.color = colors.gridColor;

    sensorChart.options.scales.temperature.ticks.color = colors.tempColor;
    sensorChart.options.scales.temperature.title.color = colors.tempColor;
    sensorChart.options.scales.temperature.title.display = !isSmall;
    sensorChart.options.scales.temperature.grid.color = colors.gridColor;

    sensorChart.options.scales.percentage.ticks.color = colors.textColor;
    sensorChart.options.scales.percentage.title.color = colors.textColor;
    sensorChart.options.scales.percentage.title.display = !isSmall;

    sensorChart.options.plugins.legend.labels.color = colors.legendColor;

    sensorChart.update();
}

// =========================================================
// INIT GRAPH
// =========================================================

function initSensorChart() {
    const canvas = get("sensorChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const colors = getChartThemeColors();
    const isSmall = window.innerWidth < 640;

    sensorChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Temp °C",
                    data: [],
                    borderColor: "#06b6d4",
                    backgroundColor: "rgba(6, 182, 212, 0.1)",
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: true,
                    yAxisID: "temperature"
                },
                {
                    label: "Gas %",
                    data: [],
                    borderColor: "#f59e0b",
                    backgroundColor: "rgba(245, 158, 11, 0.05)",
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: false,
                    yAxisID: "percentage"
                },
                {
                    label: "Risk %",
                    data: [],
                    borderColor: "#ef4444",
                    backgroundColor: "rgba(239, 68, 68, 0.1)",
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: false,
                    yAxisID: "percentage"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            layout: {
                padding: {
                    left: 0,
                    right: 4,
                    top: 4,
                    bottom: 0
                }
            },
            interaction: {
                intersect: false,
                mode: "index"
            },
            scales: {
                x: {
                    grid: {
                        color: colors.gridColor
                    },
                    ticks: {
                        color: colors.textColor,
                        font: { family: "Plus Jakarta Sans", size: isSmall ? 10 : 11 },
                        maxTicksLimit: isSmall ? 4 : 8
                    }
                },
                temperature: {
                    type: "linear",
                    position: "left",
                    grid: {
                        color: colors.gridColor
                    },
                    ticks: {
                        color: colors.tempColor,
                        font: { family: "JetBrains Mono", size: isSmall ? 10 : 11 }
                    },
                    title: {
                        display: !isSmall,
                        text: "Temp °C",
                        color: colors.tempColor,
                        font: { family: "Plus Jakarta Sans", size: 11, weight: "bold" }
                    }
                },
                percentage: {
                    type: "linear",
                    position: "right",
                    min: 0,
                    max: 100,
                    grid: {
                        drawOnChartArea: false
                    },
                    ticks: {
                        color: colors.textColor,
                        font: { family: "JetBrains Mono", size: isSmall ? 10 : 11 }
                    },
                    title: {
                        display: !isSmall,
                        text: "Gas / Risk %",
                        color: colors.textColor,
                        font: { family: "Plus Jakarta Sans", size: 11, weight: "bold" }
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: "top",
                    labels: {
                        color: colors.legendColor,
                        font: { family: "Plus Jakarta Sans", size: isSmall ? 11 : 12, weight: "600" },
                        usePointStyle: true,
                        boxWidth: 6,
                        padding: isSmall ? 8 : 12
                    }
                }
            }
        }
    });
}

// =========================================================
// UPDATE GRAPH
// =========================================================

async function updateSensorChart() {
    try {
        const response = await fetch("/api/history", { cache: "no-store" });
        if (!response.ok) {
            throw new Error("History API error");
        }

        const history = await response.json();

        if (!sensorChart) {
            initSensorChart();
        }

        if (!sensorChart) return;

        sensorChart.data.labels = history.map(item => item.time);
        sensorChart.data.datasets[0].data = history.map(item => item.temperature);
        sensorChart.data.datasets[1].data = history.map(item => item.gas);
        sensorChart.data.datasets[2].data = history.map(item => item.risk);

        sensorChart.update("none");

        const graphStatus = get("graphStatus");
        if (graphStatus) {
            graphStatus.textContent = "LIVE";
            graphStatus.className = "graph-status live";
        }

        firstChartLoad = false;
    } catch (error) {
        console.error("Graph error:", error);

        const graphStatus = get("graphStatus");
        if (graphStatus) {
            graphStatus.textContent = "OFFLINE";
            graphStatus.className = "graph-status offline";
        }
    }
}

// =========================================================
// UPDATE DASHBOARD
// =========================================================

async function updateDashboard() {
    try {
        const response = await fetch("/api/data", { cache: "no-store" });
        if (!response.ok) {
            throw new Error("API error");
        }

        const data = await response.json();

        // CONNECTION
        const dot = get("connectionDot");
        const text = get("connectionText");
        if (dot) dot.classList.add("connected");
        if (text) text.textContent = "Connected";

        // ROOM
        if (get("room")) {
            get("room").textContent = data.room || "warehouse";
        }

        // TEMPERATURE
        if (get("temperature")) {
            get("temperature").textContent = `${Number(data.temperature || 0).toFixed(2)}°C`;
        }

        // TEMP RISK
        if (get("tempRisk")) {
            get("tempRisk").textContent = `Temp Risk: ${Number(data.tempRisk || 0).toFixed(2)}%`;
        }

        // TODAY TEMP RANGE (DAILY DB)
        if (data.todayTemp) {
            if (get("todayMaxTemp")) {
                get("todayMaxTemp").textContent = `${Number(data.todayTemp.maxTemp || 0).toFixed(2)}°C`;
            }
            if (get("todayMaxTime")) {
                get("todayMaxTime").textContent = data.todayTemp.maxTempTime || "--:--";
            }
            if (get("todayMinTemp")) {
                get("todayMinTemp").textContent = `${Number(data.todayTemp.minTemp || 0).toFixed(2)}°C`;
            }
            if (get("todayMinTime")) {
                get("todayMinTime").textContent = data.todayTemp.minTempTime || "--:--";
            }
        }

        // HUMIDITY
        if (get("humidity")) {
            get("humidity").textContent = `${Number(data.humidity || 0).toFixed(2)}%`;
        }

        // GAS
        if (get("gas")) {
            get("gas").textContent = `${Number(data.gas || 0).toFixed(2)}%`;
        }

        // GAS RISK
        if (get("gasRisk")) {
            get("gasRisk").textContent = `Gas Risk: ${Number(data.gasRisk || 0).toFixed(2)}%`;
        }

        // RISK
        if (get("risk")) {
            get("risk").textContent = `${Number(data.risk || 0).toFixed(2)}%`;
            const riskBar = get("riskProgressBar");
            if (riskBar) {
                const riskVal = Math.min(Math.max(data.risk || 0, 0), 100);
                riskBar.style.width = `${riskVal}%`;

                if (riskVal > 60) {
                    riskBar.style.backgroundColor = "var(--status-danger)";
                } else if (riskVal > 25) {
                    riskBar.style.backgroundColor = "var(--status-warning)";
                } else {
                    riskBar.style.backgroundColor = "var(--status-normal)";
                }
            }
        }

        // STATUS
        const statusElement = get("status");
        if (statusElement) {
            const status = data.status || "NORMAL";
            statusElement.className = "status";

            if (status === "HIGH RISK") {
                statusElement.classList.add("high-risk");
                statusElement.textContent = "HIGH RISK";
            } else if (status === "MODERATE") {
                statusElement.classList.add("moderate");
                statusElement.textContent = "MODERATE";
            } else {
                statusElement.classList.add("normal");
                statusElement.textContent = "NORMAL";
            }
        }

        // CAMERA & STREAM
        const cameraOn = Boolean(data.camera);
        const streamOn = Boolean(data.streamActive);

        if (get("camera")) {
            get("camera").textContent = cameraOn ? "ON" : "OFF";
        }

        if (get("stream")) {
            get("stream").textContent = streamOn ? "Stream ON" : "Stream OFF";
        }

        // CAMERA BADGE
        const cameraBadge = get("cameraBadge");
        if (cameraBadge) {
            cameraBadge.className = "badge";
            if (cameraOn) {
                cameraBadge.classList.add("on");
                cameraBadge.textContent = "ON";
            } else {
                cameraBadge.classList.add("off");
                cameraBadge.textContent = "OFF";
            }
        }

        // CAMERA STREAM VIEWPORT
        const image = get("cameraStream");
        const offline = get("cameraOffline");

        if (image && offline) {
            if (streamOn) {
                if (!image.src || !image.src.includes("/camera-stream")) {
                    image.src = "/camera-stream";
                }
                image.style.display = "block";
                offline.style.display = "none";
            } else {
                image.style.display = "none";
                image.src = "";
                offline.style.display = "flex";
            }
        }

        // YOLO AI
        updateYOLO(data.yolo);

        // LAST UPDATE & SYSTEM
        if (get("lastUpdate")) {
            get("lastUpdate").textContent = data.lastUpdate || "-";
        }

        if (get("mqttStatus")) {
            get("mqttStatus").textContent = "Connected";
        }

    } catch (error) {
        console.error("Dashboard error:", error);

        const dot = get("connectionDot");
        const text = get("connectionText");

        if (dot) dot.classList.remove("connected");
        if (text) text.textContent = "Disconnected";
        if (get("mqttStatus")) get("mqttStatus").textContent = "Disconnected";
    }
}

// =========================================================
// UPDATE YOLO
// =========================================================

function updateYOLO(yolo) {
    const status = get("yoloStatus");
    const container = get("yoloDetection");

    if (!yolo) return;

    const fire = Boolean(yolo.fire);
    const smoke = Boolean(yolo.smoke);

    if (status) {
        status.className = "badge";
        if (fire) {
            status.classList.add("danger");
            status.textContent = "FIRE";
        } else if (smoke) {
            status.classList.add("warning");
            status.textContent = "SMOKE";
        } else {
            status.classList.add("off");
            status.textContent = "STANDBY";
        }
    }

    if (!container) return;

    const detections = Array.isArray(yolo.detections) ? yolo.detections : [];

    if (detections.length === 0) {
        container.innerHTML = `
            <div class="yolo-normal">
                <span class="dot-green"></span>
                <span>No fire or smoke detected</span>
            </div>
        `;
        return;
    }

    let html = "";
    detections.forEach(detection => {
        const className = escapeHTML(detection.class);
        const confidence = Number(detection.confidence || 0);

        html += `
            <div class="detection-item">
                <div class="detection-name">${className}</div>
                <div class="detection-confidence">Confidence: ${confidence.toFixed(2)}%</div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// =========================================================
// START & RESIZE LISTENERS
// =========================================================

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initSensorChart();
    updateDashboard();
    updateSensorChart();

    setInterval(updateDashboard, 300);
    setInterval(updateSensorChart, 500);

    let resizeTimer;
    window.addEventListener("resize", () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (sensorChart) {
                updateChartThemeColors();
            }
        }, 200);
    });
});