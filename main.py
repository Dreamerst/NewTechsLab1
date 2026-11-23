import csv
import os, json, time, requests
from datetime import datetime, timezone

from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

META_COLS = ["date", "url", "filename", "class"]


def page_urls(text, page, extra):
    r = requests.get("https://yandex.ru/images/search",
                     params={"text": text, "p": page, "itype": "jpg", **extra},
                     headers=HEADERS, timeout=15)
    app = BeautifulSoup(r.content, "html.parser").find(
        "div", id=lambda x: x and x.startswith("ImagesApp"))
    if not app:
        return []
    state = json.loads(app.get("data-state"))
    items = state["initialState"]["serpList"]["items"]
    urls = []
    for iid in items["keys"]:
        item = items["entities"].get(iid)
        if not isinstance(item, dict):
            continue
        url = item.get("origUrl") or (item.get("viewerData") or {}).get("img_href")
        if url and url.startswith("//"):
            url = "https:" + url
        if url:
            urls.append(url)
    return urls


def download_images(base, class_label, folder, total=1000):
    os.makedirs(folder, exist_ok=True)
    seen = set()
    rows_meta = []
    saved = 0
    for extra in ({"iorient": o} for o in ("horizontal", "vertical", "square")):
        page = 0
        while saved < total:
            urls = page_urls(base, page, extra)
            if not urls:
                break
            new = 0
            for url in urls:
                if saved >= total:
                    break
                if url in seen:
                    continue
                seen.add(url)
                new += 1

                try:
                    r = requests.get(url, headers=HEADERS, timeout=15)
                    if r.status_code != 200 or "jpeg" not in r.headers.get("Content-Type", ""):
                        continue
                except requests.RequestException:
                    continue

                path = os.path.join(folder, f"{saved:04d}.jpg")
                with open(path, "wb") as f:
                    f.write(r.content)

                    rows_meta.append({
                        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "url": url,
                        "filename": f"{saved:04d}.jpg",
                        "class": class_label,
                    })

                saved += 1
                if saved % 50 == 0:
                    print(f"  {class_label}: {saved}/{total}")
            if new == 0:
                break
            page += 1
            time.sleep(1.2)

    return rows_meta


def append_metadata(rows, csv_path):
    write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=META_COLS)
        if write_header:
            w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    csv_path = "./metadata.csv"
    queries = {"rose": "rose flower", "tulip": "tulip flower"}
    for class_label, query in queries.items():
        rows = download_images(query, class_label, f"dataset/{class_label}")
        append_metadata(rows, csv_path)
