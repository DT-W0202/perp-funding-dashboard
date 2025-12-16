"""
Perpetual Funding Rate Dashboard

实时聚合多个永续合约交易所的资费率数据。

支持的交易所:
- Hyperliquid - 1小时资费周期
- Lighter - 1小时资费周期
- Aster - 8小时资费周期

使用方法:
    # Web 看板
    streamlit run web_dashboard.py

    # CLI 看板
    python dashboard.py
"""

from .funding_fetchers import (
    FundingRate,
    FundingAggregator,
    HyperliquidFetcher,
    LighterFetcher,
    AsterFetcher,
)

__version__ = "1.0.0"
__all__ = [
    "FundingRate",
    "FundingAggregator",
    "HyperliquidFetcher",
    "LighterFetcher",
    "AsterFetcher",
]
