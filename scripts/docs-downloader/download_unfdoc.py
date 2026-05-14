#!/usr/bin/env python3
"""Download unfdoc (1C:УНФ) documentation from ITS and convert to clean text.

Unlike v851doc/bsp321doc/edtdoc which use /content/NN/hdoc?bus → JSON src,
unfdoc uses /bookmark/unf/UNFxxxxxx URLs. Flow per URL:
  1. Fetch bookmark HTML.
  2. Extract <iframe id="w_metadata_doc_frame" src="..."> — path to actual content.
  3. Fetch content with bookmark URL as referrer.
  4. Convert HTML → clean text → save.

Uses -b SESSION only (no -c) so ITS cannot overwrite our carefully crafted
authenticated session with an anonymous one.
"""

import os
import re
import time
import subprocess
import urllib.parse
from html import unescape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

DOCS_DIR = os.path.join(REPO_ROOT, "docs", "unfdoc")
BASE = "https://its.1c.ru"
URLS_FILE = os.path.join(SCRIPT_DIR, "unfdoc_urls.txt")
SESSION = os.path.join(SCRIPT_DIR, "_session.txt")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0"

os.environ["MSYS_NO_PATHCONV"] = "1"
os.makedirs(DOCS_DIR, exist_ok=True)


def curl(url, referrer=None):
    cmd = ["curl", "-sL", "-A", UA, "-b", SESSION]
    if referrer:
        cmd += ["-e", referrer]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    return r.stdout


def decode(data):
    try:
        return data.decode("windows-1251")
    except Exception:
        return data.decode("utf-8", errors="replace")


def html_to_text(html):
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.DOTALL | re.IGNORECASE)

    for i in range(1, 7):
        prefix = "#" * i
        text = re.sub(rf"<h{i}[^>]*>(.*?)</h{i}>", rf"\n\n{prefix} \1\n\n", text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r"<br[^>]*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</t[dh]>", "\t", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = text.replace("\xa0", " ")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_filename(name, max_len=120):
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_len]


def main():
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    total = len(urls)
    print(f"Total URLs: {total}\nOutput: {DOCS_DIR}\n")

    ok = err = restricted = no_src = 0

    for i, url_path in enumerate(urls, 1):
        m = re.search(r"/unf/([A-Z]+\d+)$", url_path)
        if not m:
            err += 1
            continue
        bookmark_id = m.group(1)

        try:
            bookmark_url = f"{BASE}{url_path}"
            bookmark_html = decode(curl(bookmark_url))

            if not bookmark_html or len(bookmark_html) < 500:
                print(f"[{i}/{total}] ERROR {bookmark_id} (bookmark short: {len(bookmark_html)})")
                err += 1
                continue

            iframe_match = re.search(
                r'<iframe[^>]*id="w_metadata_doc_frame"[^>]*src="([^"]+)"',
                bookmark_html,
            )
            if not iframe_match:
                print(f"[{i}/{total}] NO_SRC {bookmark_id}")
                no_src += 1
                continue

            src = iframe_match.group(1).replace("&amp;", "&")
            encoded_src = urllib.parse.quote(src, safe="/:?=&")

            content_bytes = curl(f"{BASE}{encoded_src}", referrer=bookmark_url)
            content_html = decode(content_bytes)

            if not content_html or len(content_html) < 500:
                print(f"[{i}/{total}] ERROR {bookmark_id} (content short: {len(content_html)})")
                err += 1
                continue

            if "Доступ к данному материалу ограничен" in content_html:
                print(f"[{i}/{total}] RESTRICTED {bookmark_id}")
                restricted += 1
                continue

            title_match = re.search(r"<title[^>]*>([^<]+)", content_html)
            title = unescape(title_match.group(1)) if title_match else bookmark_id
            title = re.sub(r"\s*::.*$", "", title).strip()

            clean = html_to_text(content_html)

            filename = f"{bookmark_id}_{safe_filename(title)}.txt".replace(" ", "_")
            filepath = os.path.join(DOCS_DIR, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n")
                f.write(f"# Source: {bookmark_url}\n")
                f.write(f"# Iframe: {src}\n\n")
                f.write(clean)
                f.write("\n")

            print(f"[{i}/{total}] OK {bookmark_id}: {title[:60]} ({len(clean)} chars)")
            ok += 1

        except Exception as e:
            print(f"[{i}/{total}] ERROR {bookmark_id}: {e}")
            err += 1

        time.sleep(0.2)

    print(f"\n=== Done: OK={ok}, Restricted={restricted}, NoSrc={no_src}, Errors={err}, Total={total} ===")


if __name__ == "__main__":
    main()
