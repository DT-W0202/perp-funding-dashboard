#!/usr/bin/env python3
"""
Perpetual Funding Rate Dashboard - Web Version
Run with: streamlit run web_dashboard.py
"""
import asyncio
import pandas as pd
import streamlit as st
from datetime import datetime
from funding_fetchers import FundingAggregator

st.set_page_config(
    page_title="Perp Funding Rates",
    page_icon="🚀",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stDataFrame { font-size: 14px; }
    .positive { color: #00ff00; }
    .negative { color: #ff4444; }
</style>
""", unsafe_allow_html=True)


def color_funding(val):
    """Color funding rates based on value"""
    try:
        num = float(str(val).replace('%', '').replace('+', '').replace(',', '').replace('$', '').replace('M', '').replace('K', ''))
        if num > 0.01:
            return 'color: #22c55e'
        elif num < -0.01:
            return 'color: #ef4444'
    except:
        pass
    return ''


def format_usd(val):
    """Format USD values with K/M suffix"""
    if val is None or val == 0:
        return "-"
    if val >= 1_000_000_000:
        return f"${val/1_000_000_000:.1f}B"
    elif val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    elif val >= 1_000:
        return f"${val/1_000:.1f}K"
    else:
        return f"${val:.0f}"


@st.cache_data(ttl=60)
def fetch_all_rates():
    """Fetch rates with caching"""
    async def _fetch():
        aggregator = FundingAggregator()
        try:
            return await aggregator.fetch_all()
        finally:
            await aggregator.close_all()

    return asyncio.run(_fetch())


def main():
    st.title("🚀 Perpetual Funding Rate Dashboard")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Controls row
    col_refresh, col_sort = st.columns([1, 3])

    with col_refresh:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    with col_sort:
        sort_option = st.radio(
            "Sort by:",
            ["Highest Rate (Short Opps)", "Lowest Rate (Long Opps)", "Absolute Value"],
            horizontal=True
        )

    # Fetch data
    with st.spinner("Fetching funding rates..."):
        all_rates = fetch_all_rates()

    # Display each exchange
    cols = st.columns(3)

    for i, (exchange, rates) in enumerate(all_rates.items()):
        with cols[i % 3]:
            st.subheader(exchange)

            if not rates:
                st.info("No data")
                continue

            # Sort based on user selection - use APR (annualized) for proper comparison across exchanges
            def get_apr(r):
                return r.funding_rate * (365 * 24 / r.interval_hours)

            if sort_option == "Highest Rate (Short Opps)":
                sorted_rates = sorted(rates, key=get_apr, reverse=True)
            elif sort_option == "Lowest Rate (Long Opps)":
                sorted_rates = sorted(rates, key=get_apr)
            else:  # Absolute Value
                sorted_rates = sorted(rates, key=lambda x: abs(get_apr(x)), reverse=True)

            # Create dataframe
            df = pd.DataFrame([
                {
                    "Symbol": r.symbol,
                    "Rate": f"{r.funding_rate:+.4f}%",
                    "APR": f"{r.funding_rate * (365 * 24 / r.interval_hours):+.1f}%",
                    "OI": format_usd(r.open_interest),
                    "Vol 24h": format_usd(r.volume_24h)
                }
                for r in sorted_rates
            ])

            # Style and display with scrollable height
            styled_df = df.style.map(color_funding, subset=['Rate', 'APR'])
            st.dataframe(styled_df, hide_index=True, use_container_width=True, height=400)

    # Cross-exchange comparison
    st.subheader("📊 Cross-Exchange Comparison (Sorted by Spread)")

    # Build comparison data for ALL symbols that appear on multiple exchanges
    symbol_data = {}
    for exchange, rates in all_rates.items():
        for rate in rates:
            symbol = rate.symbol.replace("-PERP", "").replace("-USD", "").replace("USDT", "").replace("/", "")
            if symbol not in symbol_data:
                symbol_data[symbol] = {}
            symbol_data[symbol][exchange] = rate.funding_rate

    # Create comparison table for symbols on 2+ exchanges
    comparison_rows = []
    exchanges = list(all_rates.keys())

    for symbol, exchange_rates in symbol_data.items():
        if len(exchange_rates) >= 2:  # Only show if on 2+ exchanges
            row = {"Symbol": symbol}
            values = list(exchange_rates.values())
            for ex in exchanges:
                if ex in exchange_rates:
                    val = exchange_rates[ex]
                    row[ex] = f"{val:+.4f}%"
                else:
                    row[ex] = "-"

            spread = max(values) - min(values)
            row["Spread"] = f"{spread:.4f}%"
            row["_spread_val"] = spread  # For sorting
            comparison_rows.append(row)

    if comparison_rows:
        # Sort by spread descending (best arb opportunities first)
        comparison_rows.sort(key=lambda x: x["_spread_val"], reverse=True)
        # Remove helper column and take top 20
        for row in comparison_rows:
            del row["_spread_val"]
        comp_df = pd.DataFrame(comparison_rows[:20])
        st.dataframe(comp_df, hide_index=True, use_container_width=True)

    # Top by OI and Volume section
    st.subheader("📈 Top Markets by Open Interest & Volume")

    col1, col2 = st.columns(2)

    # Aggregate all rates for OI/Volume ranking
    all_rates_flat = []
    for exchange, rates in all_rates.items():
        all_rates_flat.extend(rates)

    with col1:
        st.markdown("**Top 10 by Open Interest**")
        oi_sorted = sorted([r for r in all_rates_flat if r.open_interest], key=lambda x: x.open_interest or 0, reverse=True)[:10]
        if oi_sorted:
            oi_df = pd.DataFrame([
                {
                    "Symbol": r.symbol,
                    "Exchange": r.exchange,
                    "OI": format_usd(r.open_interest),
                    "Rate": f"{r.funding_rate:+.4f}%"
                }
                for r in oi_sorted
            ])
            st.dataframe(oi_df, hide_index=True, use_container_width=True)

    with col2:
        st.markdown("**Top 10 by 24h Volume**")
        vol_sorted = sorted([r for r in all_rates_flat if r.volume_24h], key=lambda x: x.volume_24h or 0, reverse=True)[:10]
        if vol_sorted:
            vol_df = pd.DataFrame([
                {
                    "Symbol": r.symbol,
                    "Exchange": r.exchange,
                    "Vol 24h": format_usd(r.volume_24h),
                    "Rate": f"{r.funding_rate:+.4f}%"
                }
                for r in vol_sorted
            ])
            st.dataframe(vol_df, hide_index=True, use_container_width=True)

    # Stats
    total_pairs = sum(len(rates) for rates in all_rates.values())
    active_exchanges = sum(1 for rates in all_rates.values() if rates)
    total_oi = sum(r.open_interest or 0 for r in all_rates_flat)
    total_vol = sum(r.volume_24h or 0 for r in all_rates_flat)

    st.caption(f"Total pairs: {total_pairs} | Active exchanges: {active_exchanges}/{len(all_rates)} | Total OI: {format_usd(total_oi)} | Total 24h Vol: {format_usd(total_vol)}")

    # Auto-refresh
    st.caption("Page auto-refreshes every 60 seconds")


if __name__ == "__main__":
    main()
