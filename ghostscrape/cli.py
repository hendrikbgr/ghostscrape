import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, DownloadColumn, TextColumn, BarColumn, TimeElapsedColumn
import asyncio
from dotenv import load_dotenv
load_dotenv()

from ghostscrape.ingestion import build_queue
from ghostscrape.models import Job
from ghostscrape.proxy_manager import ProxyManager
from ghostscrape.engine import ScraperEngine

app = typer.Typer(help="GhostScrape: A hyper-concurrent, anti-blocking CLI scraper.")
console = Console()

@app.command()
def run(
    target: str = typer.Option(..., "--target", "-t", help="Target URL or sitemap.xml to scrape."),
    concurrency: int = typer.Option(50, "--concurrency", "-c", help="Number of concurrent workers."),
    api_key: str = typer.Option(..., envvar="PROXY_API_KEY", help="Proxy pool API key.")
):
    console.print(f"[bold green]Starting GhostScrape[/bold green] on [cyan]{target}[/cyan]")
    console.print(f"Concurrency: [yellow]{concurrency}[/yellow]")
    
    urls = build_queue(target)
    console.print(f"Found [magenta]{len(urls)}[/magenta] targets.")
    
    if not urls:
        console.print("[red]No URLs found. Exiting.[/red]")
        raise typer.Exit()
        
    jobs = [Job(url=u) for u in urls]
    
    pm = ProxyManager(api_key=api_key)
    
    async def _main():
        await pm.load_proxies(20)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TextColumn(" | Banned: [red]{task.fields[banned]}[/red]"),
            TextColumn(" | Saved: [green]{task.fields[saved]}[/green]"),
            console=console
        ) as progress:
            task_id = progress.add_task(f"Scraping", total=len(jobs), banned=0, saved=0)
            
            engine = ScraperEngine(
                jobs=jobs,
                proxy_manager=pm,
                concurrency=concurrency,
                progress=progress,
                task_id=task_id
            )
            await engine.run()
    
    asyncio.run(_main())
