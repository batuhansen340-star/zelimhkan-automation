# scripts/telegram_bot.py
# Telegram bildirim gönderici

import os
import requests

BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']


def send_telegram(message, parse_mode='Markdown'):
    """Telegram'a mesaj gönder
    
    Args:
        message: Gönderilecek metin (max 4096 karakter)
        parse_mode: 'Markdown' veya 'HTML'
    """
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': message[:4096],  # Telegram karakter limiti
        'parse_mode': parse_mode
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f'Telegram hatası: {resp.status_code} - {resp.text}')
            # Markdown parse hatası olursa düz metin olarak dene
            if 'can\'t parse' in resp.text.lower():
                payload['parse_mode'] = None
                resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f'Telegram bağlantı hatası: {e}')
        return False
