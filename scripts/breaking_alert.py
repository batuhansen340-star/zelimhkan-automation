# scripts/breaking_alert.py
# TrendPulse v4.0 — Breaking Alert System
# Her 4 saatte bir calisir, HN 500+ / Reddit 1000+ skor tespit eder
# Claude API KULLANMAZ — $0 maliyet

import os
import sys
import json
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from telegram_bot import send_telegram

HEADERS = {'User-Agent': 'TrendPulse/4.0 BreakingAlert (by /u/trendpulse_bot)'}
ALERT_HISTORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'alert_history.json')

# Esik degerleri
HN_THRESHOLD = 500
REDDIT_THRESHOLD = 1000


def load_alert_history():
    """Daha once gonderilen alertleri yukle (tekrar gondermemek icin)"""
    try:
        if os.path.exists(ALERT_HISTORY_FILE):
            with open(ALERT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_alert_history(history):
    """Alert gecmisini kaydet"""
    try:
        os.makedirs(os.path.dirname(ALERT_HISTORY_FILE), exist_ok=True)
        # Son 100 alerti tut
        with open(ALERT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history[-100:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  -> Alert gecmisi kaydedilemedi: {e}")


def _make_alert_key(source, title):
    """Her alert icin benzersiz anahtar (ayni haberi tekrar gondermemek icin)"""
    today = datetime.now().strftime('%Y-%m-%d')
    return f"{today}:{source}:{title[:80]}"


def check_hacker_news():
    """Hacker News'te 500+ skor alan haberleri tespit et"""
    print("[Breaking] Hacker News kontrol ediliyor...")
    alerts = []
    try:
        resp = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=15)
        ids = resp.json()[:50]  # Top 50'ye bak

        for item_id in ids:
            try:
                item = requests.get(
                    f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json',
                    timeout=10
                ).json()
                if item and item.get('score', 0) >= HN_THRESHOLD:
                    alerts.append({
                        'source': 'Hacker News',
                        'title': item.get('title', ''),
                        'score': item.get('score', 0),
                        'comments': item.get('descendants', 0),
                        'url': item.get('url', f'https://news.ycombinator.com/item?id={item_id}'),
                        'hn_link': f'https://news.ycombinator.com/item?id={item_id}'
                    })
            except Exception:
                continue

        print(f"  -> {len(alerts)} breaking haber (>={HN_THRESHOLD} skor)")
    except Exception as e:
        print(f"  -> HN hatasi: {e}")
    return alerts


def check_reddit():
    """Reddit'te 1000+ skor alan postlari tespit et"""
    print("[Breaking] Reddit kontrol ediliyor...")
    alerts = []
    try:
        resp = requests.get(
            'https://reddit.com/r/artificial+startups+technology+programming/hot.json',
            headers=HEADERS, timeout=15
        )
        if resp.status_code != 200:
            print(f"  -> Reddit HTTP {resp.status_code}")
            return []

        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            print("  -> Reddit invalid JSON")
            return []

        for child in data.get('data', {}).get('children', [])[:50]:
            post = child.get('data', {})
            if post.get('score', 0) >= REDDIT_THRESHOLD:
                alerts.append({
                    'source': f"Reddit r/{post.get('subreddit', '?')}",
                    'title': post.get('title', ''),
                    'score': post.get('score', 0),
                    'comments': post.get('num_comments', 0),
                    'url': f"https://reddit.com{post.get('permalink', '')}",
                })

        print(f"  -> {len(alerts)} breaking post (>={REDDIT_THRESHOLD} skor)")
    except Exception as e:
        print(f"  -> Reddit hatasi: {e}")
    return alerts


def send_breaking_alert(alert):
    """Tek bir breaking alert'i Telegram'a gonder"""
    emoji = '\U0001F6A8'  # siren
    score_bar = '\u2588' * min(int(alert['score'] / 100), 20)

    message = f"""{emoji} *BREAKING TREND ALERT*

*{alert['title']}*

\U0001F4CA Skor: *{alert['score']}* {score_bar}
\U0001F4AC {alert.get('comments', 0)} yorum
\U0001F4E1 Kaynak: {alert['source']}

\U0001F517 {alert['url']}"""

    if alert.get('hn_link') and alert['hn_link'] != alert['url']:
        message += f"\n\U0001F4AC HN: {alert['hn_link']}"

    message += f"\n\n_TrendPulse Breaking Alert | {datetime.now().strftime('%H:%M')} TR_"

    send_telegram(message)
    print(f"  -> ALERT GONDERILDI: {alert['title'][:60]}... (skor: {alert['score']})")


def main():
    print(f"{'='*50}")
    print(f"  TrendPulse Breaking Alert")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} | HN>{HN_THRESHOLD} Reddit>{REDDIT_THRESHOLD}")
    print(f"{'='*50}\n")

    # Gecmis alertleri yukle
    history = load_alert_history()
    history_keys = set(h.get('key', '') for h in history)

    # Kaynaklari kontrol et
    all_alerts = check_hacker_news() + check_reddit()

    if not all_alerts:
        print("\nBreaking haber yok, normal.")
        return

    # Daha once gonderilmemis alertleri filtrele
    new_alerts = []
    for alert in all_alerts:
        key = _make_alert_key(alert['source'], alert['title'])
        if key not in history_keys:
            new_alerts.append(alert)
            history.append({
                'key': key,
                'title': alert['title'],
                'score': alert['score'],
                'source': alert['source'],
                'timestamp': datetime.now().isoformat()
            })

    if not new_alerts:
        print(f"\n{len(all_alerts)} breaking haber var ama hepsi daha once gonderildi.")
        return

    # Skora gore sirala (en yuksek once)
    new_alerts.sort(key=lambda x: x['score'], reverse=True)

    print(f"\n{len(new_alerts)} YENI breaking alert gonderiliyor...")
    for alert in new_alerts[:5]:  # Max 5 alert bir seferde
        send_breaking_alert(alert)

    # Gecmisi kaydet
    save_alert_history(history)

    print(f"\n{'='*50}")
    print(f"  {len(new_alerts)} alert gonderildi!")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
