#!/usr/bin/env python3
"""
Perpetual Funding Rate Dashboard
Aggregates funding rates from Hyperliquid, Lighter, Aevo, dYdX
Auto-refreshes on startup
"""
import asyncio
import sys
from datetime import datetime
from typing import Dict, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

from funding_fetchers import FundingAggregator, FundingRate


console = Console()


def create_exchange_table(exchange: str, rates: List[FundingRate], top_n: int = 15) -> Table:
    """Create a table for a single exchange's funding rates"""
    table = Table(
        title=f"[bold cyan]{exchange}[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        title_justify="left",
    )

    table.add_column("Symbol", style="cyan", width=12)
    table.add_column("Funding Rate", justify="right", width=14)
    table.add_column("APR", justify="right", width=10)

    # Sort by absolute funding rate
    sorted_rates = sorted(rates, key=lambda x: abs(x.funding_rate), reverse=True)[:top_n]

    for rate in sorted_rates:
        # Color code the funding rate
        fr = rate.funding_rate
        if fr > 0.01:
            color = "green"
        elif fr < -0.01:
            color = "red"
        else:
            color = "white"

        # Calculate annualized rate
        intervals_per_year = (365 * 24) / rate.interval_hours
        apr = fr * intervals_per_year

        table.add_row(
            rate.symbol,
            f"[{color}]{fr:+.4f}%[/{color}]",
            f"[{color}]{apr:+.1f}%[/{color}]"
        )

    if not rates:
        table.add_row("[dim]No data[/dim]", "-", "-")

    return table


def create_comparison_table(all_rates: Dict[str, List[FundingRate]], symbols: List[str] = None) -> Table:
    """Create a comparison table showing same symbol across exchanges"""
    table = Table(
        title="[bold yellow]Cross-Exchange Comparison (Top Symbols)[/bold yellow]",
        box=box.DOUBLE,
        show_header=True,
        header_style="bold white",
    )

    # Get all exchanges
    exchanges = list(all_rates.keys())
    table.add_column("Symbol", style="cyan bold", width=10)
    for ex in exchanges:
        table.add_column(ex, justify="right", width=12)
    table.add_column("Spread", justify="right", style="yellow", width=10)

    # Find common symbols or top symbols
    symbol_data = {}
    for exchange, rates in all_rates.items():
        for rate in rates:
            symbol = rate.symbol.replace("-PERP", "").replace("-USD", "").replace("USDT", "").replace("/", "")
            if symbol not in symbol_data:
                symbol_data[symbol] = {}
            symbol_data[symbol][exchange] = rate.funding_rate

    # Select symbols with data from multiple exchanges or high funding
    target_symbols = symbols or ["BTC", "ETH", "SOL", "ARB", "DOGE", "PEPE", "WIF", "AVAX"]

    for symbol in target_symbols:
        if symbol in symbol_data:
            row = [symbol]
            values = []
            for ex in exchanges:
                if ex in symbol_data[symbol]:
                    fr = symbol_data[symbol][ex]
                    values.append(fr)
                    color = "green" if fr > 0.01 else "red" if fr < -0.01 else "white"
                    row.append(f"[{color}]{fr:+.4f}%[/{color}]")
                else:
                    row.append("[dim]-[/dim]")

            # Calculate spread if multiple values
            if len(values) >= 2:
                spread = max(values) - min(values)
                row.append(f"{spread:.4f}%")
            else:
                row.append("-")

            table.add_row(*row)

    return table


def create_dashboard(all_rates: Dict[str, List[FundingRate]]) -> Layout:
    """Create the full dashboard layout"""
    layout = Layout()

    # Create header
    header_text = Text()
    header_text.append("🚀 Perpetual Funding Rate Dashboard\n", style="bold cyan")
    header_text.append(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")

    header = Panel(header_text, box=box.DOUBLE)

    # Create exchange panels
    exchange_tables = []
    for exchange, rates in all_rates.items():
        exchange_name = exchange.replace("Hyperliquid", "Hyperliquid").replace("Lighter", "Lighter")
        exchange_tables.append(create_exchange_table(exchange_name, rates))

    # Create comparison table
    comparison = create_comparison_table(all_rates)

    return header, exchange_tables, comparison


async def run_dashboard(auto_refresh: bool = True, refresh_interval: int = 60):
    """Main dashboard runner"""
    aggregator = FundingAggregator()

    console.clear()
    console.print(Panel.fit(
        "[bold cyan]🚀 Perpetual Funding Rate Dashboard[/bold cyan]\n"
        "[dim]Fetching data from Hyperliquid, Lighter, Aevo, dYdX...[/dim]",
        box=box.DOUBLE
    ))

    try:
        while True:
            # Fetch all data
            console.print("\n[yellow]⏳ Fetching funding rates...[/yellow]")
            all_rates = await aggregator.fetch_all()

            console.clear()

            # Print header
            console.print(Panel.fit(
                "[bold cyan]🚀 Perpetual Funding Rate Dashboard[/bold cyan]\n"
                f"[dim]Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]\n"
                "[dim]Press Ctrl+C to exit[/dim]",
                box=box.DOUBLE
            ))
            console.print()

            # Print exchange tables side by side if terminal is wide enough
            tables = []
            for exchange, rates in all_rates.items():
                table = create_exchange_table(exchange, rates, top_n=10)
                tables.append(table)

            # Print tables
            if console.width >= 120 and len(tables) >= 2:
                # Print in pairs
                for i in range(0, len(tables), 2):
                    if i + 1 < len(tables):
                        console.print(tables[i], tables[i + 1], justify="center")
                    else:
                        console.print(tables[i])
                    console.print()
            else:
                for table in tables:
                    console.print(table)
                    console.print()

            # Print comparison table
            console.print(create_comparison_table(all_rates))

            # Summary stats
            total_pairs = sum(len(rates) for rates in all_rates.values())
            active_exchanges = sum(1 for rates in all_rates.values() if rates)
            console.print(f"\n[dim]Total pairs: {total_pairs} | Active exchanges: {active_exchanges}/{len(all_rates)}[/dim]")

            if not auto_refresh:
                break

            # Wait for next refresh
            console.print(f"\n[dim]Refreshing in {refresh_interval} seconds... (Ctrl+C to exit)[/dim]")
            await asyncio.sleep(refresh_interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
    finally:
        await aggregator.close_all()


def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Perpetual Funding Rate Dashboard")
    parser.add_argument("--no-refresh", action="store_true", help="Disable auto-refresh")
    parser.add_argument("--interval", type=int, default=60, help="Refresh interval in seconds")

    args = parser.parse_args()

    asyncio.run(run_dashboard(
        auto_refresh=not args.no_refresh,
        refresh_interval=args.interval
    ))


if __name__ == "__main__":
    main()
