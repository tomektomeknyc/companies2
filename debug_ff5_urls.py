import requests
import re
from bs4 import BeautifulSoup

import requests
from bs4 import BeautifulSoup
import re

def fetch_ff5_urls() -> dict[str, str]:
    URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
    resp = requests.get(URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) Find the Developed Markets header
    header = soup.find(lambda tag: tag.name in ("h3","b")
                               and "Developed Markets Factors and Returns" in tag.get_text())
    if not header:
        raise RuntimeError("Could not find Developed Markets header")

    urls: dict[str,str] = {}
    # 2) Process every <a> until we hit “Emerging Markets”
    for link in header.find_all_next("a", href=re.compile(r"CSV\.zip$")):
        block_text = link.parent.get_text(" ", strip=True)
        # stop when we reach Emerging Markets section
        if "Emerging Markets Factors and Returns" in block_text:
            break
        # only 5-factor files, skip daily
        if "5 Factors" not in block_text or "Daily" in block_text:
            continue

        # chop off “TXT CSV Details” etc
        region = re.sub(r"\s+TXT.*$", "", block_text)
        href = link["href"]
        if href.startswith("/"):
            href = "https://mba.tuck.dartmouth.edu" + href
        urls[region] = href

    return urls
if __name__ == "__main__":
    urls = fetch_ff5_urls()
    print("✅ Scraped FF5 regions & URLs:")
    for region, url in urls.items():
        print(f"  • {region!r} → {url}")
    print(f"\nTotal regions scraped: {len(urls)}")
