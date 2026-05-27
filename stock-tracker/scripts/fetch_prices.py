#!/usr/bin/env python3
"""
Fetch Taiwan stock prices from TWSE mis API.
Saves results to stock-tracker/data/prices.json
"""
import json
import os
import time
import datetime
import requests

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def fetch_price(symbol: str, market: str) -> dict | None:
    ex = 'tse' if market == 'TSE' else 'otc'
    url = (
        'https://mis.twse.com.tw/stock/api/getStockInfo.jsp'
        f'?ex_ch={ex}_{symbol}.tw&json=1&delay=0'
    )
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; stock-tracker-bot/1.0)',
        'Referer': 'https://mis.twse.com.tw/stock/index.jsp',
    }
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            items = r.json().get('msgArray', [])
            if items:
                item = items[0]
                raw = item.get('z', '-')
                price = float(raw) if raw not in ('-', '') else float(item.get('y', 0) or 0)
                return {
                    'symbol':     symbol,
                    'name':       item.get('n', symbol),
                    'market':     market,
                    'price':      price,
                    'open':       float(item.get('o', 0) or 0),
                    'high':       float(item.get('h', 0) or 0),
                    'low':        float(item.get('l', 0) or 0),
                    'prev_close': float(item.get('y', 0) or 0),
                    'volume':     int(item.get('v', 0) or 0),
                    'timestamp':  datetime.datetime.now().isoformat(),
                }
        except Exception as e:
            print(f'  Attempt {attempt + 1} failed for {symbol}: {e}')
            time.sleep(2 ** attempt)
    return None


def main():
    portfolio_path = os.path.join(BASE_DIR, 'portfolio.json')
    with open(portfolio_path, encoding='utf-8') as f:
        portfolio = json.load(f)

    prices = {}
    for holding in portfolio['holdings']:
        symbol = holding['symbol']
        market = holding['market']
        print(f'Fetching {symbol} ({market}) ...')
        data = fetch_price(symbol, market)
        if data:
            avg_cost = holding.get('avg_cost', 0)
            shares   = holding.get('shares', 0)
            if avg_cost > 0 and data['price'] > 0:
                data['avg_cost']     = avg_cost
                data['shares']       = shares
                data['market_value'] = round(data['price'] * shares, 2)
                data['pnl']          = round((data['price'] - avg_cost) * shares, 2)
                data['pnl_pct']      = round((data['price'] - avg_cost) / avg_cost * 100, 2)
            data['alerts'] = holding.get('alerts', {})\

            prices[symbol] = data
            print(f'  {data["name"]}: {data["price"]}')
        else:
            print(f'  FAILED: {symbol}')
        time.sleep(0.5)

    out_path = os.path.join(BASE_DIR, 'data', 'prices.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result = {'last_updated': datetime.datetime.now().isoformat(), 'prices': prices}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'Done. {len(prices)} stocks saved.')


if __name__ == '__main__':
    main()
