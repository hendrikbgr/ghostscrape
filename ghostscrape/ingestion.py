import httpx
from bs4 import BeautifulSoup
from typing import List

def _fetch_sitemap(url: str, depth: int = 0) -> List[str]:
    # Prevent infinite recursion loop on cyclical sitemaps
    if depth > 3:
        return []
    
    urls = []
    try:
        # We must explicitly follow redirects for massive hubs like LangChain
        resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "xml")
        
        # Check if the root element implies nested sitemaps
        is_index = soup.find("sitemapindex") is not None
        
        locs = soup.find_all("loc")
        for loc in locs:
            child_url = loc.text.strip()
            if not child_url:
                continue
                
            # If the loc points to another sitemap, recursively dive into it
            if is_index or child_url.endswith(".xml"):
                urls.extend(_fetch_sitemap(child_url, depth + 1))
            else:
                urls.append(child_url)
                
    except Exception as e:
        print(f"Error fetching/parsing sitemap {url}: {e}")
        
    return urls

def build_queue(target_url: str) -> List[str]:
    """Builds a flat list of URLs whether given a single page, flat sitemap, or nested sitemap index."""
    if target_url.endswith(".xml"):
        return _fetch_sitemap(target_url)
    else:
        return [target_url]
