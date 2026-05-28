#!/usr/bin/env python3
"""
Fetch Taiwan stock end-of-day prices.
Primary:  TWSE / TPEX OpenAPI (official, no auth required)
Fallback: yfinance (.TW / .TWO suffix)
"""
import json
import os
import time
import datetime
import requests

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (compatible; stock-tracker-bot/2.0)',
    'Accept': 'application/json',
})


# ── TWSE OpenAPI ──────────────────────────────────────────────────────────────

def _twse_openapi(symbol: str) -> dict | None:
    """Fetch from TWSE official open data API (TSE listed stocks)."""
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
            # Last row = most recent trading day
            # Fields: date, volume, amount, open, high, low, close, change, trades
            row = rows[-1]
            close = float(row[6].replace(',', ''))
            open_ = float(row[3].replace(',', ''))
            high  = float(row[4].replace(',', ''))
            low   = float(row[5].replace(',', ''))
            vol   = int(row[1].replace(',', ''))
            change_str = row[7].replace(',', '').replace('+', '').replace('X', '0').strip()
            try:
                change = float(change_str)
                prev   = round(close - change, 2)
            except ValueError:
                prev = close
            title = data.get('title', symbol)
            name  = title.split(' ')[-1].strip() if ' ' in title else title.split(' ')[-1].strip()
            return {
                'name':       name or symbol,
                'price':      close,
                'open':       open_,
                'high':       high,
                'low':        low,
                'prev_close': prev,
                'volume':     vol,
            }
        except Exception as e:
            print(f'    TWSE OpenAPI attempt {delta}: {e}')
    return None


def _tpex_api(symbol: str) -> dict | None:
    """Fetch from TPEX (OTC) API."""
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
            row = rows[-1]
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
            return {
                'name':       data.get('stkName', symbol),
                'price':      close,
                'open':       open_,
                'high':       high,
                'low':        low,
                'prev_close': prev,
                'volume':     vol,
            }
        except Exception as e:
            print(f'    TPEX API attempt {delta}: {e}')
    return None


def _yfinance_fallback(symbol: str, market: str) -> dict | None:
    """Fallback: use yfinance (.TW for TSE, .TWO for OTC)."""
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
            'name':       name,
            'price':      round(float(row['Close']), 2),
            'open':       round(float(row['Open']), 2),
            'high':       round(float(row['High']), 2),
            'low':        round(float(row['Low']), 2),
            'prev_close': round(prev, 2),
            'volume':     int(row['Volume']),
        }
    except Exception as e:
        print(f'    yfinance fallback failed: {e}')
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def fetch_price(symbol: str, market: str) -> dict | None:
    print(f'  [1] TWSE/TPEX OpenAPI ...')
    base = _twse_openapi(symbol) if market == 'TSE' else _tpex_api(symbol)
    if base:
        return base
    print(f'  [2] yfinance fallback ...')
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
            data = {
                'symbol':    symbol,
                'market':    market,
                'timestamp': datetime.datetime.now().isoformat(),
                **base,
            }
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
        time.sleep(1)

    out_path = os.path.join(BASE_DIR, 'data', 'prices.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    result = {'last_updated': datetime.datetime.now().isoformat(), 'prices': prices}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\nDone. {len(prices)}/{len(portfolio["holdings"])} stocks saved.')


if __name__ == '__main__':
    main()
