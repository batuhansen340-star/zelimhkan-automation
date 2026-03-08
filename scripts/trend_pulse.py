# scripts/trend_pulse.py
# TrendPulse - Gunluk trend raporu pipeline'i
# 5 ucretsiz kaynaktan veri ceker, Claude ile analiz eder, DOCX rapor olusturur, Telegram'a gonderir

import os
import sys
import json
import requests
import feedparser
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

sys.path.insert(0, os.path.dirname(__file__))
from ai_engine import ask_claude
from telegram_bot import send_telegram, send_document

HEADERS = {'User-Agent': 'TrendPulse/1.0 (github.com/batuhansen340-star)'}
TODAY = datetime.now().strftime('%Y-%m-%d')
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


# ============================================================
# VERI KAYNAKLARI
# ============================================================

def fetch_hacker_news():
    """Hacker News top stories (score > 50)"""
    print("[1/5] Hacker News cekiliyor...")
    try:
        resp = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=15)
        ids = resp.json()[:30]
        stories = []
        for item_id in ids:
            try:
                item = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json', timeout=10).json()
                if item and item.get('score', 0) > 50:
                    stories.append({
                        'title': item.get('title', ''),
                        'url': item.get('url', f'https://news.ycombinator.com/item?id={item_id}'),
                        'score': item.get('score', 0),
                        'comments': item.get('descendants', 0)
                    })
            except Exception:
                continue
        print(f"  -> {len(stories)} haber bulundu")
        return stories
    except Exception as e:
        print(f"  -> Hacker News hatasi: {e}")
        return []


def fetch_product_hunt():
    """Product Hunt RSS feed'inden gunun urunleri"""
    print("[2/5] Product Hunt cekiliyor...")
    try:
        feed = feedparser.parse('https://www.producthunt.com/feed')
        products = []
        for entry in feed.entries[:10]:
            products.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'summary': entry.get('summary', '')[:200]
            })
        print(f"  -> {len(products)} urun bulundu")
        return products
    except Exception as e:
        print(f"  -> Product Hunt hatasi: {e}")
        return []


def fetch_reddit():
    """Reddit AI + Startups + Technology hot posts (score > 30)"""
    print("[3/5] Reddit cekiliyor...")
    try:
        resp = requests.get(
            'https://reddit.com/r/artificial+startups+technology/hot.json',
            headers=HEADERS,
            timeout=15
        )
        data = resp.json()
        posts = []
        for child in data.get('data', {}).get('children', [])[:20]:
            post = child.get('data', {})
            if post.get('score', 0) > 30:
                posts.append({
                    'title': post.get('title', ''),
                    'url': f"https://reddit.com{post.get('permalink', '')}",
                    'score': post.get('score', 0),
                    'subreddit': post.get('subreddit', ''),
                    'comments': post.get('num_comments', 0)
                })
        print(f"  -> {len(posts)} post bulundu")
        return posts
    except Exception as e:
        print(f"  -> Reddit hatasi: {e}")
        return []


def fetch_github_trending():
    """GitHub'da dun olusturulan en cok yildiz alan repolar"""
    print("[4/5] GitHub Trending cekiliyor...")
    try:
        resp = requests.get(
            f'https://api.github.com/search/repositories?q=created:>{YESTERDAY}&sort=stars&order=desc',
            headers=HEADERS,
            timeout=15
        )
        data = resp.json()
        repos = []
        for repo in data.get('items', [])[:10]:
            repos.append({
                'name': repo.get('full_name', ''),
                'url': repo.get('html_url', ''),
                'description': (repo.get('description') or '')[:200],
                'stars': repo.get('stargazers_count', 0),
                'language': repo.get('language', 'N/A')
            })
        print(f"  -> {len(repos)} repo bulundu")
        return repos
    except Exception as e:
        print(f"  -> GitHub hatasi: {e}")
        return []


def fetch_arxiv():
    """ArXiv'den en son AI/ML makaleleri"""
    print("[5/5] ArXiv cekiliyor...")
    try:
        resp = requests.get(
            'http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&max_results=10',
            timeout=15
        )
        feed = feedparser.parse(resp.text)
        papers = []
        for entry in feed.entries:
            papers.append({
                'title': entry.get('title', '').replace('\n', ' ').strip(),
                'url': entry.get('link', ''),
                'summary': entry.get('summary', '').replace('\n', ' ')[:200],
                'authors': ', '.join([a.get('name', '') for a in entry.get('authors', [])[:3]])
            })
        print(f"  -> {len(papers)} makale bulundu")
        return papers
    except Exception as e:
        print(f"  -> ArXiv hatasi: {e}")
        return []


# ============================================================
# CLAUDE ANALIZ
# ============================================================

