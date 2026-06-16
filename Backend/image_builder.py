import json
import time
import os
import sys
from ddgs import DDGS  # تم تغيير الاستيراد

INPUT_FILE = "technology_dataset.json"
OUTPUT_FILE = "images_only.json"
MAX_IMAGES = 3
DELAY = 3  # زيادة التأخير لتجنب ratelimit

print("Current directory:", os.getcwd())
if not os.path.exists(INPUT_FILE):
    print(f"ERROR: {INPUT_FILE} not found!")
    sys.exit(1)

def get_images(topic):
    try:
        with DDGS() as ddgs:
            results = ddgs.images(topic, max_results=MAX_IMAGES)
            urls = [r["image"] for r in results if r.get("image")]
            return urls
    except Exception as e:
        print(f"   Error for '{topic}': {e}")
        return []

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    documents = json.load(f)

images_data = []
print(f"Loaded {len(documents)} documents.")

for i, doc in enumerate(documents):
    topic = doc.get("topic", "")
    print(f"[{i+1}/{len(documents)}] {topic}")
    urls = get_images(topic)
    images_data.append({"id": doc.get("id", i+1), "topic": topic, "images": urls})
    time.sleep(DELAY)  # تأخير أطول

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(images_data, f, ensure_ascii=False, indent=2)

print(f"Done! Saved to {OUTPUT_FILE}")