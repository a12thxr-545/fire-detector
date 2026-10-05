import joblib
import pandas as pd

# โหลดโมเดล AI
model = joblib.load("fire_model.pkl")

# ข้อมูลทดลอง
data = pd.DataFrame([{
    "temperature": 38,
    "humidity": 35,
    "gas": 75,
    "temp_change": 3,
    "gas_change": 18,
    "room": 1
}])

# AI ทำนาย
prediction = model.predict(data)[0]

# ความน่าจะเป็น
probability = model.predict_proba(data)[0]

# ถ้า AI มี class 0 และ 1
if len(probability) > 1:
    risk = probability[1] * 100
else:
    risk = probability[0] * 100

print()
print("==============================")
print("      AI FIRE DETECTOR")
print("==============================")

print(f"Temperature : {data['temperature'][0]} °C")
print(f"Humidity    : {data['humidity'][0]} %")
print(f"Gas         : {data['gas'][0]} %")
print(f"AI Risk     : {risk:.2f} %")

if risk < 30:
    print("STATUS      : 🟢 ไม่มีความเสี่ยง")

elif risk < 70:
    print("STATUS      : 🟡 ค่อนข้างเสี่ยง")

else:
    print("STATUS      : 🔴 เสี่ยงมากๆ")

print("==============================")
