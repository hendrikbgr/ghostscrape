import itertools
import httpx
import logging
from typing import Optional
import asyncio

class ProxyManager:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.proxies: list[str] = []
        self.proxy_cycle = itertools.cycle([])
        self.lock = asyncio.Lock()

    async def load_proxies(self, limit: int = 20):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://proxy-pool-api.vercel.app/api/get_proxy", params={
                    "api_key": self.api_key,
                    "limit": limit
                }, timeout=10.0)
                resp.raise_for_status()
                data = resp.json()
                
                if "proxy" in data:
                    new_proxies = [data["proxy"]]
                else:
                    new_proxies = data.get("proxies", [])
                
                async with self.lock:
                    if new_proxies:
                        extracted = []
                        for p in new_proxies:
                            if isinstance(p, dict):
                                if "proxy" in p:
                                    extracted.append(p["proxy"])
                                elif "ip_port" in p:
                                    extracted.append(p["ip_port"])
                                else:
                                    extracted.append(str(p))
                            else:
                                extracted.append(str(p))
                        
                        self.proxies.extend(extracted)
                        self.proxy_cycle = itertools.cycle(self.proxies)
        except Exception as e:
            logging.error(f"Failed to load proxies: {e}")

    async def get_proxy(self) -> Optional[str]:
        async with self.lock:
            empty = not self.proxies
        
        if empty:
            await self.load_proxies(10)
            
        async with self.lock:
            try:
                return next(self.proxy_cycle)
            except StopIteration:
                return None

    async def ban_proxy(self, proxy: str):
        async with self.lock:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                if self.proxies:
                    self.proxy_cycle = itertools.cycle(self.proxies)
                else:
                    self.proxy_cycle = itertools.cycle([])
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post("https://proxy-pool-api.vercel.app/api/ban_proxy", json={
                    "api_key": self.api_key,
                    "proxy_ips": proxy,
                }, timeout=10.0)
        except Exception as e:
            logging.error(f"Failed to ban proxy {proxy}: {e}")
