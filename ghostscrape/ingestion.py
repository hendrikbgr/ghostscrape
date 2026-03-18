import httpx
from bs4 import BeautifulSoup

def build_queue(target_url: str) -> list[str]:
    urls = []
    if target_url.endswith(".xml"):
        # Parse XML sitemap
        try:
            resp = httpx.get(target_url, timeout=15.0)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "xml")
            locs = soup.find_all("loc")
            urls = [loc.text.strip() for loc in locs if loc.text]
        except Exception as e:
            print(f"Error fetching/parsing sitemap: {e}")
    else:
        urls.append(target_url)
    return urls
