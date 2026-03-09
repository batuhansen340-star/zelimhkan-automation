# scripts/trend_memory.py
# TrendPulse v4.0 — 14 Gunluk Trend Hafizasi
# Trendlerin yasam dongusunu takip eder: new → rising → peak → declining

import os
import json
from datetime import datetime, timedelta
from collections import Counter

MEMORY_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'trend_memory.json')
MAX_DAYS = 14  # 14 gun hafiza


def _normalize_title(text):
    """Baslik normalizasyonu — kucuk harf, fazla bosluklari temizle"""
    return ' '.join(text.lower().split())


def _extract_keywords(text):
    """Basliktan anahtar kelimeleri cikar (3+ karakter)"""
    words = _normalize_title(text).split()
    return set(w for w in words if len(w) > 3)


def load_memory():
    """Trend hafizasini yukle"""
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 14 gunden eski entryleri temizle
            cutoff = (datetime.now() - timedelta(days=MAX_DAYS)).strftime('%Y-%m-%d')
            cleaned = {}
            for title, info in data.items():
                dates = [d for d in info.get('seen_dates', []) if d >= cutoff]
                if dates:
                    info['seen_dates'] = dates
                    cleaned[title] = info
            return cleaned
    except Exception as e:
        print(f"  -> Trend hafizasi yuklenemedi: {e}")
    return {}


def save_memory(memory):
    """Trend hafizasini kaydet"""
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
        print(f"  -> Trend hafizasi kaydedildi ({len(memory)} trend)")
    except Exception as e:
        print(f"  -> Trend hafizasi kaydedilemedi: {e}")


def save_today(sources, today=None):
    """Bugunun trendlerini hafizaya ekle

    Args:
        sources: dict of {source_name: [items]}
        today: tarih string (varsayilan: bugun)
    """
    if today is None:
        today = datetime.now().strftime('%Y-%m-%d')

    memory = load_memory()

    for source_name, items in sources.items():
        for item in items:
            title = _normalize_title(item.get('title', '') or item.get('name', ''))
            if not title or len(title) < 5:
                continue

            # Mevcut kayit var mi kontrol et (keyword eslestirmesi ile)
            matched_key = _find_matching_key(memory, title)

            if matched_key:
                # Mevcut trendi guncelle
                entry = memory[matched_key]
                if today not in entry['seen_dates']:
                    entry['seen_dates'].append(today)
                if source_name not in entry['sources']:
                    entry['sources'].append(source_name)
                entry['last_seen'] = today
                # Score guncelle (en yuksegi tut)
                new_score = item.get('score', 0) or item.get('stars', 0) or item.get('reactions', 0)
                entry['peak_score'] = max(entry.get('peak_score', 0), new_score)
            else:
                # Yeni trend ekle
                score = item.get('score', 0) or item.get('stars', 0) or item.get('reactions', 0)
                memory[title] = {
                    'first_seen': today,
                    'last_seen': today,
                    'seen_dates': [today],
                    'sources': [source_name],
                    'peak_score': score,
                    'keywords': list(_extract_keywords(title))
                }

    save_memory(memory)
    return memory


def _find_matching_key(memory, title):
    """Hafizada benzer bir baslik var mi kontrol et (%50 keyword eslesmesi)"""
    title_keywords = _extract_keywords(title)
    if not title_keywords:
        return None

    for key, info in memory.items():
        key_keywords = set(info.get('keywords', []))
        if not key_keywords:
            key_keywords = _extract_keywords(key)

        if title_keywords and key_keywords:
            overlap = len(title_keywords & key_keywords) / min(len(title_keywords), len(key_keywords))
            if overlap >= 0.5:
                return key

    return None


def analyze_trend_lifecycle(memory):
    """Her trendin yasam dongusu durumunu hesapla

    Lifecycle:
    - new: Sadece bugun goruldu (1 gun)
    - rising: 2-3 gun goruldu, skor artiyorsa
    - peak: 4+ gun goruldu veya 3+ kaynakta
    - declining: Son 2 gundur gorulmuyor ama hafizada var

    Returns: dict of {title: {lifecycle, days_active, sources_count, ...}}
    """
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')

    lifecycle_data = {}

    for title, info in memory.items():
        seen_dates = info.get('seen_dates', [])
        days_active = len(seen_dates)
        sources_count = len(info.get('sources', []))
        last_seen = info.get('last_seen', '')
        first_seen = info.get('first_seen', '')

        # Yasam dongusu hesapla
        if last_seen == today:
            if days_active == 1:
                lifecycle = 'new'
            elif days_active <= 3:
                lifecycle = 'rising'
            else:
                lifecycle = 'peak'
            # 3+ kaynak = peak
            if sources_count >= 3:
                lifecycle = 'peak'
        elif last_seen == yesterday:
            lifecycle = 'declining'
        elif last_seen >= two_days_ago:
            lifecycle = 'declining'
        else:
            lifecycle = 'faded'

        # Sadece aktif trendleri dahil et (faded olanlari atla)
        if lifecycle != 'faded':
            lifecycle_data[title] = {
                'lifecycle': lifecycle,
                'days_active': days_active,
                'sources_count': sources_count,
                'first_seen': first_seen,
                'last_seen': last_seen,
                'peak_score': info.get('peak_score', 0),
                'sources': info.get('sources', [])
            }

    return lifecycle_data


def get_lifecycle_summary(memory):
    """Hafizadaki trendlerin yasam dongusu ozeti

    Returns: {
        'new': count,
        'rising': count,
        'peak': count,
        'declining': count,
        'total_tracked': count,
        'top_rising': [titles],
        'top_peak': [titles]
    }
    """
    lifecycle_data = analyze_trend_lifecycle(memory)

    counts = Counter(info['lifecycle'] for info in lifecycle_data.values())

    # En onemli rising trendler (skor bazli)
    rising = [(t, info) for t, info in lifecycle_data.items() if info['lifecycle'] == 'rising']
    rising.sort(key=lambda x: x[1]['peak_score'], reverse=True)
    top_rising = [t for t, _ in rising[:3]]

    # Peak trendler
    peak = [(t, info) for t, info in lifecycle_data.items() if info['lifecycle'] == 'peak']
    peak.sort(key=lambda x: x[1]['days_active'], reverse=True)
    top_peak = [t for t, _ in peak[:3]]

    return {
        'new': counts.get('new', 0),
        'rising': counts.get('rising', 0),
        'peak': counts.get('peak', 0),
        'declining': counts.get('declining', 0),
        'total_tracked': len(lifecycle_data),
        'top_rising': top_rising,
        'top_peak': top_peak,
        'lifecycle_data': lifecycle_data
    }
