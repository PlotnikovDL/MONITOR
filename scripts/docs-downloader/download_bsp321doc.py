#!/usr/bin/env python3
"""Download bsp321doc documentation from ITS (authenticated) and convert to clean text."""

import os
import re
import time
import subprocess
import urllib.parse
from html import unescape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

DOCS_DIR = os.path.join(REPO_ROOT, "docs", "bsp321doc")
BASE = "https://its.1c.ru"
URLS_FILE = os.path.join(SCRIPT_DIR, "bsp321doc_urls.txt")
SESSION = os.path.join(SCRIPT_DIR, "_session.txt")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0"

os.environ["MSYS_NO_PATHCONV"] = "1"
os.makedirs(DOCS_DIR, exist_ok=True)


def curl(url, referrer=None, extra_headers=None):
    cmd = ["curl", "-sL", "-A", UA, "-b", SESSION, "-c", SESSION]
    if referrer:
        cmd += ["-e", referrer]
    if extra_headers:
        for h in extra_headers:
            cmd += ["-H", h]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    try:
        return r.stdout.decode("windows-1251")
    except:
        return r.stdout.decode("utf-8", errors="replace")


def html_to_text(html):
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.DOTALL | re.IGNORECASE)

    for i in range(1, 7):
        prefix = '#' * i
        text = re.sub(rf'<h{i}[^>]*>(.*?)</h{i}>', rf'\n\n{prefix} \1\n\n', text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r'<br[^>]*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</tr>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</t[dh]>', '\t', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '- ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = text.replace('\xa0', ' ')

    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def safe_filename(name, max_len=120):
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len]


def main():
    with open(URLS_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    total = len(urls)
    print(f"Total content pages: {total}\nOutput: {DOCS_DIR}\n")

    ok = err = restricted = 0

    for i, url_path in enumerate(urls, 1):
        m = re.search(r'/content/(\d+)/hdoc', url_path)
        if not m:
            err += 1
            continue
        doc_id = m.group(1)

        try:
            bus_text = curl(f"{BASE}{url_path}?bus",
                            extra_headers=["X-Requested-With: XMLHttpRequest"])
            src_match = re.search(r'"src":"([^"]*\.htm)"', bus_text)
            if not src_match:
                print(f"[{i}/{total}] SKIP doc_id={doc_id} (no iframe)")
                err += 1
                continue

            iframe_src = src_match.group(1).replace('\\/', '/')
            encoded_src = urllib.parse.quote(iframe_src, safe='/:')
            html = curl(f"{BASE}{encoded_src}", referrer=f"{BASE}{url_path}")

            if not html or len(html) < 500:
                print(f"[{i}/{total}] ERROR doc_id={doc_id} (short {len(html)})")
                err += 1
                continue

            if "Доступ к данному материалу ограничен" in html:
                print(f"[{i}/{total}] RESTRICTED doc_id={doc_id}")
                restricted += 1
                continue

            title_match = re.search(r'<title>([^<]*)', html)
            title = unescape(title_match.group(1)) if title_match else f"doc_{doc_id}"
            title = re.sub(r'\s*::.*$', '', title).strip()

            clean = html_to_text(html)

            filename = f"{int(doc_id):04d}_{safe_filename(title)}.txt".replace(" ", "_")
            filepath = os.path.join(DOCS_DIR, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# {title}\n")
                f.write(f"# Source: {BASE}{url_path}\n\n")
                f.write(clean)
                f.write('\n')

            print(f"[{i}/{total}] OK: {title[:70]} ({len(clean)} chars)")
            ok += 1

        except Exception as e:
            print(f"[{i}/{total}] ERROR doc_id={doc_id}: {e}")
            err += 1

        time.sleep(0.2)

    print(f"\n=== Done: OK={ok}, Restricted={restricted}, Errors={err}, Total={total} ===")


if __name__ == "__main__":
    main()
