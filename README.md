<p align="center">
  <img src="https://media.giphy.com/media/aTf4PONtSYBCE/giphy.gif" alt="GhostScrape Logo" width="120">
</p>

<h1 align="center">👻 GhostScrape</h1>

<p align="center">
  <strong>A hyper-concurrent, anti-blocking CLI tool that turns any website or sitemap into clean, LLM-ready Markdown.</strong><br>
  Built for RAG pipelines, powered by an infinite proxy pool.
</p>

<p align="center">
  <a href="https://python.org">
    <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python Versions">
  </a>
  <a href="https://python-poetry.org/">
    <img src="https://img.shields.io/badge/managed%20by-Poetry-blue" alt="Poetry">
  </a>
  <a href="https://github.com/hendrikbgr/ghostscrape/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  </a>
  <a href="https://github.com/hendrikbgr/ghostscrape/pulls">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat" alt="PRs Welcome">
  </a>
</p>

<br>

<p align="center">
  <img src="https://media.giphy.com/media/yx400dIdkwWdsCgWYp/giphy.gif" alt="Let me in meme" height="200">
</p>

<p align="center">
  <em>Because feeding raw HTML to your LLM is a war crime, and Cloudflare doesn't want you to have the text.</em>
</p>

---

## 📖 Table of Contents

- [The Killer Use Case](#-the-killer-use-case)
- [Architecture & Evasion](#-architecture--evasion)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 The Killer Use Case

Developers building Retrieval-Augmented Generation (RAG) applications face two massive hurdles:

1. **The Context Window Limits:** If you feed raw HTML to an LLM, 70% of your prompt tokens are wasted on `<div>`, `<script>`, and CSS classes. You need pure semantic text or Markdown.
2. **The Cloudflare Wall:** Aggressively scraping documentation sites, forums, or news outlets to build your dataset will inevitably trigger a `403 Forbidden` WAF block or an IP ban within minutes.

**GhostScrape elegantly solves both.** 
Feed it a target (`https://docs.docker.com/sitemap.xml`), and it orchestrates hundreds of asynchronous workers. Each worker perfectly cleanly extracts the core article text, ignores ads and navigation menus via `trafilatura`, and writes pristine `.md` files directly to your output directory.

When sites fight back? GhostScrape dynamically weaves through its proxy pool, testing multiple IPs concurrently until it penetrates the block.

---

## ⚡ Architecture & Evasion

GhostScrape is designed from the ground up to never stall and never get permanently blocked.

<p align="center">
  <img src="https://media.giphy.com/media/eIm624c8nnNbiG0V3g/giphy.gif" alt="matrix dodging bullets" height="180">
  <br><em>Workers spinning up concurrent proxies to bypass WAF challenges.</em>
</p>

- 🏎️ **Concurrent Proxy Racing:** For every URL, GhostScrape launches **5 simultaneous asynchronous requests** utilizing 5 different proxies. The first proxy to successfully download the page "wins", and all slower/failing requests are instantly cancelled to free up resources.
- 🧲 **Sticky Proxies:** When a worker finds a proxy that penetrates a firewall, it immediately caches it locally. Future URLs processed by that worker bypass the 5-proxy race entirely, routing directly through the "known good" proxy to scrape at maximum velocity!
- 🛡️ **Auto-Banning & Rotation:** If a proxy is caught and throws a `403 Forbidden` or `429 Too Many Requests`, GhostScrape communicates with your Proxy Pool API to ban that IP permanently, ensuring workers never waste time on burnt addresses.
- 🎭 **Fingerprint Randomization:** Every single request is paired with a randomized, real-world browser `User-Agent` to trick basic bot mitigation scripts.
- 🤖 **Playwright SPA Fallback:** If GhostScrape encounters a heavily JavaScript-hydrated application (like React/Next.js) resulting in an empty payload shell, it instantly spins up a headless Chromium browser through the verified proxy to execute the JS and extract the true semantic text.
- 🏷️ **LLM Metadata Injection:** Every extracted `.md` file is automatically prepended with clean YAML Frontmatter (containing the origin URL, domain, and ISO timestamp) to generate perfectly structured citations for your RAG Vector Databases.

---

## 📦 Installation

<img src="https://media.giphy.com/media/13HgwGsXF0aiGY/giphy.gif" alt="fast typer hacker meme" width="180" align="right">

GhostScrape uses [Poetry](https://python-poetry.org/) to maintain a deterministic and isolated development environment.

### Prerequisites
- Python 3.10 or higher.
- [Poetry](https://python-poetry.org/docs/#installation) installed on your system.

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/hendrikbgr/ghostscrape.git
cd ghostscrape

# 2. Install dependencies via Poetry
poetry install

# 3. Install Headless Chromium (for SPA fallback rendering)
poetry run playwright install chromium
```

---

## 🚀 Usage

GhostScrape is invoked via a beautiful CLI backed by `Typer` and `Rich`.

### Scrape a Full Website via Sitemap

Automatically parse an XML sitemap and concurrently download every single page:

```bash
ghostscrape --target https://docs.docker.com/sitemap.xml --concurrency 50
```

*(Note: Typer intelligently handles the commands behind the scenes!)*

### Scrape a Tricky Single Page

Target heavily protected, heavily JavaScript-reliant pages:

```bash
gs --target https://news.ycombinator.com/ --concurrency 1
```

### Output 📂

Every successfully extracted article is intelligently stored under its respective domain folder:

```text
output/
└── docs.docker.com/
    ├── engine-install.md
    ├── get-started.md
    └── build-guide.md
```

---

## ⚙️ Configuration

GhostScrape relies on the *v-proxy-pool* API to provide an infinite stream of pristine rotating proxies. 

**To use GhostScrape, you must first create a free account and generate an API key here:**
👉 **[proxy-pool-api.vercel.app](https://proxy-pool-api.vercel.app/)**

Once you have your key, GhostScrape automatically loads credentials from a `.env` file!

Simply rename `.env.example` to `.env` and drop your key in:

```env
PROXY_API_KEY=your_api_key_here
```

To run with a custom API key bypassing the `.env` temporarily:
```bash
ghostscrape --target https://example.com --api-key "your_api_key_here"
```

*(Note: GhostScrape currently integrates natively with the Vercel Proxy Pool API for dynamic IP streaming and endpoint banning).*

---

## 🛠 Tech Stack

- **[HTTPX](https://www.python-httpx.org/) & [Asyncio](https://docs.python.org/3/library/asyncio.html):** For hyper-concurrent, non-blocking network I/O.
- **[Trafilatura](https://trafilatura.readthedocs.io/):** For State-of-the-Art HTML noise stripping and semantic Markdown extraction.
- **[BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/):** As a raw text fallback for aggressive Single Page Applications.
- **[Typer](https://typer.tiangolo.com/) & [Rich](https://rich.readthedocs.io/):** Supplying the aesthetic, responsive CLI dashboard and live terminal updates.

---

## 🤝 Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

<br>

<p align="center">
  <b>If this tool helps you build the ultimate RAG dataset, give the repo a ⭐️!</b>
</p>
