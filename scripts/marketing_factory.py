# scripts/marketing_factory.py
# Pipeline 2: StoryPal için günlük sosyal medya içerik üretimi
# Çalışma saati: 08:00 (TR)

import os
import json
from datetime import datetime
from ai_engine import ask_claude
from telegram_bot import send_telegram

PRODUCT_CONTEXT = """
StoryPal: AI ile çocuklara kişiselleştirilmiş hikaye yaratan uygulama.
Hedef kitle: 3-10 yaş çocuklarının ebeveynleri.
Değer önerisi: Her çocuk kendi hikayesinin kahramanı.
Fiyat: Free tier (3 hikaye/gün) + Premium ($4.99/ay, sınırsız).
Platform: iOS (App Store).
Öne çıkan özellikler: AI görseller, PDF export, çocuk profilleri, istatistikler.
"""


def generate_content():
    """Günlük içerik paketi üret"""
    day_of_week = datetime.now().strftime('%A')
    day_tr = {
        'Monday': 'Pazartesi', 'Tuesday': 'Salı', 'Wednesday': 'Çarşamba',
        'Thursday': 'Perşembe', 'Friday': 'Cuma', 'Saturday': 'Cumartesi',
        'Sunday': 'Pazar'
    }.get(day_of_week, day_of_week)

    prompt = f"""İçerik stratejisti olarak StoryPal için günlük sosyal medya içeriği üret.

Ürün bilgisi: {PRODUCT_CONTEXT}
Gün: {day_tr}

JSON formatında 3 içerik üret:
{{"contents": [
  {{"platform": "twitter", "type": "thread", "content": "thread metni (max 280 karakter/tweet, 3-4 tweet)", "hashtags": ["#StoryPal", "#tag2"]}},
  {{"platform": "instagram", "type": "caption", "content": "caption metni", "visual_idea": "görsel önerisi (ne tür fotoğraf/grafik)"}},
  {{"platform": "blog", "type": "outline", "content": "blog başlığı + 3 madde özet"}}
]}}

Kurallar:
- Türkçe yaz
- Samimi, ebeveyn dostu ton
- Her gün farklı açı: eğitim, yaratıcılık, aile vakti, teknoloji, çocuk gelişimi
- CTA (call to action) ekle"""

    try:
        return ask_claude(prompt, json_mode=True)
    except Exception as e:
        print(f'İçerik üretim hatası: {e}')
        return {'contents': [], 'error': str(e)}


def main():
    print('[Marketing Fabrikası] İçerik üretiliyor...')
    content = generate_content()

    # Kaydet
    data_path = 'data/marketing.json'
    try:
        history = json.loads(open(data_path).read())
    except (FileNotFoundError, json.JSONDecodeError):
        history = []

    history.append({
        'date': datetime.now().isoformat(),
        'content': content
    })
    history = history[-30:]

    with open(data_path, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    # Telegram bildirim
    items = content.get('contents', [])
    msg = f'🎭 *Marketing Fabrikası*\n'
    msg += f'📅 {datetime.now().strftime("%d.%m.%Y")}\n\n'

    for item in items:
        emoji = '🐦' if item['platform'] == 'twitter' else '📷' if item['platform'] == 'instagram' else '📝'
        msg += f'{emoji} *{item["platform"].title()}* ({item.get("type", "")})\n'
        msg += f'{item["content"][:200]}...\n\n'

    send_telegram(msg)
    print(f'[Marketing Fabrikası] {len(items)} içerik hazır.')


if __name__ == '__main__':
    main()
