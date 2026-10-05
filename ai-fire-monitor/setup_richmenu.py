import os
import sys
import requests

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

# ==========================================
# ตั้ง URL Dashboard ตรงนี้
# ==========================================

DASHBOARD_URL = "https://reverence-reuse-chop.ngrok-free.dev"

# ==========================================
# ไฟล์รูป Rich Menu
# ==========================================

IMAGE_FILE = "richmenu.png"

if not TOKEN:
    print("❌ ไม่พบ LINE_CHANNEL_ACCESS_TOKEN")
    print()
    print("ให้ตั้งค่าก่อน เช่น:")
    print()
    print('export LINE_CHANNEL_ACCESS_TOKEN="YOUR_TOKEN"')
    sys.exit(1)

if not os.path.exists(IMAGE_FILE):
    print(f"❌ ไม่พบไฟล์ {IMAGE_FILE}")
    print("กรุณาเอา richmenu.png มาไว้ในโฟลเดอร์เดียวกับไฟล์นี้")
    sys.exit(1)

if "YOUR-DASHBOARD-URL" in DASHBOARD_URL:
    print("❌ กรุณาใส่ URL Dashboard ก่อน")
    print()
    print('ตัวอย่าง:')
    print('DASHBOARD_URL = "https://reverence-reuse-chop.ngrok-free.dev"')
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# ==========================================
# 1. สร้าง Rich Menu
# ==========================================

print("🔧 กำลังสร้าง Rich Menu...")

menu_data = {
    "size": {
        "width": 2500,
        "height": 843
    },
    "selected": True,
    "name": "AI Fire Detector Menu",
    "chatBarText": "🔥 AI Fire",
    "areas": [
        {
            "bounds": {
                "x": 0,
                "y": 0,
                "width": 833,
                "height": 843
            },
            "action": {
                "type": "uri",
                "uri": DASHBOARD_URL
            }
        },
        {
            "bounds": {
                "x": 833,
                "y": 0,
                "width": 834,
                "height": 843
            },
            "action": {
                "type": "message",
                "text": "สถานะ"
            }
        },
        {
            "bounds": {
                "x": 1667,
                "y": 0,
                "width": 833,
                "height": 843
            },
            "action": {
                "type": "message",
                "text": "ความเสี่ยง"
            }
        }
    ]
}

response = requests.post(
    "https://api.line.me/v2/bot/richmenu",
    headers=HEADERS,
    json=menu_data
)

if response.status_code != 200:
    print("❌ สร้าง Rich Menu ไม่สำเร็จ")
    print(response.text)
    sys.exit(1)

rich_menu_id = response.json()["richMenuId"]

print("✅ สร้าง Rich Menu สำเร็จ")
print(f"Rich Menu ID: {rich_menu_id}")

# ==========================================
# 2. Upload รูป
# ==========================================

print("🖼️ กำลังอัปโหลด richmenu.png...")

image_headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "image/png"
}

with open(IMAGE_FILE, "rb") as image:
    response = requests.post(
        f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
        headers=image_headers,
        data=image
    )

if response.status_code != 200:
    print("❌ Upload รูปไม่สำเร็จ")
    print(response.text)
    sys.exit(1)

print("✅ Upload รูปสำเร็จ")

# ==========================================
# 3. ตั้งเป็น Default Rich Menu
# ==========================================

print("📌 กำลังตั้งเป็น Default Rich Menu...")

response = requests.post(
    f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
    headers={
        "Authorization": f"Bearer {TOKEN}"
    }
)

if response.status_code != 200:
    print("❌ ตั้ง Default Rich Menu ไม่สำเร็จ")
    print(response.text)
    sys.exit(1)

# ==========================================
# เสร็จ
# ==========================================

print()
print("========================================")
print("🎉 RICH MENU พร้อมใช้งานแล้ว!")
print("========================================")
print()
print(f"Rich Menu ID: {rich_menu_id}")
print()
print("ปุ่ม:")
print("🔥 Dashboard")
print("📊 สถานะ")
print("⚠️ ความเสี่ยง")
print()
print("เปิด LINE บนมือถือเพื่อทดสอบ")