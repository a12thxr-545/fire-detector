
from pathlib import Path
import shutil


SOURCE = Path("datasets/fire_smoke")
OUTPUT = Path("datasets/fire_smoke_2class")


# =========================================================
# CREATE FOLDERS
# =========================================================

for split in ["train", "valid", "test"]:
    (OUTPUT / split / "images").mkdir(
        parents=True,
        exist_ok=True
    )

    (OUTPUT / split / "labels").mkdir(
        parents=True,
        exist_ok=True
    )


# =========================================================
# CLASS MAPPING
#
# Original:
# 0 = Fire
# 1 = default
# 2 = smoke
#
# New:
# 0 = Fire
# 1 = Smoke
# =========================================================

CLASS_MAP = {
    0: 0,
    2: 1
}


total_images = 0
total_labels = 0
removed_default = 0


# =========================================================
# PROCESS DATASET
# =========================================================

for split in ["train", "valid", "test"]:

    image_dir = SOURCE / split / "images"
    label_dir = SOURCE / split / "labels"

    output_image_dir = OUTPUT / split / "images"
    output_label_dir = OUTPUT / split / "labels"

    if not image_dir.exists():
        print(
            f"WARNING: {image_dir} not found"
        )
        continue

    for image_file in image_dir.iterdir():

        if image_file.suffix.lower() not in [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        ]:
            continue

        label_file = (
            label_dir /
            f"{image_file.stem}.txt"
        )

        # Copy image
        shutil.copy2(
            image_file,
            output_image_dir / image_file.name
        )

        total_images += 1

        # No label
        if not label_file.exists():
            continue

        new_lines = []

        for line in label_file.read_text().splitlines():

            line = line.strip()

            if not line:
                continue

            parts = line.split()

            try:
                old_class = int(parts[0])
            except ValueError:
                continue

            # Remove default
            if old_class == 1:
                removed_default += 1
                continue

            # Keep Fire / Smoke
            if old_class in CLASS_MAP:

                parts[0] = str(
                    CLASS_MAP[old_class]
                )

                new_lines.append(
                    " ".join(parts)
                )

                total_labels += 1

        # Only create label file if objects remain
        if new_lines:

            output_label_file = (
                output_label_dir /
                label_file.name
            )

            output_label_file.write_text(
                "\n".join(new_lines) + "\n"
            )


# =========================================================
# CREATE DATA.YAML
# =========================================================

yaml_content = """path: datasets/fire_smoke_2class

train: train/images
val: valid/images
test: test/images

names:
  0: Fire
  1: Smoke

nc: 2
"""

(OUTPUT / "data.yaml").write_text(
    yaml_content
)


# =========================================================
# RESULT
# =========================================================

print()
print("=" * 60)
print("DATASET PREPARATION COMPLETE")
print("=" * 60)

print(
    f"Images copied : {total_images}"
)

print(
    f"Labels kept   : {total_labels}"
)

print(
    f"Default removed: {removed_default}"
)

print()
print(
    "Output:"
)

print(
    OUTPUT / "data.yaml"
)

print()
print("Classes:")
print("0 = Fire")
print("1 = Smoke")
