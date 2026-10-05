#  AI Fire & Smoke Detection System (ระบบตรวจจับไฟและควันด้วย AI + IoT)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF.svg)](https://docs.ultralytics.com/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000.svg)](https://flask.palletsprojects.com/)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32--CAM-red.svg)](https://www.espressif.com/)
[![MQTT](https://img.shields.io/badge/Protocol-MQTT-3C2179.svg)](https://mqtt.org/)
[![LINE API](https://img.shields.io/badge/Messaging-LINE%20API-00C300.svg)](https://developers.line.biz/)

ระบบเฝ้าระวังและตรวจจับอัคคีภัยแบบเรียลไทม์ที่ผสมผสานพลังของ **Artificial Intelligence (Computer Vision)** ร่วมกับ **IoT Microcontroller (ESP32-CAM)** เพื่อประมวลผลการเกิดเปลวไฟ ควัน และค่าดัชนีความเสี่ยงจากสภาพแวดล้อม (อุณหภูมิ, ความชื้น, ปริมาณก๊าซ/ควัน) พร้อมแจ้งเตือนเข้า **LINE Official Account** แบบทันทีทันใด

---

##  จุดเด่นของโครงการ (Key Features)

* ** Real-time AI Object Detection (YOLOv8)**: ตรวจจับภาพเปลวไฟ (Fire) และควัน (Smoke) แบบเรียลไทม์ด้วยคอนฟิเดนซ์ความแม่นยำสูง
* ** Multi-Sensor Monitoring**: อ่านค่าจากเซนเซอร์ **DHT11** (อุณหภูมิและความชื้น) และ **MQ Sensor** (ก๊าซและควัน) ส่งข้อมูลผ่านโปรโตคอล **MQTT**
* ** Modern Web Dashboard**: หน้าจอควบคุมแบบ Interactive Glassmorphism UI แสดงผลวิดีโอสตรีมสด, กราฟสถิติแบบเรียลไทม์, และตารางบันทึกค่าอุณหภูมิสูงสุด/ต่ำสุดประจำวัน (SQLite Database)
* ** LINE Messaging API & Rich Menu**: ส่งภาพถ่ายสถานการณ์จริงพร้อมกรอบ AI Detection เข้า LINE ทันทีเมื่อพบความเสี่ยง และรองรับการสั่งงานผ่าน Rich Menu
* ** Machine Learning Risk Model**: วิเคราะห์ความเสี่ยงรวมโดยใช้ Scikit-learn (RandomForest) คำนวณร่วมระหว่างสภาพแวดล้อมและภาพถ่าย

---

##  สถาปัตยกรรมระบบ (System Architecture)

```
[ ESP32-CAM + Sensors ]
   │  ├── Camera Stream (HTTP Video Stream)
   │  └── DHT11 & MQ Sensors (MQTT / HTTP Data POST)
   ▼
[ Flask AI Monitor Server (server.py) ]
   │  ├── YOLOv8 Engine (Fire & Smoke Detection)
   │  ├── Scikit-Learn Model (Environmental Risk Calculation)
   │  ├── SQLite Database (Temperature Extremes & History)
   │  └── MQTT Broker Client (Mosquitto)
   ├──► [ Interactive Web Dashboard ] (Real-time Video & Gauges)
   └──► [ LINE Messaging API ] ────► User Mobile App (Alert + Photo)
```

---

##  โครงสร้างโปรเจกต์ (Project Structure)

```
fire-detector/
├── ai-fire-monitor/              # ส่วนเซิร์ฟเวอร์ AI และ Dashboard
│   ├── captures/                 # โฟลเดอร์เก็บภาพถ่ายเหตุการณ์ความเสี่ยง
│   ├── datasets/                 # ชุดข้อมูลสำหรับฝึกฝน AI (Datasets)
│   ├── static/                   # สไตล์ชีต CSS และ สคริปต์ JavaScript หน้าเว็บ
│   │   ├── style.css
│   │   └── script.js
│   ├── templates/                # แม่แบบ HTML
│   │   └── dashboard.html        # หน้าจอควบคุม Web Dashboard
│   ├── best.pt                   # โมเดล YOLOv8 ที่ฝึกฝนสำเร็จแล้ว
│   ├── fire_model.pkl            # โมเดล Scikit-learn ประเมินความเสี่ยงเซนเซอร์
│   ├── server.py                 # Core Backend (Flask + MQTT + LINE API)
│   ├── train_yolo.py             # สคริปต์สำหรับ Train โมเดล YOLOv8
│   ├── train_ai.py               # สคริปต์สำหรับ Train โมเดล Scikit-learn
│   ├── setup_richmenu.py         # สคริปต์ติดตั้ง LINE Rich Menu
│   ├── start.sh                  # Shell script สำหรับเปิดระบบทั้งหมดพร้อมกัน
│   └── requirements.txt          # รายการ Library dependencies
├── esp32/                        # โค้ดสำหรับฮาร์ดแวร์ ESP32-CAM
│   └── fire_detector_copy_20260916204020/
│       └── fire_detector_copy_20260916204020.ino # Firmware สำหรับ ESP32
├── .gitignore                    # ไฟล์ยกเว้นการอัปโหลด Git
└── README.md                     # เอกสารอธิบายโปรเจกต์
```

---

##  ฮาร์ดแวร์และการต่อสาย (Hardware Requirements)

1. **ESP32-CAM** (AI-Thinker Module)
2. **DHT11 Sensor** (เซนเซอร์วัดอุณหภูมิและความชื้น) -> ต่อเข้ากับปิน `GPIO 13`
3. **MQ Gas Sensor** (เซนเซอร์ตรวจจับก๊าซ/ควัน) -> ต่อเข้ากับปิน `GPIO 14` (Active LOW)
4. **Buzzer / Alarm** -> ต่อเข้ากับปิน `GPIO 12`
5. **Alert LED** -> ต่อเข้ากับปิน `GPIO 2`

---

##  การติดตั้งและใช้งาน (Installation & Setup)

### 1. การเตรียมเซิร์ฟเวอร์ AI (AI Monitor Server)

1. **Clone Repository**
   ```bash
   git clone https://github.com/a12thxr-545/fire-detector.git
   cd fire-detector/ai-fire-monitor
   ```

2. **สร้าง Virtual Environment และติดตั้ง Dependencies**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **ตั้งค่า Environment Variables (LINE Messaging API)**
   ```bash
   export LINE_CHANNEL_ACCESS_TOKEN="YOUR_LINE_ACCESS_TOKEN"
   export LINE_CHANNEL_SECRET="YOUR_LINE_CHANNEL_SECRET"
   ```

4. **เริ่มการทำงานของเซิร์ฟเวอร์**
   ```bash
   python3 server.py
   ```
   หรือใช้ `start.sh` บน macOS เพื่อรัน Mosquitto MQTT, Flask Server และ Tunnel พร้อมกัน:
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

5. **เข้าใช้งาน Dashboard**
   เปิดเบราว์เซอร์ไปที่ `http://localhost:5001`

---

### 2. การอัปโหลดโค้ดลง ESP32-CAM

1. เปิดไฟล์ `esp32/fire_detector_copy_20260916204020/fire_detector_copy_20260916204020.ino` ใน **Arduino IDE**
2. แก้ไขค่าการเชื่อมต่อ Wi-Fi และ IP ของเซิร์ฟเวอร์:
   ```cpp
   const char *WIFI_SSID = "YOUR_WIFI_SSID";
   const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char *SERVER_HOST = "YOUR_SERVER_IP";
   ```
3. เลือก Board เป็น **AI Thinker ESP32-CAM** และทําการ Upload Firmware

---

### 3. การติดตั้ง LINE Rich Menu (Optional)

ตั้งค่าเมนูปุ่มกดบน LINE Official Account ด้วยสคริปต์อัตโนมัติ:
```bash
python3 setup_richmenu.py
```

---

##  การฝึกฝนโมเดล AI เพิ่มเติม (AI Model Training)

หากต้องการฝึกฝนโมเดลตรวจจับไฟและควันด้วยชุดข้อมูลของคุณเอง:

1. วางไฟล์ `data.yaml` และชุดภาพใน `ai-fire-monitor/datasets/fire_smoke_2class/`
2. รันสคริปต์ฝึกฝน YOLOv8:
   ```bash
   python3 train_yolo.py
   ```
3. โมเดลที่ดีที่สุดจะถูกบันทึกเป็น `best.pt` โดยอัตโนมัติ

---

##  การรับประกันและการใช้งาน (License)

โปรเจกต์นี้เปิดให้ใช้งานและพัฒนาต่อเพื่อการศึกษาและวิจัย (Open-source for educational and research purposes).

---
*จัดทำและพัฒนาโดยทีมงาน นายอติชาตเดโช หนุนกลาง และ นาย พิสิฐ ครูสอนดี* 
