#!/usr/bin/env python3
"""
Fetch Taiwan stock prices via Fugle Market Data API (real-time intraday).
Fallback: TWSE/TPEX OpenAPI (end-of-day) → yfinance
"""
import json
import os
import time
import datetime
import requests

BASE_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FUGLE_API_KEY = os.environ.get('FUGLE_API_KEY', '')

SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'stock-tracker-bot/3.0'})


# ── Fugle Market Data API (real-time) ─────────────────────────────────────────

def _fugle(symbol: str) -> dict | None:
    """Real-time intraday quote via Fugle Market Data API v1.0."""
    if not FUGLE_API_KEY:
        return None
    url = f'https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/{symbol}'
    try:
        r = SESSION.get(url, headers={'X-API-KEY': FUGLE_API_KEY}, timeout=10)
        if r.status_code == 403:
            print('    Fugle: invalid or missing API key')
            return None
        if r.status_code != 200:
            print(f'    Fugle HTTP {r.status_code}')
            return None
        d = r.json()
        price = d.get('lastPrice') or d.get('closePrice') or d.get('referencePrice')
        if not price:
            return None
        return {
            'name':       d.get('name', symbol),
            'price':      float(price),
            'open':       float(d.get('openPrice') or price),
            'high':       float(d.get('highPrice') or price),
            'low':        float(d.get('lowPrice') or price),
            'prev_close': float(d.get('previousClose') or price),
            'volume':     int(d.get('volume') or 0),
        }
    except Exception as e:
        print(f'    Fugle error: {e}')
        return None


# ── TWSE / TPEX OpenAPI (end-of-day fallback) ────────────────────────────────

def _twse_openapi(symbol: str) -> dict | None:
    today = datetime.date.today()
    for delta in range(7):
        date = (today - datetime.timedelta(days=delta)).strftime('%Y%m%d')
        url = (
            'https://www.twse.com.tw/exchangeReport/STOCK_DAY'
            f'?response=json&stockNo={symbol}&date={date}'
        )
        try:
            r = SESSION.get(url, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            rows = data.get('data', [])
            if not rows:
                continue
            row   = rows[-1]
            close = float(row[6].replace(',', ''))
            open_ = float(row[3].replace(',', ''))
            high  = float(row[4].replace(',', ''))
            low   = float(row[5].replace(',', ''))
            vol   = int(row[1].replace(',', ''))
            try:
                change = float(row[7].replace(',', '').replace('+', '').replace('X', '0'))
                prev   = round(close - change, 2)
            except ValueError:
                prev = close
            title = data.get('title', symbol)
            name  = title.split(' ')[-1].strip()
            return {'name': name or symbol, 'price': close, 'open': open_,
                    'high': high, 'low': low, 'prev_close': prev, 'volume': vol}
        except Exception as e:
            print(f'    TWSE OpenAPI delta={delta}: {e}')
    return None


def _tpex_api(symbol: str) -> dict | None:
    today = datetime.date.today()
    for delta in range(7):
        date = (today - datetime.timedelta(days=delta)).strftime('%Y/%m/%d')
        url = (
            'https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php'
            f'?l=zh-tw&d={date}&stkno={symbol}&o=json'
        )
        try:
            r = SESSION.get(url, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            rows = data.get('aaData', [])
            if not rows:
                continue
            row   = rows[-1]
            close = float(row[6].replace(',', ''))
            open_ = float(row[3].replace(',', ''))
            high  = float(row[4].replace(',', ''))
            low   = float(row[5].replace(',', ''))
            vol   = int(row[1].replace(',', ''))
            try:
                change = float(row[7].replace(',', '').replace('+', ''))
                prev   = round(close - change, 2)
            except ValueError:
                prev = close
            return {'name': data.get('stkName', symbol), 'price': close,
                    'open': open_, 'high': high, 'low': low,
                    'prev_close': prev, 'volume': vol}
        except Exception as e:
            print(f'    TPEX delta={delta}: {e}')
    return None


def _yfinance_fallback(symbol: str, market: str) -> dict | None:
    try:
        import yfinance as yf
        suffix = '.TW' if market == 'TSE' else '.TWO'
        ticker = yf.Ticker(symbol + suffix)
        hist = ticker.history(period='5d')
        if hist.empty:
            return None
        row  = hist.iloc[-1]
        prev = float(hist.iloc[-2]['Close']) if len(hist) >= 2 else float(row['Close'])
        name = symbol
        try:
            name = ticker.info.get('shortName', symbol)
        except Exception:
            pass
        return {
            'name': name, 'price': round(float(row['Close']), 2),
            'open': round(float(row['Open']), 2), 'high': round(float(row['High']), 2),
            'low':  round(float(row['Low']),  2), 'prev_close': round(prev, 2),
            'volume': int(row['Volume']),
        }
    except Exception as e:
        print(f'    yfinance: {e}')
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def fetch_price(symbol: str, market: str) -> dict | None:
    if FUGLE_API_KEY:
        print('  [1] Fugle real-time API ...')
        result = _fugle(symbol)
        if result:
            return result
    print('  [2] TWSE/TPEX OpenAPI ...')
    result = _twse_openapi(symbol) if market == 'TSE' else _tpex_api(symbol)
    if result:
        return result
    print('  [3] yfinance fallback ...')
    return _yfinance_fallback(symbol, market)


def main():
    portfolio_path = os.path.join(BASE_DIR, 'portfolio.json')
    with open(portfolio_path, encoding='utf-8') as f:
        portfolio = json.load(f)

    prices = {}
    for holding in portfolio['holdings']:
        symbol = holding['symbol']
        market = holding['market']
        print(f'\nFetching {symbol} ({market}) ...')
        base = fetch_price(symbol, market)
        if base:
            avg_cost = holding.get('avg_cost', 0)
            shares   = holding.get('shares', 0)
            data = {'symbol': symbol, 'market': market,
                    'timestamp': datetime.datetime.now().isoformat(), **base}
            if avg_cost > 0 and data['price'] > 0:
                data['avg_cost']     = avg_cost
                data['shares']       = shares
                data['market_value'] = round(data['price'] * shares, 2)
                data['pnl']          = round((data['price'] - avg_cost) * shares, 2)
                data['pnl_pct']      = round((data['price'] - avg_cost) / avg_cost * 100, 2)
            data['alerts'] = holding.get('alerts', {})
            prices[symbol] = data
            print(f'  OK: {data["name"]} = {data["price"]}')
        else:
            print(f'  FAILED: {symbol}')
        time.sleep(0.3)

    out_path = os.path.join(BASE_DIR, 'data', 'prices.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result = {'last_updated': datetime.datetime.now().isoformat(), 'prices': prices}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\nDone. {len(prices)}/{len(portfolio["holdings"])} stocks saved.')


if __name__ == '__main__':
    main()
