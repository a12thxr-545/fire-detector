import os
import json
import time
import threading
import hashlib
import hmac
import base64
import sqlite3
from collections import deque

import cv2
import numpy as np
import requests
import paho.mqtt.client as mqtt

from flask import Flask, Response, jsonify, request, render_template
from ultralytics import YOLO


# =========================================================
# DATABASE CONFIG & HELPERS (Daily Temp Max/Min)
# =========================================================

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
db_lock = threading.Lock()


def init_db():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_temperatures (
                    date TEXT PRIMARY KEY,
                    max_temp REAL NOT NULL,
                    max_temp_time TEXT NOT NULL,
                    min_temp REAL NOT NULL,
                    min_temp_time TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            print(f"[DB] Initialized SQLite database: {DB_PATH}")
        except Exception as e:
            print(f"[ERROR] DB init error: {e}")


def update_daily_temperature(temperature):
    date_str = time.strftime("%Y-%m-%d")
    time_str = time.strftime("%H:%M:%S")
    timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT max_temp, max_temp_time, min_temp, min_temp_time "
                "FROM daily_temperatures WHERE date = ?",
                (date_str,)
            )
            row = cursor.fetchone()

            if row is None:
                cursor.execute("""
                    INSERT INTO daily_temperatures (
                        date, max_temp, max_temp_time, min_temp, min_temp_time, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    date_str, temperature, time_str, temperature, time_str, timestamp_str
                ))
                conn.commit()
                max_t, max_t_time = temperature, time_str
                min_t, min_t_time = temperature, time_str
            else:
                current_max, current_max_time, current_min, current_min_time = row
                max_t = current_max
                max_t_time = current_max_time
                min_t = current_min
                min_t_time = current_min_time
                updated = False

                if temperature > current_max:
                    max_t = temperature
                    max_t_time = time_str
                    updated = True

                if temperature < current_min:
                    min_t = temperature
                    min_t_time = time_str
                    updated = True

                if updated:
                    cursor.execute("""
                        UPDATE daily_temperatures
                        SET max_temp = ?, max_temp_time = ?, min_temp = ?, min_temp_time = ?, updated_at = ?
                        WHERE date = ?
                    """, (
                        max_t, max_t_time, min_t, min_t_time, timestamp_str, date_str
                    ))
                    conn.commit()

            conn.close()

            return {
                "date": date_str,
                "maxTemp": max_t,
                "maxTempTime": max_t_time,
                "minTemp": min_t,
                "minTempTime": min_t_time
            }
        except Exception as e:
            print(f"[ERROR] DB update daily temp error: {e}")
            return None


def get_today_temperature():
    date_str = time.strftime("%Y-%m-%d")
    with db_lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT max_temp, max_temp_time, min_temp, min_temp_time "
                "FROM daily_temperatures WHERE date = ?",
                (date_str,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "date": date_str,
                    "maxTemp": row[0],
                    "maxTempTime": row[1],
                    "minTemp": row[2],
                    "minTempTime": row[3]
                }
        except Exception as e:
            print(f"[ERROR] DB fetch today error: {e}")

    return {
        "date": date_str,
        "maxTemp": 0.0,
        "maxTempTime": "-",
        "minTemp": 0.0,
        "minTempTime": "-"
    }


def get_all_daily_temperatures():
    with db_lock:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date, max_temp, max_temp_time, min_temp, min_temp_time, updated_at "
                "FROM daily_temperatures ORDER BY date DESC"
            )
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "date": r[0],
                    "maxTemp": r[1],
                    "maxTempTime": r[2],
                    "minTemp": r[3],
                    "minTempTime": r[4],
                    "updatedAt": r[5]
                }
                for r in rows
            ]
        except Exception as e:
            print(f"[ERROR] DB fetch all error: {e}")
            return []


# =========================================================
# CONFIG
# =========================================================

CAMERA_IP = "192.168.1.160"

CAMERA_STREAM_URL = f"http://{CAMERA_IP}/stream"
CAMERA_ON_URL = f"http://{CAMERA_IP}/camera/on"
CAMERA_OFF_URL = f"http://{CAMERA_IP}/camera/off"

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "firemonitor/sensor"

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5001

LOCALHOST_URL = f"http://localhost:{FLASK_PORT}"
PUBLIC_NGROK_URL = "https://your-ngrok-url.ngrok-free.app"  # แก้ไขเป็น URL ของ ngrok หรือ Cloudflare Tunnel
DASHBOARD_URL = LOCALHOST_URL

TEMP_CAMERA_TRIGGER = 29.5
RISK_LINE_ALERT_THRESHOLD = 50.0

MQ_ACTIVE_LOW = True


# =========================================================
# RISK MODEL
# =========================================================

TEMP_RISK_START = 25.0
TEMP_RISK_MAX_TEMP = 40.0
TEMP_RISK_MAX_SCORE = 60.0

GAS_RISK_SCORE = 40.0


def calculate_risk(temperature, gas_detected):

    if temperature <= TEMP_RISK_START:

        temp_risk = 0.0

    elif temperature >= TEMP_RISK_MAX_TEMP:

        temp_risk = TEMP_RISK_MAX_SCORE

    else:

        temp_risk = (
            (temperature - TEMP_RISK_START)
            / (TEMP_RISK_MAX_TEMP - TEMP_RISK_START)
        ) * TEMP_RISK_MAX_SCORE

    gas_risk = GAS_RISK_SCORE if gas_detected else 0.0

    risk = min(
        max(temp_risk + gas_risk, 0.0),
        100.0
    )

    return (
        round(risk, 2),
        round(temp_risk, 2),
        round(gas_risk, 2)
    )


# =========================================================
# YOLO CONFIG
# =========================================================

MODEL_FILE = "best.pt"

YOLO_CONFIDENCE = 0.35
YOLO_ALERT_CONFIDENCE = 0.50
YOLO_IMAGE_SIZE = 416
YOLO_EVERY_N_FRAMES = 1

STREAM_JPEG_QUALITY = 75

YOLO_ALERT_COOLDOWN = 60


# =========================================================
# LINE CONFIG
# =========================================================

LINE_CHANNEL_ACCESS_TOKEN = os.getenv(
    "LINE_CHANNEL_ACCESS_TOKEN",
    ""
)

LINE_CHANNEL_SECRET = os.getenv(
    "LINE_CHANNEL_SECRET",
    ""
)

LINE_USERS_FILE = "line_users.json"

LINE_REPLY_URL = (
    "https://api.line.me/v2/bot/message/reply"
)

LINE_PUSH_URL = (
    "https://api.line.me/v2/bot/message/push"
)


# =========================================================
# FLASK
# =========================================================

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)


# =========================================================
# GLOBAL DATA
# =========================================================

data_lock = threading.Lock()

latest_data = {
    "room": "warehouse",

    "temperature": 0.0,
    "humidity": 0.0,

    "gasRaw": 0,
    "gas": 0.0,
    "gasDetected": False,

    "risk": 0.0,
    "tempRisk": 0.0,
    "gasRisk": 0.0,

    "status": "NORMAL",

    "camera": False,
    "streamActive": False,

    "yolo": {
        "fire": False,
        "smoke": False,
        "detections": []
    },

    "todayTemp": {
        "date": "-",
        "maxTemp": 0.0,
        "maxTempTime": "-",
        "minTemp": 0.0,
        "minTempTime": "-"
    },

    "lastUpdate": "-"
}


# =========================================================
# GRAPH HISTORY
# =========================================================

history = deque(maxlen=60)


# =========================================================
# CAMERA STATE
# =========================================================

camera_lock = threading.Lock()

camera_running = False
stream_thread = None
yolo_thread = None

latest_raw_frame = None
latest_annotated_frame = None
latest_frame_lock = threading.Lock()

yolo_detections = []

last_yolo_alert_time = 0


# =========================================================
# RISK ALERT STATE
# =========================================================

previous_risk_above_50 = False


# =========================================================
# YOLO MODEL
# =========================================================

model = None

try:

    if os.path.exists(MODEL_FILE):

        model = YOLO(MODEL_FILE)

        print(
            f"[OK] YOLO Model Loaded: {MODEL_FILE}"
        )

    else:

        print(
            f"[WARN] YOLO model not found: {MODEL_FILE}"
        )

except Exception as e:

    print(
        f"[ERROR] YOLO model load failed: {e}"
    )


# =========================================================
# LINE USER FUNCTIONS
# =========================================================

def load_line_users():

    if not os.path.exists(LINE_USERS_FILE):

        return []

    try:

        with open(
            LINE_USERS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            users = data

        elif isinstance(data, dict):

            users = data.get(
                "users",
                []
            )

        else:

            users = []

        result = []

        seen = set()

        for user in users:

            if not isinstance(user, dict):

                continue

            user_id = user.get("userId")

            if user_id and user_id not in seen:

                result.append(user)

                seen.add(user_id)

        return result

    except Exception as e:

        print(
            f"[ERROR] Load LINE users error: {e}"
        )

        return []


def save_line_user(source):

    if not isinstance(source, dict):

        return

    user_id = source.get("userId")

    if not user_id:

        return

    users = load_line_users()

    for user in users:

        if user.get("userId") == user_id:

            return

    users.append({
        "userId": user_id,
        "groupId": source.get("groupId"),
        "roomId": source.get("roomId")
    })

    try:

        with open(
            LINE_USERS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                users,
                f,
                ensure_ascii=False,
                indent=2
            )

        print(
            f"[OK] LINE user saved: {user_id}"
        )

    except Exception as e:

        print(
            f"[ERROR] Save LINE user error: {e}"
        )


def remove_line_user(user_id):

    if not user_id:

        return

    users = load_line_users()

    users = [
        user
        for user in users
        if user.get("userId") != user_id
    ]

    try:

        with open(
            LINE_USERS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                users,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:

        print(
            f"[ERROR] Remove LINE user error: {e}"
        )


# =========================================================
# LINE REPLY
# =========================================================

def line_reply(reply_token, text):

    if not LINE_CHANNEL_ACCESS_TOKEN:

        print(
            "[WARN] LINE access token not configured"
        )

        return False

    headers = {
        "Authorization":
            f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",

        "Content-Type":
            "application/json"
    }

    payload = {
        "replyToken": reply_token,

        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    try:

        response = requests.post(
            LINE_REPLY_URL,
            headers=headers,
            json=payload,
            timeout=10
        )

        if response.status_code != 200:

            print(
                f"[ERROR] LINE Reply Error: "
                f"{response.status_code}"
            )

            print(response.text)

            return False

        return True

    except Exception as e:

        print(
            f"[ERROR] LINE Reply Exception: {e}"
        )

        return False


# =========================================================
# LINE PUSH
# =========================================================

def send_line_push(text):

    if not LINE_CHANNEL_ACCESS_TOKEN:

        print(
            "[WARN] LINE access token not configured"
        )

        return False

    users = load_line_users()

    if not users:

        print(
            "[WARN] No LINE users"
        )

        return False

    headers = {
        "Authorization":
            f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",

        "Content-Type":
            "application/json"
    }

    success = False

    for user in users:

        user_id = user.get("userId")

        if not user_id:

            continue

        payload = {
            "to": user_id,

            "messages": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }

        try:

            response = requests.post(
                LINE_PUSH_URL,
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:

                success = True

                print(
                    f"[OK] LINE Push sent: {user_id}"
                )

            else:

                print(
                    f"[ERROR] LINE Push Error "
                    f"{response.status_code}: "
                    f"{response.text}"
                )

        except Exception as e:

            print(
                f"[ERROR] LINE Push Exception: {e}"
            )

    return success


# =========================================================
# LINE STATUS MESSAGE
# =========================================================

def build_status_message():

    with data_lock:

        data = dict(latest_data)

        yolo = dict(
            latest_data.get(
                "yolo",
                {}
            )
        )

    status = data["status"]

    gas_text = (
        "ตรวจพบ"
        if data["gasDetected"]
        else
        "ปกติ"
    )

    camera_text = (
        "ON"
        if data["camera"]
        else
        "OFF"
    )

    stream_text = (
        "ON"
        if data["streamActive"]
        else
        "OFF"
    )

    yolo_text = "Standby"

    if yolo.get("fire"):

        yolo_text = "FIRE"

    elif yolo.get("smoke"):

        yolo_text = "SMOKE"

    today_temp = data.get("todayTemp") or {}
    max_t = today_temp.get("maxTemp", 0.0)
    max_t_time = today_temp.get("maxTempTime", "-")
    min_t = today_temp.get("minTemp", 0.0)
    min_t_time = today_temp.get("minTempTime", "-")

    message = f"""AI FIRE DETECTOR
━━━━━━━━━━━━━━

ห้อง: {data["room"]}

สถานะ: {status}

Temperature: {data["temperature"]:.2f}°C
Today Max: {max_t:.2f}°C ({max_t_time})
Today Min: {min_t:.2f}°C ({min_t_time})
Gas / Smoke: {gas_text}
Humidity: {data["humidity"]:.2f}%
Risk: {data["risk"]:.2f}%
Camera: {camera_text}
Stream: {stream_text}
YOLO: {yolo_text}

━━━━━━━━━━━━━━"""

    return message


# =========================================================
# LINE RISK ALERT
# =========================================================

def send_risk_line_alert():

    with data_lock:

        data = dict(latest_data)

    gas_text = (
        "ตรวจพบ"
        if data["gasDetected"]
        else
        "ปกติ"
    )

    camera_text = (
        "ON"
        if data["camera"]
        else
        "OFF"
    )

    message = f"""🔥 FIRE RISK ALERT
━━━━━━━━━━━━━━

ห้อง: {data["room"]}

Risk: {data["risk"]:.2f}%
Status: HIGH RISK

Temperature: {data["temperature"]:.2f}°C
Gas / Smoke: {gas_text}
Humidity: {data["humidity"]:.2f}%
Camera: {camera_text}

🌐 AI FIRE DASHBOARD:
• Local: {LOCALHOST_URL}
• Public/Ngrok: {PUBLIC_NGROK_URL}

━━━━━━━━━━━━━━
Alert threshold: 50%"""

    send_line_push(message)


# =========================================================
# YOLO LINE ALERT
# =========================================================

def send_yolo_line_alert(
    detection_type,
    confidence
):

    with data_lock:

        data = dict(latest_data)

    confidence_percent = confidence * 100

    if detection_type == "fire":

        title = "YOLO FIRE DETECTION"

        detection = "FIRE DETECTED"

        description = (
            "YOLO ตรวจพบไฟจากกล้อง"
        )

    else:

        title = "YOLO SMOKE DETECTION"

        detection = "SMOKE DETECTED"

        description = (
            "YOLO ตรวจพบควันจากกล้อง"
        )

    gas_text = (
        "ตรวจพบ"
        if data["gasDetected"]
        else
        "ปกติ"
    )

    message = f"""🚨 {title}
━━━━━━━━━━━━━━

ห้อง: {data["room"]}

{detection}
Confidence: {confidence_percent:.2f}%

Temperature: {data["temperature"]:.2f}°C
Gas / Smoke: {gas_text}
Humidity: {data["humidity"]:.2f}%
Sensor Risk: {data["risk"]:.2f}%

{description}

🌐 AI FIRE DASHBOARD:
• Local: {LOCALHOST_URL}
• Public/Ngrok: {PUBLIC_NGROK_URL}

━━━━━━━━━━━━━━"""

    send_line_push(message)


# =========================================================
# CAMERA ON
# =========================================================

def camera_on():

    try:

        response = requests.get(
            CAMERA_ON_URL,
            timeout=5
        )

        if response.status_code == 200:

            print("[CAMERA] Camera ON")

            return True

        print(
            f"[WARN] Camera ON HTTP "
            f"{response.status_code}"
        )

    except Exception as e:

        print(
            f"[ERROR] Camera ON error: {e}"
        )

    return False


# =========================================================
# CAMERA OFF
# =========================================================

def camera_off():

    try:

        response = requests.get(
            CAMERA_OFF_URL,
            timeout=5
        )

        if response.status_code == 200:

            print("[CAMERA] Camera OFF")

            return True

        print(
            f"[WARN] Camera OFF HTTP "
            f"{response.status_code}"
        )

    except Exception as e:

        print(
            f"[ERROR] Camera OFF error: {e}"
        )

    return False


# =========================================================
# START STREAM
# =========================================================

def start_stream():

    global camera_running
    global stream_thread
    global yolo_thread

    with camera_lock:

        if camera_running:

            return

        camera_on()

        camera_running = True

        with data_lock:

            latest_data["camera"] = True

            latest_data["streamActive"] = True

        stream_thread = threading.Thread(
            target=stream_worker,
            daemon=True
        )

        stream_thread.start()

        yolo_thread = threading.Thread(
            target=yolo_worker,
            daemon=True
        )

        yolo_thread.start()

        print("[STREAM] Stream worker & YOLO worker started")


# =========================================================
# STOP STREAM
# =========================================================

def stop_stream():

    global camera_running
    global yolo_detections
    global latest_raw_frame
    global latest_annotated_frame

    with camera_lock:

        if not camera_running:

            return

        camera_running = False

        camera_off()

        with latest_frame_lock:

            latest_raw_frame = None
            latest_annotated_frame = None

        yolo_detections = []

        with data_lock:

            latest_data["camera"] = False

            latest_data["streamActive"] = False

            latest_data["yolo"] = {
                "fire": False,
                "smoke": False,
                "detections": []
            }

        print("[STREAM] Stream stopped")


# =========================================================
# YOLO PROCESS
# =========================================================

def process_yolo(frame):

    global last_yolo_alert_time

    if model is None:

        return frame, []

    try:

        results = model.predict(
            source=frame,
            conf=YOLO_CONFIDENCE,
            imgsz=YOLO_IMAGE_SIZE,
            verbose=False
        )

        result = results[0]

        annotated = result.plot()

        detections = []

        fire_detected = False
        smoke_detected = False

        highest_fire_conf = 0.0
        highest_smoke_conf = 0.0

        if result.boxes is not None:

            for box in result.boxes:

                cls_id = int(
                    box.cls[0]
                )

                confidence = float(
                    box.conf[0]
                )

                name = model.names.get(
                    cls_id,
                    str(cls_id)
                )

                name_lower = name.lower()

                if (
                    "fire" in name_lower
                    or
                    "smoke" in name_lower
                ):

                    detections.append({
                        "class": name,
                        "confidence":
                            round(
                                confidence * 100,
                                2
                            )
                    })

                if "fire" in name_lower:

                    fire_detected = True

                    highest_fire_conf = max(
                        highest_fire_conf,
                        confidence
                    )

                if "smoke" in name_lower:

                    smoke_detected = True

                    highest_smoke_conf = max(
                        highest_smoke_conf,
                        confidence
                    )

        current_time = time.time()

        if (
            fire_detected
            and
            highest_fire_conf >=
            YOLO_ALERT_CONFIDENCE
            and
            current_time -
            last_yolo_alert_time
            >= YOLO_ALERT_COOLDOWN
        ):

            send_yolo_line_alert(
                "fire",
                highest_fire_conf
            )

            last_yolo_alert_time = current_time

        elif (
            smoke_detected
            and
            highest_smoke_conf >=
            YOLO_ALERT_CONFIDENCE
            and
            current_time -
            last_yolo_alert_time
            >= YOLO_ALERT_COOLDOWN
        ):

            send_yolo_line_alert(
                "smoke",
                highest_smoke_conf
            )

            last_yolo_alert_time = current_time

        with data_lock:

            latest_data["yolo"] = {
                "fire": fire_detected,
                "smoke": smoke_detected,
                "detections": detections
            }

        return annotated, detections

    except Exception as e:

        print(
            f"❌ YOLO error: {e}"
        )

        return frame, []


# =========================================================
# STREAM WORKER
# =========================================================

def stream_worker():

    global latest_raw_frame

    print(
        f"🎥 Connecting camera stream: "
        f"{CAMERA_STREAM_URL}"
    )

    while camera_running:

        try:

            response = requests.get(
                CAMERA_STREAM_URL,
                stream=True,
                timeout=10
            )

            if response.status_code != 200:

                print(
                    f"⚠️ Camera stream HTTP "
                    f"{response.status_code}"
                )

                time.sleep(2)

                continue

            buffer = b""

            for chunk in response.iter_content(
                chunk_size=16384
            ):

                if not camera_running:

                    break

                buffer += chunk

                latest_jpg = None

                while True:

                    start = buffer.find(
                        b"\xff\xd8"
                    )

                    if start == -1:

                        break

                    end = buffer.find(
                        b"\xff\xd9",
                        start + 2
                    )

                    if end == -1:

                        if start > 65536:

                            buffer = buffer[start:]

                        break

                    latest_jpg = buffer[
                        start:end + 2
                    ]

                    buffer = buffer[
                        end + 2:
                    ]

                if latest_jpg is not None:

                    frame = cv2.imdecode(
                        np.frombuffer(
                            latest_jpg,
                            dtype=np.uint8
                        ),
                        cv2.IMREAD_COLOR
                    )

                    if frame is not None:

                        with latest_frame_lock:

                            latest_raw_frame = frame

        except Exception as e:

            print(
                f"❌ Stream worker error: {e}"
            )

            time.sleep(1)

    print("🎥 Stream worker exited")


# =========================================================
# YOLO WORKER
# =========================================================

def yolo_worker():

    global latest_annotated_frame

    print("🤖 YOLO worker thread started")

    last_run_time = 0.0

    while camera_running:

        try:

            current_time = time.time()

            # Limit YOLO inference rate to max ~15 FPS to prevent CPU thrashing
            if current_time - last_run_time < 0.06:

                time.sleep(0.01)

                continue

            raw_copy = None

            with latest_frame_lock:

                if latest_raw_frame is not None:

                    raw_copy = latest_raw_frame.copy()

            if raw_copy is None:

                time.sleep(0.02)

                continue

            processed, _ = process_yolo(raw_copy)

            last_run_time = time.time()

            with latest_frame_lock:

                latest_annotated_frame = processed

        except Exception as e:

            print(
                f"❌ YOLO worker error: {e}"
            )

            time.sleep(0.05)

    print("🤖 YOLO worker thread exited")


# =========================================================
# MJPEG GENERATOR
# =========================================================

def generate_camera_stream():

    last_yield_time = 0.0
    target_interval = 1.0 / 30.0  # Max 30 FPS stream
    last_frame_id = None
    cached_jpeg = None

    while camera_running:

        now = time.time()

        elapsed = now - last_yield_time

        if elapsed < target_interval:

            time.sleep(target_interval - elapsed)

        frame = None

        with latest_frame_lock:

            if latest_annotated_frame is not None:

                frame = latest_annotated_frame

            elif latest_raw_frame is not None:

                frame = latest_raw_frame

        if frame is None:

            time.sleep(0.01)

            continue

        try:

            frame_id = id(frame)

            if frame_id != last_frame_id or cached_jpeg is None:

                success, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [
                        cv2.IMWRITE_JPEG_QUALITY,
                        STREAM_JPEG_QUALITY
                    ]
                )

                if not success:

                    time.sleep(0.01)

                    continue

                cached_jpeg = buffer.tobytes()

                last_frame_id = frame_id

            last_yield_time = time.time()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                +
                cached_jpeg
                +
                b"\r\n"
            )

        except Exception:

            time.sleep(0.01)


# =========================================================
# MQTT CONNECT
# =========================================================

def mqtt_on_connect(
    client,
    userdata,
    flags,
    rc
):

    if rc == 0:

        print(
            "✅ MQTT Connected!"
        )

        print(
            f"📡 Subscribe: {MQTT_TOPIC}"
        )

        client.subscribe(
            MQTT_TOPIC
        )

    else:

        print(
            f"❌ MQTT connection failed: {rc}"
        )


# =========================================================
# SENSOR PAYLOAD PROCESSOR (HTTP & MQTT)
# =========================================================

def process_sensor_payload(data, source="SENSOR"):
    global previous_risk_above_50

    try:
        # =============================================
        # DYNAMIC CAMERA IP FROM ESP32
        # =============================================
        if "ip" in data and data["ip"]:
            esp_ip = str(data["ip"]).strip()
            global CAMERA_IP, CAMERA_STREAM_URL, CAMERA_ON_URL, CAMERA_OFF_URL
            if CAMERA_IP != esp_ip:
                CAMERA_IP = esp_ip
                CAMERA_STREAM_URL = f"http://{CAMERA_IP}/stream"
                CAMERA_ON_URL = f"http://{CAMERA_IP}/camera/on"
                CAMERA_OFF_URL = f"http://{CAMERA_IP}/camera/off"
                print(f"📷 [{source}] Dynamic CAMERA_IP updated to: {CAMERA_IP}")

        room = data.get("room", "warehouse")
        temperature = float(data.get("temperature", 0))
        humidity = float(data.get("humidity", 0))
        gas_raw = int(data.get("gasRaw", 0))

        # =============================================
        # GAS DETECTED
        # =============================================
        if "gasDetected" in data:
            gas_detected = bool(data["gasDetected"])
        else:
            if MQ_ACTIVE_LOW:
                gas_detected = (gas_raw == 0)
            else:
                gas_detected = (gas_raw == 1)

        gas_value = 100.0 if gas_detected else 0.0

        # =============================================
        # RISK
        # =============================================
        risk, temp_risk, gas_risk = calculate_risk(temperature, gas_detected)

        # =============================================
        # STATUS
        # =============================================
        if risk >= 50:
            status = "HIGH RISK"
        elif risk >= 25:
            status = "MODERATE"
        else:
            status = "NORMAL"

        # =============================================
        # ABNORMAL
        # =============================================
        abnormal = (temperature >= TEMP_CAMERA_TRIGGER or gas_detected)

        # =============================================
        # UPDATE DAILY TEMP IN DB
        # =============================================
        daily_stats = update_daily_temperature(temperature)

        # =============================================
        # UPDATE DATA
        # =============================================
        with data_lock:
            latest_data["room"] = room
            latest_data["temperature"] = temperature
            latest_data["humidity"] = humidity
            latest_data["gasRaw"] = gas_raw
            latest_data["gas"] = gas_value
            latest_data["gasDetected"] = gas_detected
            latest_data["risk"] = risk
            latest_data["tempRisk"] = temp_risk
            latest_data["gasRisk"] = gas_risk
            latest_data["status"] = status
            if daily_stats:
                latest_data["todayTemp"] = daily_stats
            latest_data["lastUpdate"] = time.strftime("%H:%M:%S")

        # =============================================
        # GRAPH HISTORY
        # =============================================
        with data_lock:
            history.append({
                "time": time.strftime("%H:%M:%S"),
                "temperature": temperature,
                "gas": gas_value,
                "risk": risk
            })

        # =============================================
        # RISK 50% ONE-SHOT ALERT
        # =============================================
        risk_above_50 = (risk >= RISK_LINE_ALERT_THRESHOLD)
        if risk_above_50 and not previous_risk_above_50:
            print("[ALERT] Risk crossed 50% -> LINE alert")
            send_risk_line_alert()
        previous_risk_above_50 = risk_above_50

        # =============================================
        # CAMERA CONTROL
        # =============================================
        if abnormal:
            start_stream()
        else:
            stop_stream()

        print(
            f"[{source}] {room} | T={temperature:.2f}°C | H={humidity:.2f}% | "
            f"Gas={gas_value:.2f}% | Risk={risk:.2f}% | {status}"
        )

    except Exception as e:
        print(f"[ERROR] {source} payload processing error: {e}")


# =========================================================
# MQTT MESSAGE
# =========================================================

def mqtt_on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        process_sensor_payload(data, source="MQTT")
    except Exception as e:
        print(f"[ERROR] MQTT message decode error: {e}")


# =========================================================
# MQTT THREAD
# =========================================================

def mqtt_worker():

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION1
    )

    client.on_connect = mqtt_on_connect

    client.on_message = mqtt_on_message

    try:

        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            60
        )

        client.loop_forever()

    except Exception as e:

        print(
            f"❌ MQTT worker error: {e}"
        )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
def dashboard():

    return render_template(
        "dashboard.html"
    )


# =========================================================
# API SENSOR INGESTION (HTTP POST from ESP32)
# =========================================================

@app.route("/api/sensor", methods=["POST"])
def api_sensor():
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload"}), 400

        process_sensor_payload(data, source="HTTP")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[ERROR] /api/sensor failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================
# API DATA
# =========================================================

@app.route("/api/data")
def api_data():

    with data_lock:

        return jsonify(
            latest_data
        )


# =========================================================
# API HISTORY
# =========================================================

@app.route("/api/history")
def api_history():

    with data_lock:

        return jsonify(
            list(history)
        )


# =========================================================
# API DAILY TEMP
# =========================================================

@app.route("/api/daily")
def api_daily():

    return jsonify(
        get_all_daily_temperatures()
    )


# =========================================================
# CAMERA STREAM
# =========================================================

@app.route("/camera-stream")
def camera_stream():

    return Response(
        generate_camera_stream(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        )
    )


# =========================================================
# LINE SIGNATURE
# =========================================================

def verify_line_signature(
    body,
    signature
):

    if not LINE_CHANNEL_SECRET:

        return False

    digest = hmac.new(
        LINE_CHANNEL_SECRET.encode(
            "utf-8"
        ),
        body,
        hashlib.sha256
    ).digest()

    expected = base64.b64encode(
        digest
    ).decode()

    return hmac.compare_digest(
        expected,
        signature or ""
    )


# =========================================================
# LINE CALLBACK
# =========================================================

@app.route(
    "/callback",
    methods=["POST"]
)
def callback():

    body = request.get_data()

    signature = request.headers.get(
        "X-Line-Signature",
        ""
    )

    if not verify_line_signature(
        body,
        signature
    ):

        return "Invalid signature", 400

    try:

        payload = request.get_json()

        events = payload.get(
            "events",
            []
        )

        for event in events:

            event_type = event.get(
                "type"
            )

            source = event.get(
                "source",
                {}
            )

            # =========================================
            # FOLLOW
            # =========================================

            if event_type == "follow":

                save_line_user(
                    source
                )

                reply_token = event.get(
                    "replyToken"
                )

                if reply_token:

                    line_reply(
                        reply_token,
                        build_status_message()
                    )

            # =========================================
            # UNFOLLOW
            # =========================================

            elif event_type == "unfollow":

                remove_line_user(
                    source.get(
                        "userId"
                    )
                )

            # =========================================
            # MESSAGE
            # =========================================

            elif event_type == "message":

                save_line_user(
                    source
                )

                message = event.get(
                    "message",
                    {}
                )

                if message.get(
                    "type"
                ) != "text":

                    continue

                text = message.get(
                    "text",
                    ""
                ).strip().lower()

                reply_token = event.get(
                    "replyToken"
                )

                # =====================================
                # STATUS
                # =====================================

                if text in [
                    "สถานะ",
                    "status",
                    "state",
                    "ดูสถานะ"
                ]:

                    reply_text = (
                        build_status_message()
                    )

                # =====================================
                # RISK
                # =====================================

                elif text in [
                    "ความเสี่ยง",
                    "risk",
                    "ดูความเสี่ยง",
                    "ความเสี่ยงตอนนี้"
                ]:

                    with data_lock:

                        d = dict(
                            latest_data
                        )

                    reply_text = f"""🔥 AI FIRE RISK

📍 ห้อง: {d["room"]}

🔥 Risk
{d["risk"]:.2f}%

🌡 Temperature
{d["temperature"]:.2f}°C

💨 Gas / Smoke
{"ตรวจพบ" if d["gasDetected"] else "ปกติ"}

💧 Humidity
{d["humidity"]:.2f}%

📊 Status
{d["status"]}"""

                # =====================================
                # DAILY TEMP
                # =====================================

                elif text in [
                    "อุณหภูมิ",
                    "อุณหภูมิวันนี้",
                    "วันนี้",
                    "daily",
                    "temp"
                ]:

                    with data_lock:

                        d = dict(
                            latest_data
                        )

                    today_t = d.get("todayTemp") or {}

                    max_t = today_t.get("maxTemp", 0.0)
                    max_t_time = today_t.get("maxTempTime", "-")
                    min_t = today_t.get("minTemp", 0.0)
                    min_t_time = today_t.get("minTempTime", "-")

                    reply_text = f"""🌡 อุณหภูมิประจำวัน ({today_t.get('date', '-')})

📍 ห้อง: {d["room"]}
🔥 ปัจจุบัน: {d["temperature"]:.2f}°C
🔺 สูงสุด: {max_t:.2f}°C (เวลา {max_t_time})
🔻 ต่ำสุด: {min_t:.2f}°C (เวลา {min_t_time})"""

                # =====================================
                # CAMERA
                # =====================================

                elif text in [
                    "กล้อง",
                    "camera",
                    "ดูภาพ"
                ]:

                    with data_lock:

                        camera_state = (
                            latest_data["camera"]
                        )

                        stream_state = (
                            latest_data[
                                "streamActive"
                            ]
                        )

                    reply_text = f"""📷 CAMERA

Camera:
{"ON" if camera_state else "OFF"}

Stream:
{"ON" if stream_state else "OFF"}

🎥 Dashboard
{DASHBOARD_URL}"""

                # =====================================
                # DASHBOARD
                # =====================================

                elif text in [
                    "dashboard",
                    "web",
                    "เว็บ"
                ]:

                    reply_text = f"""🌐 AI FIRE DASHBOARD

เปิด Dashboard ได้ที่:

• Localhost:
{LOCALHOST_URL}

• Ngrok / Public:
{PUBLIC_NGROK_URL}"""

                # =====================================
                # PING
                # =====================================

                elif text == "ping":

                    reply_text = (
                        "🏓 Pong!\n\n"
                        "AI Fire Detector Online"
                    )

                # =====================================
                # HELP
                # =====================================

                elif text in [
                    "help",
                    "menu",
                    "เมนู",
                    "คำสั่ง",
                    "ช่วยเหลือ"
                ]:

                    reply_text = f"""🔥 AI FIRE DETECTOR

คำสั่ง:

📊 สถานะ
ดูสถานะระบบ

🔥 ความเสี่ยง
ดูค่า Risk

📷 กล้อง
ดูสถานะกล้อง

🌐 Dashboard
เปิด Dashboard

🏓 ping
ตรวจสอบระบบ"""

                # =====================================
                # UNKNOWN
                # =====================================

                else:

                    reply_text = """❓ ไม่พบคำสั่ง

พิมพ์ "help"
เพื่อดูคำสั่งทั้งหมด"""

                if reply_token:

                    line_reply(
                        reply_token,
                        reply_text
                    )

        return "OK", 200

    except Exception as e:

        print(
            f"❌ LINE callback error: {e}"
        )

        return "Internal Server Error", 500


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    init_db()

    with data_lock:

        latest_data["todayTemp"] = get_today_temperature()

    print()
    print("=" * 60)
    print("AI FIRE DETECTOR")
    print("=" * 60)

    print(
        f"Dashboard: {DASHBOARD_URL}"
    )

    print(
        f"Camera: {CAMERA_STREAM_URL}"
    )

    print(
        f"MQTT: "
        f"{MQTT_BROKER}:{MQTT_PORT}"
    )

    print(
        f"Topic: {MQTT_TOPIC}"
    )

    print(
        f"Risk alert: "
        f"{RISK_LINE_ALERT_THRESHOLD}%"
    )

    print(
        f"Camera trigger: "
        f"{TEMP_CAMERA_TRIGGER}°C"
    )

    print("=" * 60)
    print()

    mqtt_thread = threading.Thread(
        target=mqtt_worker,
        daemon=True
    )

    mqtt_thread.start()

    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=False,
        threaded=True
    )