# scripts/trend_pulse.py
# TrendPulse - Gunluk trend raporu pipeline'i
# 7 ucretsiz kaynaktan veri ceker, Claude ile analiz eder, DOCX rapor olusturur, Telegram'a gonderir

import os
import sys
import json
import requests
import feedparser
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

sys.path.insert(0, os.path.dirname(__file__))
from ai_engine import ask_claude
from telegram_bot import send_telegram, send_document

HEADERS = {'User-Agent': 'TrendPulse/1.0 (by /u/trendpulse_bot)'}
TODAY = datetime.now().strftime('%Y-%m-%d')
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


# ============================================================
# VERI KAYNAKLARI (7 kaynak, hepsi ucretsiz, auth yok)
# ============================================================

def fetch_hacker_news():
    """Hacker News top stories (score > 50) — en iyi tech sinyal kaynagi"""
    print("[1/7] Hacker News cekiliyor...")
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
    print("[2/7] Product Hunt cekiliyor...")
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
    """Reddit AI + Startups + Technology + SideProject hot posts (score > 30)"""
    print("[3/7] Reddit cekiliyor...")
    try:
        resp = requests.get(
            'https://reddit.com/r/artificial+startups+technology+SideProject/hot.json',
            headers=HEADERS,
            timeout=15
        )
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            print("  -> Reddit HTML/invalid JSON dondurdu, atlaniyor")
            return []
        posts = []
        for child in data.get('data', {}).get('children', [])[:25]:
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
    """GitHub'da gercek trending repolar — son 7 gunde olusturulan en cok yildiz alan"""
    print("[4/7] GitHub Trending cekiliyor...")
    try:
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        gh_headers = {
            'User-Agent': 'TrendPulse/1.0',
            'Accept': 'application/vnd.github.v3+json',
        }
        gh_token = os.environ.get('GITHUB_TOKEN', '')
        if gh_token:
            gh_headers['Authorization'] = f'token {gh_token}'
        resp = requests.get(
            f'https://api.github.com/search/repositories?q=created:>{week_ago}&sort=stars&order=desc&per_page=15',
            headers=gh_headers,
            timeout=15
        )
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            print("  -> GitHub invalid JSON, atlaniyor")
            return []
        repos = []
        for repo in data.get('items', [])[:15]:
            repos.append({
                'name': repo.get('full_name', ''),
                'url': repo.get('html_url', ''),
                'description': (repo.get('description') or '')[:200],
                'stars': repo.get('stargazers_count', 0),
                'language': repo.get('language', 'N/A'),
                'topics': repo.get('topics', [])[:5]
            })
        print(f"  -> {len(repos)} repo bulundu")
        return repos
    except Exception as e:
        print(f"  -> GitHub hatasi: {e}")
        return []


def fetch_techcrunch():
    """TechCrunch RSS — fonlama haberleri ve startup dunyasi"""
    print("[5/7] TechCrunch cekiliyor...")
    try:
        feed = feedparser.parse('https://techcrunch.com/feed/')
        articles = []
        for entry in feed.entries[:15]:
            # Fonlama, AI, startup haberlerini filtrele
            title = entry.get('title', '')
            summary = entry.get('summary', '')[:300]
            tags = [t.get('term', '') for t in entry.get('tags', [])]
            articles.append({
                'title': title,
                'url': entry.get('link', ''),
                'summary': summary,
                'tags': tags,
                'published': entry.get('published', '')
            })
        print(f"  -> {len(articles)} makale bulundu")
        return articles
    except Exception as e:
        print(f"  -> TechCrunch hatasi: {e}")
        return []


def fetch_devto():
    """Dev.to API — gelistirici community trendleri"""
    print("[6/7] Dev.to cekiliyor...")
    try:
        resp = requests.get(
            'https://dev.to/api/articles?top=1&per_page=15',
            headers=HEADERS,
            timeout=15
        )
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
            print("  -> Dev.to invalid JSON, atlaniyor")
            return []
        articles = []
        for item in data[:15]:
            articles.append({
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'description': (item.get('description') or '')[:200],
                'reactions': item.get('public_reactions_count', 0),
                'comments': item.get('comments_count', 0),
                'tags': item.get('tag_list', []),
                'reading_time': item.get('reading_time_minutes', 0)
            })
        print(f"  -> {len(articles)} makale bulundu")
        return articles
    except Exception as e:
        print(f"  -> Dev.to hatasi: {e}")
        return []


