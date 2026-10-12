"""
Download the built-in photos in static/cafes/stock/ from Unsplash.

Cafés without their own photos can pick one of these in the dashboard. They're
plain static files, so they survive redeploys and need no image storage.
All are free to use under the Unsplash License (https://unsplash.com/license);
each photo's page is https://unsplash.com/photos/<id> if you want to credit it.

Run:  python tools/fetch_stock_photos.py
"""

import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "cafes" / "stock"

# Menu pictures, by StockImage value.
MENU = {
    "espresso": "1610889556528-9a770e32642f",
    "cappuccino": "1572442388796-11668a67e53d",
    "latte": "1509042239860-f550ce710b93",
    "chai": "1576092768241-dec231879fc3",
    "hot-chocolate": "1542990253-0d0f5be5f0ed",
    "iced-latte": "1461023058943-07fcbe16d735",
    "juice": "1600271886742-f049cd451bba",
    "croissant": "1530610476181-d83430b64dcd",
    "banana-bread": "1606101273945-e9eba91c0dc4",
    "mandazi": "1514517220017-8ce97a34a7b6",
    "breakfast": "1533089860892-a7c6f0a88666",
    "avocado-toast": "1588137378633-dea1336ce1e2",
}

# Home page cover photos, by StockCover value.
COVERS = {
    "counter": "1554118811-1e0d58224f24",
    "coffee-bar": "1453614512568-c4024d13c247",
    "terrace": "1559925393-8be0ec4767c8",
    "garden": "1600093463592-8e36ae95ef56",
    "window-seat": "1445116572660-236099ec97a0",
}


def fetch(photo_id, path, width, height, quality):
    url = f"https://images.unsplash.com/photo-{photo_id}?w={width}&h={height}&fit=crop&q={quality}&fm=jpg"
    with urllib.request.urlopen(url, timeout=60) as response:
        path.write_bytes(response.read())
    print(f"{path.relative_to(OUT)}  {path.stat().st_size // 1024} KB")


def main():
    (OUT / "covers").mkdir(parents=True, exist_ok=True)
    for name, photo_id in MENU.items():
        fetch(photo_id, OUT / f"{name}.jpg", 1000, 750, 72)
    for name, photo_id in COVERS.items():
        fetch(photo_id, OUT / "covers" / f"{name}.jpg", 1800, 1100, 60)


if __name__ == "__main__":
    main()
