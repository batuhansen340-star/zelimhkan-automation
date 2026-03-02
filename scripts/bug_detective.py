# scripts/bug_detective.py
# Pipeline 1: GitHub Issues tarama + Claude analiz + Telegram rapor
# Çalışma saati: 07:00 (TR)

import os
import json
import requests
from datetime import datetime
from ai_engine import ask_claude
from telegram_bot import send_telegram

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
TARGET_REPO = os.environ.get('TARGET_REPO', 'batuhansen340-star/StoryPal')


def fetch_open_issues():
    """GitHub API'den açık issue'ları çek"""
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    url = f'https://api.github.com/repos/{TARGET_REPO}/issues'
    params = {'state': 'open', 'per_page': 20}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        # PR'ları filtrele (GitHub issues endpoint PR'ları da döndürür)
        return [i for i in resp.json() if 'pull_request' not in i]
    except Exception as e:
        print(f'GitHub API hatası: {e}')
        return []


def analyze_bugs(issues):
    """Claude ile hata analizi yap"""
    if not issues:
        return {'bugs': [], 'summary': 'Açık hata yok. 🎉'}

    # Issue'ları metne çevir
    issues_text = '\n'.join([
        f'#{i["number"]}: {i["title"]}\n{i.get("body", "")[:500]}'
        for i in issues[:10]  # Max 10 issue analiz et
    ])

    prompt = f"""Sen bir kıdemli QA mühendisisin.
Aşağıdaki GitHub issue'ları analiz et.
Her biri için: öncelik (P0-P3), tahmini fix süresi, kısa fix önerisi ver.

Öncelik kriterleri:
- P0: Uygulama çöküyor veya veri kaybı
- P1: Ana özellik çalışmıyor
- P2: Minor bug, workaround var
- P3: Kozmetik, nice-to-have

JSON formatında yanıtla:
{{"bugs": [{{"number": 1, "priority": "P1", "fix_time": "2 saat", "suggestion": "..."}}], "summary": "genel değerlendirme"}}

Issues:
{issues_text}"""

    try:
        return ask_claude(prompt, json_mode=True)
    except Exception as e:
        print(f'Claude analiz hatası: {e}')
        return {'bugs': [], 'summary': f'Analiz hatası: {str(e)}'}


def main():
    print('[Bug Dedektifi] Tarama başlıyor...')
    issues = fetch_open_issues()
    analysis = analyze_bugs(issues)

    # Veriyi kaydet
    data_path = 'data/bugs.json'
    try:
        history = json.loads(open(data_path).read())
    except (FileNotFoundError, json.JSONDecodeError):
        history = []
    
    history.append({
        'date': datetime.now().isoformat(),
        'total_issues': len(issues),
        'analysis': analysis
    })
    # Son 30 günü tut
    history = history[-30:]
    
    with open(data_path, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    # Telegram bildirim oluştur
    bugs = analysis.get('bugs', [])
    p0_count = sum(1 for b in bugs if b.get('priority') == 'P0')
    p1_count = sum(1 for b in bugs if b.get('priority') == 'P1')

    msg = f'🐛 *Bug Dedektifi Raporu*\n'
    msg += f'📅 {datetime.now().strftime("%d.%m.%Y %H:%M")}\n\n'
    msg += f'Toplam açık issue: {len(issues)}\n'
    msg += f'🔴 P0 (Kritik): {p0_count}\n'
    msg += f'🟠 P1 (Yüksek): {p1_count}\n\n'

    for b in bugs[:5]:  # İlk 5 bug
        emoji = '🔴' if b.get('priority') == 'P0' else '🟠' if b.get('priority') == 'P1' else '🟡'
        msg += f'{emoji} #{b["number"]} [{b["priority"]}]\n'
        msg += f'  Fix: {b.get("suggestion", "N/A")[:100]}\n\n'

    if analysis.get('summary'):
        msg += f'📝 {analysis["summary"]}'

    send_telegram(msg)
    print(f'[Bug Dedektifi] {len(issues)} issue analiz edildi.')


if __name__ == '__main__':
    main()
