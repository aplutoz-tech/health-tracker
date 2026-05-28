#!/usr/bin/env python3
"""
Check stock prices vs alert thresholds.
Opens a GitHub Issue when target price or stop-loss is triggered.
"""
import json
import os
import sys
import requests
import datetime

BASE_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
GITHUB_TOKEN  = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO   = os.environ.get('GITHUB_REPOSITORY', 'aplutoz-tech/stock-tracker')


def _headers():
    return {'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'}


def ensure_labels():
    owner, repo = GITHUB_REPO.split('/')
    url = f'https://api.github.com/repos/{owner}/{repo}/labels'
    for name, color, desc in [
        ('stock-alert',    'e11d48', '股票價格警示'),
        ('target-reached', '16a34a', '達到目標價'),
        ('stop-loss',      'dc2626', '觸發停損'),
    ]:
        requests.post(url, headers=_headers(),
                      json={'name': name, 'color': color, 'description': desc},
                      timeout=10)  # 422 = already exists, ignored


def open_issue_titles(symbol):
    owner, repo = GITHUB_REPO.split('/')
    r = requests.get(
        f'https://api.github.com/repos/{owner}/{repo}/issues',
        headers=_headers(),
        params={'state': 'open', 'labels': 'stock-alert', 'per_page': 100},
        timeout=10,
    )
    return [i['title'] for i in (r.json() if r.ok else []) if f'[{symbol}]' in i['title']]


def create_issue(title, body, labels):
    owner, repo = GITHUB_REPO.split('/')
    r = requests.post(
        f'https://api.github.com/repos/{owner}/{repo}/issues',
        headers=_headers(),
        json={'title': title, 'body': body, 'labels': labels},
        timeout=10,
    )
    return r.status_code == 201


def main():
    prices_path    = os.path.join(BASE_DIR, 'data', 'prices.json')
    portfolio_path = os.path.join(BASE_DIR, 'portfolio.json')
    if not os.path.exists(prices_path):
        print('prices.json missing — run fetch_prices.py first'); sys.exit(1)

    with open(portfolio_path, encoding='utf-8') as f:
        portfolio = json.load(f)
    with open(prices_path, encoding='utf-8') as f:
        data = json.load(f)

    prices  = data['prices']
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    ensure_labels()
    triggered = 0

    for holding in portfolio['holdings']:
        symbol = holding['symbol']
        if symbol not in prices:
            continue
        p      = prices[symbol]
        price  = p['price']
        name   = p.get('name', symbol)
        alerts = p.get('alerts', {})
        open_t = open_issue_titles(symbol)

        def row(label, val): return f'| {label} | {val} |\n'

        # Target price
        target = alerts.get('target_price')
        if target and price >= target and not any('目標價' in t for t in open_t):
            title = f'🎯 [{symbol}] {name} 達到目標價 ${target}'
            body = (
                '## 🎯 達到目標價\n\n| 項目 | 數值 |\n|---|---|\n'
                + row('股票', f'**{symbol} {name}**')
                + row('目前股價', f'**${price:,.2f}**')
                + row('目標價', f'${target:,.2f}')
                + row('超出', f'+{(price-target)/target*100:.1f}%')
                + row('持股', f'{p.get("shares",0):,} 股')
                + row('損益', f'${p.get("pnl",0):,.0f} ({p.get("pnl_pct",0):+.1f}%)')
                + f'\n⏰ {now_str}\n\n> 請評估是否執行獲利了結。'
            )
            ok = create_issue(title, body, ['stock-alert', 'target-reached'])
            print(('  ✅ ' if ok else '  ❌ ') + title)
            triggered += ok

        # Stop loss
        stop = alerts.get('stop_loss')
        if stop and price <= stop and not any('停損' in t for t in open_t):
            title = f'🛑 [{symbol}] {name} 觸發停損 ${stop}'
            body = (
                '## 🛑 觸發停損\n\n| 項目 | 數值 |\n|---|---|\n'
                + row('股票', f'**{symbol} {name}**')
                + row('目前股價', f'**${price:,.2f}**')
                + row('停損價', f'${stop:,.2f}')
                + row('跌破', f'{(price-stop)/stop*100:.1f}%')
                + row('持股', f'{p.get("shares",0):,} 股')
                + row('損益', f'${p.get("pnl",0):,.0f} ({p.get("pnl_pct",0):+.1f}%)')
                + f'\n⏰ {now_str}\n\n> ⚠️ 請立即評估停損以控制風險。'
            )
            ok = create_issue(title, body, ['stock-alert', 'stop-loss'])
            print(('  ✅ ' if ok else '  ❌ ') + title)
            triggered += ok

    print(f'\nDone. {triggered} new issue(s) created.')


if __name__ == '__main__':
    main()
