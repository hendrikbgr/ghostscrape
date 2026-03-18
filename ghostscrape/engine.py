import asyncio
import httpx
from urllib.parse import urlparse
import re
from pathlib import Path
from fake_useragent import UserAgent
import trafilatura
from rich.progress import Progress
import typing
from datetime import datetime, timezone

from .models import Job
from .proxy_manager import ProxyManager

class ScraperEngine:
    def __init__(self, jobs: typing.List[Job], proxy_manager: ProxyManager, concurrency: int, progress: Progress, task_id):
        self.queue = asyncio.Queue()
        for job in jobs:
            self.queue.put_nowait(job)
        self.proxy_manager = proxy_manager
        self.concurrency = concurrency
        self.ua = UserAgent()
        self.progress = progress
        self.task_id = task_id
        
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        
        self.banned_proxies = 0
        self.files_saved = 0
        self.lock = asyncio.Lock()
        self.engine_stopped = False

    def _slugify(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path
        if not path or path == "/":
            path = "index"
        else:
            path = path.strip("/")
        
        slug = re.sub(r'[^a-zA-Z0-9_\-]', '-', path)
        return slug

    def _get_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc

    async def _try_single_proxy(self, url: str, proxy_url: str) -> str:
        proxy_arg = f"http://{proxy_url}"
        headers = {"User-Agent": self.ua.random}
        try:
            async with httpx.AsyncClient(proxy=proxy_arg, verify=False, timeout=15.0) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code in (403, 429):
                    raise Exception(f"HTTP {response.status_code}")
                response.raise_for_status()
                return response.text
        except Exception as e:
            raise e

    async def _playwright_fallback(self, url: str, proxy_url: str) -> str | None:
        from playwright.async_api import async_playwright
        try:
            async with async_playwright() as p:
                proxy_settings = {"server": f"http://{proxy_url}"} if proxy_url else None
                browser = await p.chromium.launch(proxy=proxy_settings, headless=True)
                page = await browser.new_page(user_agent=self.ua.random)
                await page.goto(url, wait_until="networkidle", timeout=15000)
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            import os
            if os.environ.get("DEBUG"):
                print(f"Playwright fallback failed for {url}: {e}")
            return None

    async def _try_proxy(self, url: str) -> tuple[str, str | None]:
        proxy_url = await self.proxy_manager.get_proxy()
        if not proxy_url:
            self.engine_stopped = True
            raise Exception("OUT_OF_PROXIES")
            
        proxy_arg = f"http://{proxy_url}" if proxy_url else None

        headers = {
            "User-Agent": self.ua.random
        }

        try:
            async with httpx.AsyncClient(proxy=proxy_arg, verify=False, timeout=15.0) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                
                if response.status_code in (403, 429):
                    if proxy_url:
                        await self.proxy_manager.ban_proxy(proxy_url)
                        async with self.lock:
                            self.banned_proxies += 1
                            self.progress.update(self.task_id, banned=self.banned_proxies)
                    raise Exception(f"HTTP {response.status_code}")
                
                response.raise_for_status()
                return response.text, proxy_url
                
        except Exception as e:
            print(f"Fetch failed for {url} via proxy {proxy_url}: {type(e).__name__} - {e}")
            if proxy_url:
                await self.proxy_manager.ban_proxy(proxy_url)
                async with self.lock:
                    self.banned_proxies += 1
                    self.progress.update(self.task_id, banned=self.banned_proxies)
            raise e

    async def _fetch(self, job: Job, working_proxy: str | None) -> str | None:
        if self.engine_stopped:
            return None

        success_content = None
        proxy_used = None

        # 1. Try the known working proxy first
        if working_proxy:
            try:
                content = await self._try_single_proxy(job.url, working_proxy)
                success_content = content
                proxy_used = working_proxy
            except Exception as e:
                print(f"Working proxy {working_proxy} failed for {job.url}: {type(e).__name__} - {e}")
                await self.proxy_manager.ban_proxy(working_proxy)
                async with self.lock:
                    self.banned_proxies += 1
                    self.progress.update(self.task_id, banned=self.banned_proxies)
                working_proxy = None

        # 2. If no working proxy, race 5 new proxies
        if not success_content:
            tasks = [asyncio.create_task(self._try_proxy(job.url)) for _ in range(5)]
            
            for coro in asyncio.as_completed(tasks):
                try:
                    content, proxy_winner = await coro
                    success_content = content
                    proxy_used = proxy_winner
                    
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    break
                except Exception:
                    pass
                
        # 3. Process success or requeue
        if success_content:
            markdown = trafilatura.extract(success_content)
            
            # Playwright Headless Fallback for heavy JS SPAs
            if (not markdown or len(markdown.strip()) < 150) and proxy_used:
                pw_content = await self._playwright_fallback(job.url, proxy_used)
                if pw_content:
                    markdown = trafilatura.extract(pw_content)
                    if not markdown:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(pw_content, "html.parser")
                        markdown = soup.get_text(separator="\n\n", strip=True)

            # Standard BS4 text fallback if still empty
            if not markdown:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(success_content, "html.parser")
                markdown = soup.get_text(separator="\n\n", strip=True)

            if markdown:
                domain = self._get_domain(job.url)
                
                # Inject YAML Frontmatter Metadata
                timestamp = datetime.now(timezone.utc).isoformat()
                frontmatter = f"---\nurl: {job.url}\ndomain: {domain}\nscraped_at: {timestamp}\n---\n\n"
                final_markdown = frontmatter + markdown

                slug = self._slugify(job.url)
                domain_dir = self.output_dir / domain
                domain_dir.mkdir(exist_ok=True)
                
                file_path = domain_dir / f"{slug}.md"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(final_markdown)
                
                async with self.lock:
                    self.files_saved += 1
                    self.progress.update(self.task_id, saved=self.files_saved, advance=1)
            else:
                self.progress.update(self.task_id, advance=1)
            return proxy_used
        else:
            if not self.engine_stopped:
                job.retry_count += 1
                await self.queue.put(job)
            return None

    async def _worker(self):
        current_proxy = None
        while not self.queue.empty():
            if self.engine_stopped:
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    pass
                continue

            try:
                job = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            
            new_proxy = await self._fetch(job, current_proxy)
            if new_proxy:
                current_proxy = new_proxy
            else:
                current_proxy = None
                
            self.queue.task_done()

    async def run(self):
        workers = [asyncio.create_task(self._worker()) for _ in range(self.concurrency)]
        await asyncio.gather(*workers)
