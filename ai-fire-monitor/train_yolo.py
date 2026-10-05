import os
import sys
from pathlib import Path
from ultralytics import YOLO
import torch

def train():
    project_dir = Path(__file__).parent.resolve()
    yaml_path = project_dir / "datasets" / "fire_smoke_2class" / "data.yaml"
    
    if not yaml_path.exists():
        print(f"❌ Error: {yaml_path} not found!")
        sys.exit(1)
        
    print("=" * 60)
    print("🔥 HIGH-ACCURACY YOLO FIRE & SMOKE TRAINING 🔥")
    print("=" * 60)
    print(f"📁 Dataset YAML: {yaml_path}")
    
    # Multi-threaded CPU execution for fast and stable PyTorch training on ARM Apple Silicon
    torch.set_num_threads(8)
    device = "cpu"
    print("⚡ Acceleration: Multi-threaded ARM CPU (8 Threads)")
        
    # Load base model (yolov8s - Small model for high accuracy & fast real-time inference)
    base_model = "yolov8s.pt"
    print(f"📦 Loading pre-trained base model: {base_model}")
    model = YOLO(base_model)
    
    print("\n🚀 Starting Training (50 Epochs, High Precision Augmentation)...")
    results = model.train(
        data=str(yaml_path),
        epochs=50,
        imgsz=640,
        batch=16,
        workers=4,
        cache=True,
        device=device,
        patience=15,
        save=True,
        project=str(project_dir / "runs" / "train"),
        name="fire_smoke_high_acc",
        exist_ok=True,
        # Augmentations tailored for fire & smoke detection
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        verbose=True
    )
    
    best_weights = project_dir / "runs" / "train" / "fire_smoke_high_acc" / "weights" / "best.pt"
    target_best = project_dir / "best.pt"
    
    if best_weights.exists():
        import shutil
        shutil.copy2(best_weights, target_best)
        print("\n" + "=" * 60)
        print("✅ TRAINING COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print(f"🎯 Best model saved to: {target_best}")
        
        # Evaluate model on test set
        print("\n📊 Evaluating model performance on validation set...")
        val_results = model.val(data=str(yaml_path), split="val", device=device)
        print(f"📈 mAP50    : {val_results.box.map50 * 100:.2f}%")
        print(f"📈 mAP50-95 : {val_results.box.map * 100:.2f}%")
        print(f"🎯 Precision: {val_results.box.mp * 100:.2f}%")
        print(f"🎯 Recall   : {val_results.box.mr * 100:.2f}%")
    else:
        print(f"⚠️ Warning: Best weights not found at {best_weights}")

if __name__ == "__main__":
    train()