def fetch_arxiv():
    """ArXiv'den en son AI/ML makaleleri — AI spotlight icin"""
    print("[7/7] ArXiv cekiliyor...")
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

def analyze_trends(sources):
    """Toplanan verileri Claude ile analiz et"""
    print("\nClaude ile analiz ediliyor...")

    raw_data = f"""
## Hacker News (Top Stories, score > 50):
{json.dumps(sources['hacker_news'], ensure_ascii=False, indent=2)}

## Product Hunt (Gunun Urunleri):
{json.dumps(sources['product_hunt'], ensure_ascii=False, indent=2)}

## Reddit (r/artificial + r/startups + r/technology + r/SideProject, score > 30):
{json.dumps(sources['reddit'], ensure_ascii=False, indent=2)}

## GitHub Trending (100+ yildiz, dun push edilen repolar):
{json.dumps(sources['github'], ensure_ascii=False, indent=2)}

## TechCrunch (Son haberler, fonlama, startup dunyasi):
{json.dumps(sources['techcrunch'], ensure_ascii=False, indent=2)}

## Dev.to (Gelistirici community trendleri, en populer yazilar):
{json.dumps(sources['devto'], ensure_ascii=False, indent=2)}

## ArXiv (Son AI/ML Arastirma Makaleleri):
{json.dumps(sources['arxiv'], ensure_ascii=False, indent=2)}
"""

    prompt = f"""Sen Zelimkhan mentalitesinde bir trend analisti + girisim danismanisin.
Hedef kitle: Turkiye'de tek kisi calisan, AI araclarini aktif kullanan bir gelistirici-girisimci.
Bu kisi sabah kahvesini icerken 2 dakikada "bugun ne onemli, ne yapmaliyim?" ogrenmek istiyor.

Asagidaki veriler GERCEK API'lerden cekilmistir. SADECE bu verilerden analiz yap. Veri UYDURMA.
Emin olmadigin bir sey varsa "Yeterli veri yok" de.

Tarih: {TODAY}

KAYNAKLARIN:
- Hacker News: Tech dunyasinin nabzi
- Product Hunt: Yeni urun/startup lansmanlari
- Reddit: Topluluk tartismalari ve viral konular
- GitHub: Acik kaynak trendleri ve gelistirici araclari
- TechCrunch: Fonlama haberleri ve startup ekosistemi
- Dev.to: Gelistirici community icgörüleri
- ArXiv: AI/ML arastirma makaleleri

KURALLARIN:
1. Her trendin SONUNDA "Peki Bana Ne?" sorusunu cevapla — solo gelistirici icin ne anlama geliyor?
2. Turkiye pazari acisi: Bu trend Turkiye'de firsat mi tehdit mi?
3. Zelimkhan Prensibi uygula: "Once ihtiyac yarat, sonra cozum sat"
4. Jargonsuz yaz — bankaci, ogretmen, pazarlamaci da anlasin
5. Her firsat icin gercekci "tek kisi MVP" suresi ver
6. TechCrunch verilerini ozellikle "Para Nereye Akiyor" bolumu icin kullan
7. Dev.to verilerini gelistirici trendleri icin degerlendir

Gorevlerin:
1. En onemli 5 trendi belirle (puan, tekrar sikligi, kaynak sayisina gore)
2. Her trend icin: kisa baslik (max 8 kelime) + 2-3 cumle neden onemli + "Peki Bana Ne?" (1 cumle aksiyon) + etki puani (1-10)
3. AI/ML ozel: yeni model/paper/framework varsa 1 paragrafta ozetle, teknik olmadan anlat
4. BUGUN NE YAPMALI: Bu trendlerden bugun uygulanabilecek 1 somut aksiyon
5. Firsat Radar: En guclu uygulama firsati — ne, kime, nasil, tek kisi MVP suresi, tahmini maliyet, Turkiye'de rakip var mi?
6. Para Nereye Akiyor: yatirim/fonlama haberleri (TechCrunch verisine dayanarak)
7. Turkiye Acisi: Bu trendler Turkiye teknoloji ekosistemine nasil yansir?

Format: Sadece JSON dondur, baska hicbir sey yazma:
{{
  "date": "{TODAY}",
  "daily_headline": "Bugunun 1 cumlelik ozeti (gazete manseti gibi, max 15 kelime)",
  "executive_summary": "3 cumle ozet — teknik degil, herkesin anlayacagi dilde",
  "top_trends": [
    {{
      "title": "Max 8 kelime baslik",
      "emoji": "tek emoji",
      "impact_score": 8,
      "why_important": "2-3 cumle, jargonsuz",
      "so_what": "Peki bana ne? Solo gelistirici icin 1 cumle aksiyon",
      "turkey_angle": "Turkiye'de bu ne anlama geliyor? 1 cumle",
      "sources": ["kaynak1"],
      "category": "AI|Startup|Altyapi|Yaratici|Arastirma"
    }}
  ],
  "ai_spotlight": {{
    "title": "Baslik",
    "detail": "2-3 cumle, teknik olmadan",
    "practical_use": "Bunu bugun nasil kullanabilirim? 1 cumle"
  }},
  "today_action": "Bugun yapilabilecek 1 somut sey (link dahil)",
  "opportunity_radar": {{
    "idea": "Urun fikri adi",
    "one_liner": "1 cumle aciklama",
    "target_market": "Kim icin?",
    "turkey_potential": "Turkiye'de potansiyeli var mi?",
    "mvp_time": "Tek kisi MVP suresi",
    "mvp_cost": "Tahmini maliyet",
    "competitors": "Rakipler",
    "zelimkhan_hook": "Ucretsiz deger olarak ne verilir, ucretli ne satilir?"
  }},
  "money_flow": {{
    "title": "Baslik",
    "detail": "1-2 cumle (TechCrunch verisine dayali)"
  }},
  "turkey_corner": "Turkiye ekosistemi icin 2-3 cumle yorum",
  "source_links": ["url1","url2"]
}}
Turkce yaz. Kisa ve oz ol. Emoji kullan ama abartma.

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
    """Profesyonel DOCX rapor olustur — 10/10 kalite"""
    print("\nDOCX rapor olusturuluyor...")

    doc = Document()

    # Stil ayarlari
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)

    # Renk paleti
    BLUE_DARK = RGBColor(0x1B, 0x4F, 0x72)
    ORANGE = RGBColor(0xF3, 0x9C, 0x12)
    GREEN = RGBColor(0x27, 0xAE, 0x60)
    GRAY = RGBColor(0x5D, 0x6D, 0x7E)
    GRAY_LIGHT = RGBColor(0x85, 0x92, 0x9E)

    def add_styled_heading(text, level=1):
        h = doc.add_heading(text, level=level)
        for run in h.runs:
            run.font.color.rgb = BLUE_DARK
        return h

    def add_run_to_para(para, text, color=None, bold=False, italic=False, size=None):
        run = para.add_run(text)
        if color:
            run.font.color.rgb = color
        if bold:
            run.bold = True
        if italic:
            run.italic = True
        if size:
            run.font.size = Pt(size)
        return run

    def add_separator():
        p = doc.add_paragraph()
        run = p.add_run('_' * 60)
        run.font.color.rgb = GRAY_LIGHT
        run.font.size = Pt(8)

    def stars(score):
        try:
            s = int(score)
        except (ValueError, TypeError):
            s = 5
        return '\u2B50' * s + '\u2606' * (10 - s)

    # === KAPAK ===
    doc.add_paragraph()
    doc.add_paragraph()
    cover = doc.add_paragraph()
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run_to_para(cover, '\U0001F4C8 TrendPulse', color=BLUE_DARK, bold=True, size=28)

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run_to_para(date_p, analysis.get('date', TODAY), color=GRAY, size=14)

    headline_p = doc.add_paragraph()
    headline_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run_to_para(headline_p, analysis.get('daily_headline', ''), italic=True, color=BLUE_DARK, size=16)

    add_separator()
    doc.add_page_break()

    # === YONETICI OZETI ===
    add_styled_heading('\u2615 Yonetici Ozeti', level=1)
    summary_p = doc.add_paragraph()
    add_run_to_para(summary_p, analysis.get('executive_summary', 'Ozet mevcut degil.'), size=12)
    note_p = doc.add_paragraph()
    add_run_to_para(note_p, '\u2615 2 dk okuma | 7 kaynaktan derlendi', color=GRAY_LIGHT, italic=True, size=9)
    doc.add_paragraph()

    # === BUGUN NE YAPMALI ===
    add_styled_heading('\U0001F3AF Bugun Ne Yapmali', level=1)
    action_p = doc.add_paragraph()
    add_run_to_para(action_p, analysis.get('today_action', 'Aksiyon bilgisi mevcut degil.'), bold=True, color=BLUE_DARK, size=13)
    add_separator()

    # === TOP 5 TREND ===
    add_styled_heading('\U0001F525 Top 5 Trend', level=1)

    trends = analysis.get('top_trends', [])
    for i, trend in enumerate(trends[:5], 1):
        emoji = trend.get('emoji', '\U0001F525')
        title = trend.get('title', '')
        score = trend.get('impact_score', 5)

        trend_h = doc.add_paragraph()
        add_run_to_para(trend_h, f'{emoji} {i}. {title}', bold=True, color=BLUE_DARK, size=14)
        score_p = doc.add_paragraph()
        add_run_to_para(score_p, f'Etki: {stars(score)}', size=10)

        why_p = doc.add_paragraph()
        add_run_to_para(why_p, 'Neden onemli: ', bold=True, size=11)
        add_run_to_para(why_p, trend.get('why_important', ''), size=11)

        so_p = doc.add_paragraph()
        add_run_to_para(so_p, '\U0001F4A1 Peki bana ne: ', bold=True, color=BLUE_DARK, size=11)
        add_run_to_para(so_p, trend.get('so_what', ''), color=BLUE_DARK, size=11)

        tr_p = doc.add_paragraph()
        add_run_to_para(tr_p, '\U0001F1F9\U0001F1F7 Turkiye: ', bold=True, size=10)
        add_run_to_para(tr_p, trend.get('turkey_angle', ''), italic=True, color=GRAY, size=10)

        sources = trend.get('sources', [])
        if sources:
            src_p = doc.add_paragraph()
            add_run_to_para(src_p, 'Kaynaklar: ' + ', '.join(str(s) for s in sources), color=GRAY_LIGHT, size=8)

        if i < len(trends[:5]):
            add_separator()

    doc.add_paragraph()

    # === AI/ML GUNDEM ===
    add_styled_heading('\U0001F916 AI/ML Gundem', level=1)
    ai = analysis.get('ai_spotlight', {})
    if ai:
        ai_title_p = doc.add_paragraph()
        add_run_to_para(ai_title_p, ai.get('title', ''), bold=True, color=BLUE_DARK, size=13)
        ai_detail_p = doc.add_paragraph()
        add_run_to_para(ai_detail_p, ai.get('detail', ''), size=11)
        ai_use_p = doc.add_paragraph()
        add_run_to_para(ai_use_p, '\U0001F9EA Bugun dene: ', bold=True, color=GREEN, size=11)
        add_run_to_para(ai_use_p, ai.get('practical_use', ''), color=GREEN, size=11)
    doc.add_paragraph()

    # === FIRSAT RADAR ===
    add_styled_heading('\U0001F4A1 Firsat Radar', level=1)
    opp = analysis.get('opportunity_radar', {})
    if opp:
        opp_table = doc.add_table(rows=6, cols=2)
        opp_table.style = 'Light Grid Accent 1'
        opp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        labels = ['Fikir', 'Hedef Pazar', 'Turkiye Potansiyeli', 'MVP Suresi', 'Tahmini Maliyet', 'Rakipler']
        keys = ['idea', 'target_market', 'turkey_potential', 'mvp_time', 'mvp_cost', 'competitors']
        for i, (label, key) in enumerate(zip(labels, keys)):
            opp_table.rows[i].cells[0].text = label
            opp_table.rows[i].cells[1].text = str(opp.get(key, ''))

        doc.add_paragraph()
        one_liner = opp.get('one_liner', '')
        if one_liner:
            ol_p = doc.add_paragraph()
            add_run_to_para(ol_p, one_liner, italic=True, color=GRAY, size=11)

        hook = opp.get('zelimkhan_hook', '')
        if hook:
            hook_p = doc.add_paragraph()
            add_run_to_para(hook_p, 'Zelimkhan Hook: ', bold=True, color=ORANGE, size=12)
            add_run_to_para(hook_p, hook, color=ORANGE, size=12)
    doc.add_paragraph()

    # === PARA NEREYE AKIYOR ===
    add_styled_heading('\U0001F4B0 Para Nereye Akiyor', level=1)
    money = analysis.get('money_flow', {})
    if money:
        money_title_p = doc.add_paragraph()
        add_run_to_para(money_title_p, money.get('title', ''), bold=True, color=BLUE_DARK, size=13)
        money_detail_p = doc.add_paragraph()
        add_run_to_para(money_detail_p, money.get('detail', ''), color=GRAY, size=11)
    doc.add_paragraph()

    # === TURKIYE KOSESI ===
    add_styled_heading('\U0001F1F9\U0001F1F7 Turkiye Kosesi', level=1)
    turkey_p = doc.add_paragraph()
    add_run_to_para(turkey_p, analysis.get('turkey_corner', 'Turkiye yorumu mevcut degil.'), size=11)
    doc.add_paragraph()

    # === KAYNAKLAR ===
    add_styled_heading('\U0001F517 Kaynaklar', level=1)
    links = analysis.get('source_links', [])
    for link in links:
        link_p = doc.add_paragraph()
        add_run_to_para(link_p, f'\u2022 {link}', color=BLUE_DARK, size=9)

    # Footer
    doc.add_paragraph()
    add_separator()
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run_to_para(footer, 'TrendPulse by Zelimkhan Automation | Gunluk otomatik trend raporu | 7 kaynaktan derlendi', color=GRAY_LIGHT, size=8)

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

    headline = analysis.get('daily_headline', '')
    today_action = analysis.get('today_action', '')
    opp = analysis.get('opportunity_radar', {})
    opp_idea = opp.get('idea', '')
    opp_mvp = opp.get('mvp_time', '')

    trends_text = ""
    for i, t in enumerate(analysis.get('top_trends', [])[:5], 1):
        emoji = t.get('emoji', '')
        title = t.get('title', '')
        trends_text += f"\n{i}. {emoji} {title}"

    message = f"""\U0001F4C8 *TrendPulse* \u2014 {TODAY}

