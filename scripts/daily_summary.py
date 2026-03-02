# scripts/daily_summary.py
# Pipeline 3: Günlük commit özeti + metrikler + Telegram rapor
# Çalışma saati: 20:00 (TR)

import os
import json
import requests
from datetime import datetime, timedelta
from ai_engine import ask_claude
from telegram_bot import send_telegram

GITHUB_TOKEN = os.environ['GITHUB_TOKEN']
TARGET_REPO = os.environ.get('TARGET_REPO', 'batuhansen340-star/StoryPal')


def fetch_today_commits():
    """Son 24 saatin commit'lerini çek"""
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    since = (datetime.utcnow() - timedelta(hours=24)).isoformat() + 'Z'
    url = f'https://api.github.com/repos/{TARGET_REPO}/commits'
    
    try:
        resp = requests.get(url, headers=headers, params={'since': since}, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f'Commit çekme hatası: {e}')
        return []


def fetch_workflow_runs():
    """Son Actions run'larını çek"""
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    url = f'https://api.github.com/repos/{TARGET_REPO}/actions/runs'
    
    try:
        resp = requests.get(url, headers=headers, params={'per_page': 10}, timeout=15)
        return resp.json().get('workflow_runs', []) if resp.status_code == 200 else []
    except Exception as e:
        print(f'Workflow çekme hatası: {e}')
        return []


def generate_summary(commits, runs):
    """Claude ile günlük özet oluştur"""
    commit_text = '\n'.join([
        f'- {c["commit"]["message"][:100]}'
        for c in commits[:20]
    ]) or 'Bugün commit yok.'

    run_text = '\n'.join([
        f'- {r["name"]}: {r["conclusion"] or "running"}'
        for r in runs[:10]
    ]) or 'Actions run yok.'

    prompt = f"""Günlük geliştirme özeti oluştur. Kısa ve öz Türkçe yaz.

Commitler:
{commit_text}

GitHub Actions:
{run_text}

Şu formatta yaz:
1. Bugün ne yapıldı (2-3 cümle)
2. Önemli değişiklikler (varsa)
3. Yarın için öneri (1 cümle)"""

    try:
        return ask_claude(prompt)
    except Exception as e:
        return f'Özet oluşturulamadı: {str(e)}'


def main():
    print('[Günlük Özet] Toplama başlıyor...')
    commits = fetch_today_commits()
    runs = fetch_workflow_runs()
    summary = generate_summary(commits, runs)

    # Kaydet
    data_path = 'data/summaries.json'
    try:
        history = json.loads(open(data_path).read())
    except (FileNotFoundError, json.JSONDecodeError):
        history = []

    history.append({
        'date': datetime.now().isoformat(),
        'commits': len(commits),
        'runs': len(runs),
        'summary': summary
    })
    history = history[-30:]

    with open(data_path, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    # Telegram rapor
    msg = f'📊 *Günlük Özet*\n'
    msg += f'📅 {datetime.now().strftime("%d.%m.%Y %H:%M")}\n\n'
    msg += f'💻 Commit sayısı: {len(commits)}\n'
    msg += f'⚙️ Actions run: {len(runs)}\n\n'
    msg += f'{summary}'

    send_telegram(msg)
    print(f'[Günlük Özet] Rapor gönderildi. ({len(commits)} commit)')


if __name__ == '__main__':
    main()
