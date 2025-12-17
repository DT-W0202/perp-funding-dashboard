"""
Funding rate fetchers for various perpetual exchanges
"""
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class FundingRate:
    exchange: str
    symbol: str
    funding_rate: float  # as percentage
    next_funding_time: Optional[datetime]
    interval_hours: int  # funding interval in hours
    open_interest: Optional[float] = None  # in USD
    volume_24h: Optional[float] = None  # in USD


class BaseFetcher:
    """Base class for funding rate fetchers"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch(self) -> List[FundingRate]:
        raise NotImplementedError


class HyperliquidFetcher(BaseFetcher):
    """Fetch funding rates from Hyperliquid"""

    BASE_URL = "https://api.hyperliquid.xyz/info"

    async def fetch(self) -> List[FundingRate]:
        session = await self.get_session()
        rates = []

        try:
            # Get all mids and funding rates
            async with session.post(
                self.BASE_URL,
                json={"type": "metaAndAssetCtxs"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    universe = data[0]["universe"]
                    asset_ctxs = data[1]

                    for i, asset in enumerate(universe):
                        if i < len(asset_ctxs):
                            ctx = asset_ctxs[i]
                            funding = float(ctx.get("funding", 0)) * 100  # Convert to percentage
                            # Get mark price for OI calculation
                            mark_px = float(ctx.get("markPx", 0))
                            oi_coins = float(ctx.get("openInterest", 0))
                            oi_usd = oi_coins * mark_px if mark_px else None
                            volume_24h = float(ctx.get("dayNtlVlm", 0)) if ctx.get("dayNtlVlm") else None

                            # Skip low volume (<10k) or low OI (<200k) markets
                            if volume_24h is None or volume_24h < 10000:
                                continue
                            if oi_usd is None or oi_usd < 200000:
                                continue

                            rates.append(FundingRate(
                                exchange="Hyperliquid",
                                symbol=asset["name"],
                                funding_rate=funding,
                                next_funding_time=None,
                                interval_hours=8,  # API returns 8-hour funding rate
                                open_interest=oi_usd,
                                volume_24h=volume_24h
                            ))
        except Exception as e:
            print(f"Error fetching Hyperliquid: {e}")

        return rates


class LighterFetcher(BaseFetcher):
    """Fetch funding rates from Lighter"""

    BASE_URL = "https://mainnet.zklighter.elliot.ai"

    async def fetch(self) -> List[FundingRate]:
        session = await self.get_session()
        rates = []

        try:
            # Get funding rates directly - the response includes symbol
            async with session.get(f"{self.BASE_URL}/api/v1/funding-rates") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("funding_rates", [])

                    # Group by symbol and get the "lighter" exchange rate (native rate)
                    symbol_rates = {}
                    for item in items:
                        exchange = item.get("exchange", "")
                        symbol = item.get("symbol", "")
                        rate = item.get("rate", 0)

                        # Prefer "lighter" exchange rates, fallback to first seen
                        if exchange == "lighter" or symbol not in symbol_rates:
                            symbol_rates[symbol] = rate

                    for symbol, funding in symbol_rates.items():
                        if funding and symbol:
                            rates.append(FundingRate(
                                exchange="Lighter",
                                symbol=symbol,
                                funding_rate=float(funding) * 100,
                                next_funding_time=None,
                                interval_hours=8  # Lighter uses 8-hour funding rate
                            ))
        except Exception as e:
            print(f"Error fetching Lighter: {e}")

        return rates


class AsterFetcher(BaseFetcher):
    """Fetch funding rates from Aster DEX"""

    BASE_URL = "https://fapi.asterdex.com"

    async def fetch(self) -> List[FundingRate]:
        session = await self.get_session()
        rates = []

        try:
            # Get funding rates from premiumIndex
            async with session.get(f"{self.BASE_URL}/fapi/v1/premiumIndex") as funding_resp:
                funding_data = {}
                if funding_resp.status == 200:
                    funding_list = await funding_resp.json()
                    for item in funding_list:
                        symbol = item.get("symbol", "")
                        funding_data[symbol] = {
                            "rate": float(item.get("lastFundingRate", 0)),
                            "mark_price": float(item.get("markPrice", 0))
                        }

            # Get 24h volume
            async with session.get(f"{self.BASE_URL}/fapi/v1/ticker/24hr") as vol_resp:
                vol_data = {}
                if vol_resp.status == 200:
                    vol_list = await vol_resp.json()
                    for item in vol_list:
                        symbol = item.get("symbol", "")
                        vol_data[symbol] = float(item.get("quoteVolume", 0))

            # Combine data
            for symbol, data in funding_data.items():
                funding_rate = data["rate"] * 100  # Convert to percentage
                volume_24h = vol_data.get(symbol, 0)

                # Skip low volume (<10k) markets
                if volume_24h < 10000:
                    continue

                # Clean symbol name
                clean_symbol = symbol.replace("USDT", "").replace("USD", "").replace("1000", "")

                rates.append(FundingRate(
                    exchange="Aster",
                    symbol=clean_symbol,
                    funding_rate=funding_rate,
                    next_funding_time=None,
                    interval_hours=4,  # Aster uses 4-hour funding
                    open_interest=None,  # Skip OI to avoid rate limits
                    volume_24h=volume_24h
                ))

        except Exception as e:
            print(f"Error fetching Aster: {e}")

        return rates


class DydxFetcher(BaseFetcher):
    """Fetch funding rates from dYdX v4"""

    BASE_URL = "https://indexer.dydx.trade"

    async def fetch(self) -> List[FundingRate]:
        session = await self.get_session()
        rates = []

        try:
            # dYdX v4 API - get all perpetual markets with funding rates
            async with session.get(f"{self.BASE_URL}/v4/perpetualMarkets") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    markets = data.get("markets", {})

                    for ticker, market in markets.items():
                        # Skip markets in final settlement
                        if market.get("status") == "FINAL_SETTLEMENT":
                            continue

                        funding = market.get("nextFundingRate", 0)
                        if funding:
                            # Get OI and volume - dYdX returns OI in base asset, need to convert
                            oracle_price = float(market.get("oraclePrice", 0))
                            oi_base = float(market.get("openInterest", 0))
                            oi_usd = oi_base * oracle_price if oracle_price else None
                            volume_24h = float(market.get("volume24H", 0)) if market.get("volume24H") else None

                            # Skip low volume (<10k) or low OI (<200k) markets
                            if volume_24h is None or volume_24h < 10000:
                                continue
                            if oi_usd is None or oi_usd < 200000:
                                continue

                            rates.append(FundingRate(
                                exchange="dYdX",
                                symbol=ticker.replace("-USD", ""),
                                funding_rate=float(funding) * 100,
                                next_funding_time=None,
                                interval_hours=1,
                                open_interest=oi_usd,
                                volume_24h=volume_24h
                            ))
        except Exception as e:
            print(f"Error fetching dYdX: {e}")

        return rates


class FundingAggregator:
    """Aggregate funding rates from multiple exchanges"""

    def __init__(self):
        self.fetchers = [
            HyperliquidFetcher(),
            LighterFetcher(),
            AsterFetcher(),
        ]

    async def fetch_all(self) -> Dict[str, List[FundingRate]]:
        """Fetch funding rates from all exchanges concurrently"""
        tasks = [fetcher.fetch() for fetcher in self.fetchers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        aggregated = {}
        for fetcher, result in zip(self.fetchers, results):
            exchange_name = fetcher.__class__.__name__.replace("Fetcher", "")
            if isinstance(result, Exception):
                print(f"Error from {exchange_name}: {result}")
                aggregated[exchange_name] = []
            else:
                aggregated[exchange_name] = result

        return aggregated

    async def close_all(self):
        """Close all HTTP sessions"""
        for fetcher in self.fetchers:
            await fetcher.close()