\U0001F5DE *{headline}*

\U0001F3AF *Bugun Yap:* {today_action}

\U0001F525 *Top 5:*{trends_text}

\U0001F4A1 *Firsat:* {opp_idea} ({opp_mvp})

_Detayli rapor ektedir_ \u2B07\uFE0F"""

    send_telegram(message)
    send_document(docx_path, caption=f"TrendPulse Raporu - {TODAY}")
    print("  -> Telegram gonderimi tamamlandi")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"{'='*50}")
    print(f"  TrendPulse - {TODAY}")
    print(f"  7 kaynaktan maksimum verim")
    print(f"{'='*50}\n")

    # 1. Veri topla (7 kaynak)
    sources = {
        'hacker_news': fetch_hacker_news(),
        'product_hunt': fetch_product_hunt(),
        'reddit': fetch_reddit(),
        'github': fetch_github_trending(),
        'techcrunch': fetch_techcrunch(),
        'devto': fetch_devto(),
        'arxiv': fetch_arxiv(),
    }

    total = sum(len(v) for v in sources.values())
    print(f"\nToplam {total} veri noktasi toplandi (7 kaynak).")
    for name, data in sources.items():
        print(f"  {name}: {len(data)}")

    if total == 0:
        print("HATA: Hicbir kaynaktan veri alinamadi!")
        send_telegram("*TrendPulse HATA*\nHicbir kaynaktan veri alinamadi.")
        sys.exit(1)

    # 2. Claude ile analiz
    analysis = analyze_trends(sources)

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