def analyze_trends(hn, ph, reddit, github, arxiv):
    """Toplanan verileri Claude ile analiz et"""
    print("\nClaude ile analiz ediliyor...")

    raw_data = f"""
## Hacker News (Top Stories, score > 50):
{json.dumps(hn, ensure_ascii=False, indent=2)}

## Product Hunt (Gunun Urunleri):
{json.dumps(ph, ensure_ascii=False, indent=2)}

## Reddit (r/artificial + r/startups + r/technology, score > 30):
{json.dumps(reddit, ensure_ascii=False, indent=2)}

## GitHub Trending (Dun olusturulan, en cok yildiz):
{json.dumps(github, ensure_ascii=False, indent=2)}

## ArXiv (Son AI/ML Makaleleri):
{json.dumps(arxiv, ensure_ascii=False, indent=2)}
"""

    prompt = f"""Sen bir trend analisti ve girisim danismanisin.
Asagidaki veriler GERCEK API'lerden cekilmistir. SADECE bu verilerden analiz yap. Veri UYDURMA.
Emin olmadigin bir sey varsa "Yeterli veri yok" de.

Tarih: {TODAY}

Gorevlerin:
1. En onemli 5 trendi belirle (puan, tekrar sikligi, kaynak sayisina gore)
2. Her trend icin: baslik + neden onemli + kim etkileniyor
3. AI/ML ozel: yeni model/paper/framework varsa vurgula
4. Firsat Radar: Bu trendlerden dogan uygulama firsati (tek kisi MVP suresi tahmini)
5. Para nereye akiyor: yatirim/fonlama haberleri (varsa)

Format: JSON dondur:
{{
  "date": "{TODAY}",
  "executive_summary": "3 cumle ozet",
  "top_trends": [{{"title":"","why_important":"","who_affected":"","sources":[""],"category":"AI|Startup|Finans|Consumer|Turkiye"}}],
  "ai_spotlight": {{"title":"","detail":""}},
  "opportunity_radar": {{"idea":"","market":"","mvp_time":"","competitors":""}},
  "money_flow": {{"title":"","detail":""}},
  "source_links": ["url1","url2"]
}}
Turkce yaz. Emoji kullan.

VERILER:
{raw_data}
"""

    result = ask_claude(prompt, json_mode=True)
    print("  -> Analiz tamamlandi")
    return result


# ============================================================
# DOCX RAPOR OLUSTURMA
# ============================================================

