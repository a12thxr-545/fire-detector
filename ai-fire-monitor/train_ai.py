import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score


# ==========================================
# โหลด Dataset
# ==========================================

data = pd.read_csv("dataset/fire_data.csv")

print("Dataset:")
print(data)

# ==========================================
# แปลง room เป็นตัวเลข
# ==========================================

room_mapping = {
    "medicine": 0,
    "warehouse": 1,
    "server": 2
}

data["room"] = data["room"].map(room_mapping)


# ==========================================
# Features
# ==========================================

features = [
    "temperature",
    "humidity",
    "gas",
    "temp_change",
    "gas_change",
    "room"
]

X = data[features]

# 0 = ปกติ
# 1 = เสี่ยง
y = data["risk"]


# ==========================================
# แบ่งข้อมูล Train / Test
# ==========================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)


# ==========================================
# Random Forest
# ==========================================

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=8,
    random_state=42
)


# ==========================================
# Train
# ==========================================

print()
print("กำลัง Train Random Forest...")

model.fit(
    X_train,
    y_train
)


# ==========================================
# Test
# ==========================================

prediction = model.predict(X_test)

accuracy = accuracy_score(
    y_test,
    prediction
)

print()
print("================================")
print("AI TRAIN COMPLETE")
print("================================")

print(
    f"Accuracy: {accuracy * 100:.2f}%"
)


# ==========================================
# Save Model
# ==========================================

joblib.dump(
    model,
    "fire_model.pkl"
)

print()
print("บันทึก AI แล้ว:")
print("fire_model.pkl")
