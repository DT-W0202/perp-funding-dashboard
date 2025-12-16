# Perpetual Funding Rate Dashboard

实时聚合多个永续合约交易所的资费率数据。

## 支持的交易所

- **Hyperliquid** - 1小时资费周期 (含OI/Volume数据)
- **Lighter** - 1小时资费周期
- **Aster** - 8小时资费周期 (含Volume数据)

## 安装

```bash
pip install -r requirements.txt
```

## 使用

### Web 看板 (推荐)

```bash
streamlit run web_dashboard.py
```

打开浏览器访问 http://localhost:8501

### CLI 看板

```bash
# 启动看板（自动刷新，每60秒）
python dashboard.py

# 单次获取，不刷新
python dashboard.py --no-refresh

# 自定义刷新间隔（秒）
python dashboard.py --interval 30
```

## 功能

- 自动获取各交易所资费率
- 三种排序方式: 最高费率(做空机会)、最低费率(做多机会)、绝对值
- 年化收益率计算（APR）
- Open Interest 和 24h Volume 显示
- 跨交易所对比，按 Spread 排序显示套利机会
- 颜色标记（绿色=正资费，红色=负资费）
- 过滤低流动性市场（Volume < 10k, OI < 200k）

## 文件结构

```
perp-funding-dashboard/
├── __init__.py          # 包初始化
├── funding_fetchers.py  # 各交易所数据抓取器
├── web_dashboard.py     # Streamlit Web 看板
├── dashboard.py         # CLI 终端看板
├── requirements.txt     # 依赖包
└── README.md           # 说明文档
```