def create_docx_report(analysis):
    """Profesyonel DOCX rapor olustur"""
    print("\nDOCX rapor olusturuluyor...")

    doc = Document()

    # Stil ayarlari
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)

    BLUE_DARK = RGBColor(0x1B, 0x3A, 0x5C)
    BLUE_MED = RGBColor(0x2E, 0x86, 0xC1)
    BLUE_LIGHT = RGBColor(0x85, 0xC1, 0xE9)
    GRAY = RGBColor(0x5D, 0x6D, 0x7E)

    def add_styled_heading(text, level=1):
        h = doc.add_heading(text, level=level)
        for run in h.runs:
            run.font.color.rgb = BLUE_DARK
        return h

    def add_colored_paragraph(text, color=None, bold=False, size=None):
        p = doc.add_paragraph()
        run = p.add_run(text)
        if color:
            run.font.color.rgb = color
        if bold:
            run.bold = True
        if size:
            run.font.size = Pt(size)
        return p

    # === KAPAK ===
    doc.add_paragraph()
    doc.add_paragraph()
    cover = doc.add_paragraph()
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cover.add_run('TrendPulse')
    run.font.size = Pt(36)
    run.font.color.rgb = BLUE_DARK
    run.bold = True

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run(f'Gunluk Trend Raporu')
    run.font.size = Pt(18)
    run.font.color.rgb = BLUE_MED

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_p.add_run(analysis.get('date', TODAY))
    run.font.size = Pt(14)
    run.font.color.rgb = GRAY

    doc.add_page_break()

    # === YONETICI OZETI ===
    add_styled_heading('Yonetici Ozeti', level=1)
    add_colored_paragraph(analysis.get('executive_summary', 'Ozet mevcut degil.'), size=12)
    doc.add_paragraph()

    # === TOP 5 TREND ===
    add_styled_heading('Top 5 Trend', level=1)

    trends = analysis.get('top_trends', [])
    if trends:
        table = doc.add_table(rows=1, cols=4)
        table.style = 'Light Grid Accent 1'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr = table.rows[0].cells
        hdr[0].text = '#'
        hdr[1].text = 'Trend'
        hdr[2].text = 'Neden Onemli'
        hdr[3].text = 'Kategori'

        for i, trend in enumerate(trends[:5], 1):
            row = table.add_row().cells
            row[0].text = str(i)
            row[1].text = trend.get('title', '')
            row[2].text = trend.get('why_important', '')
            row[3].text = trend.get('category', '')

        doc.add_paragraph()

        # Detaylar
        for i, trend in enumerate(trends[:5], 1):
            add_styled_heading(f'{i}. {trend.get("title", "")}', level=2)
            add_colored_paragraph(f'Neden onemli: {trend.get("why_important", "")}', color=GRAY)
            add_colored_paragraph(f'Kim etkileniyor: {trend.get("who_affected", "")}', color=GRAY)
            sources = trend.get('sources', [])
            if sources:
                add_colored_paragraph(f'Kaynaklar: {", ".join(sources)}', color=BLUE_MED, size=9)
            doc.add_paragraph()

    # === AI/ML GUNDEM ===
    add_styled_heading('AI/ML Gundem', level=1)
    ai = analysis.get('ai_spotlight', {})
    if ai:
        add_colored_paragraph(ai.get('title', ''), bold=True, color=BLUE_DARK, size=13)
        add_colored_paragraph(ai.get('detail', ''), color=GRAY)
    doc.add_paragraph()

    # === FIRSAT RADAR ===
    add_styled_heading('Firsat Radar', level=1)
    opp = analysis.get('opportunity_radar', {})
    if opp:
        opp_table = doc.add_table(rows=4, cols=2)
        opp_table.style = 'Light Grid Accent 1'
        labels = ['Fikir', 'Hedef Pazar', 'MVP Suresi', 'Rakipler']
        keys = ['idea', 'market', 'mvp_time', 'competitors']
        for i, (label, key) in enumerate(zip(labels, keys)):
            opp_table.rows[i].cells[0].text = label
            opp_table.rows[i].cells[1].text = str(opp.get(key, ''))
    doc.add_paragraph()

    # === PARA NEREYE AKIYOR ===
    add_styled_heading('Para Nereye Akiyor', level=1)
    money = analysis.get('money_flow', {})
    if money:
        add_colored_paragraph(money.get('title', ''), bold=True, color=BLUE_DARK, size=13)
        add_colored_paragraph(money.get('detail', ''), color=GRAY)
    doc.add_paragraph()

    # === KAYNAK LINKLERI ===
    add_styled_heading('Kaynak Linkleri', level=1)
    links = analysis.get('source_links', [])
    for link in links:
        add_colored_paragraph(f'- {link}', color=BLUE_MED, size=9)

    # Footer
    doc.add_paragraph()
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run('TrendPulse by Zelimkhan Automation')
    run.font.size = Pt(8)
    run.font.color.rgb = GRAY

    # Kaydet
    filename = f'TrendPulse_{TODAY}.docx'
    doc.save(filename)
    print(f"  -> Rapor kaydedildi: {filename}")
    return filename


# ============================================================
# TELEGRAM GONDERIM
# ============================================================

def send_report(analysis, docx_path):
    """Raporu Telegram'a gonder"""
    print("\nTelegram'a gonderiliyor...")

    # Kisa ozet mesaji
    summary = analysis.get('executive_summary', 'Rapor hazir.')
    trends_text = ""
    for i, t in enumerate(analysis.get('top_trends', [])[:5], 1):
        trends_text += f"\n{i}. {t.get('title', '')}"

    message = f"""*TrendPulse - {TODAY}*

{summary}

*Top Trendler:*{trends_text}

_Detayli rapor asagida._"""

    send_telegram(message)
    send_document(docx_path, caption=f"TrendPulse Raporu - {TODAY}")
    print("  -> Telegram gonderimi tamamlandi")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"{'='*50}")
    print(f"  TrendPulse - {TODAY}")
    print(f"{'='*50}\n")

    # 1. Veri topla
    hn = fetch_hacker_news()
    ph = fetch_product_hunt()
    reddit = fetch_reddit()
    github = fetch_github_trending()
    arxiv = fetch_arxiv()

    total = len(hn) + len(ph) + len(reddit) + len(github) + len(arxiv)
    print(f"\nToplam {total} veri noktasi toplandi.")

    if total == 0:
        print("HATA: Hicbir kaynaktan veri alinamadi!")
        send_telegram("*TrendPulse HATA*\nHicbir kaynaktan veri alinamadi.")
        sys.exit(1)

    # 2. Claude ile analiz
    analysis = analyze_trends(hn, ph, reddit, github, arxiv)

    # 3. DOCX rapor olustur
    docx_path = create_docx_report(analysis)

    # 4. Telegram'a gonder
    send_report(analysis, docx_path)

    # 5. Temizlik
    if os.path.exists(docx_path):
        os.remove(docx_path)

    print(f"\n{'='*50}")
    print("  TrendPulse tamamlandi!")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
