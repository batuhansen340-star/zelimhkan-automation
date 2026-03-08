# scripts/trend_pulse.py
# TrendPulse - Kisisel girisim danismani
# 7 ucretsiz kaynaktan veri ceker, Claude ile analiz eder, DOCX rapor olusturur, Telegram'a gonderir

import os
import sys
import json
import requests
import feedparser
from datetime import datetime, timedelta
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

sys.path.insert(0, os.path.dirname(__file__))
from ai_engine import ask_claude
from telegram_bot import send_telegram, send_document

HEADERS = {'User-Agent': 'TrendPulse/2.0 (by /u/trendpulse_bot)'}
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
        if resp.status_code != 200:
            print(f"  -> Reddit HTTP {resp.status_code}, atlaniyor")
            return []
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
            'User-Agent': 'TrendPulse/2.0',
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
    """Toplanan verileri Claude ile analiz et — kisisel girisim danismani"""
    print("\nClaude ile analiz ediliyor...")

    raw_data = f"""
## Hacker News (Top Stories, score > 50):
{json.dumps(sources['hacker_news'], ensure_ascii=False, indent=2)}

## Product Hunt (Gunun Urunleri):
{json.dumps(sources['product_hunt'], ensure_ascii=False, indent=2)}

## Reddit (r/artificial + r/startups + r/technology + r/SideProject, score > 30):
{json.dumps(sources['reddit'], ensure_ascii=False, indent=2)}

## GitHub Trending (Son 7 gun, en cok yildiz):
{json.dumps(sources['github'], ensure_ascii=False, indent=2)}

## TechCrunch (Son haberler, fonlama, startup dunyasi):
{json.dumps(sources['techcrunch'], ensure_ascii=False, indent=2)}

## Dev.to (Gelistirici community trendleri, en populer yazilar):
{json.dumps(sources['devto'], ensure_ascii=False, indent=2)}

## ArXiv (Son AI/ML Arastirma Makaleleri):
{json.dumps(sources['arxiv'], ensure_ascii=False, indent=2)}
"""

    prompt = f"""Sen benim kisisel girisim danismanim. Adim Batuhan, Turkiye'de bankacilik BI analisti + solo gelistirici + girisimciyim. AI araclarini aktif kullaniyorum. Su an StoryPal (AI cocuk hikaye uygulamasi) ve TrendPulse (bu rapor) uzerinde calisiyorum.

Asagidaki veriler GERCEK API'lerden CEKILMISTIR. SADECE bu verilerden analiz yap. Veri UYDURMA. Emin olmadigin bir sey varsa "Yeterli veri yok" de.

SENIN GOREVIN: Her sabah bana "bugun ne yapmaliyim, nereye bakmaliyim, hangi firsat var?" soylemek. Haber bulteni YAZMA. Beni harekete gecir.

Tarih: {TODAY}

KURALLAR:
1. Her trend icin "BU SANA NE IFADE EDIYOR?" sorusunu cevapla — solo gelistirici olarak bugun ne yapmaliyim?
2. Firsat varsa NET soyle: "Bu alanda Turkiye'de bosluk var, sunu yap"
3. Tool/urun cikmissa: "Bunu bugun dene, link bu" de
4. StoryPal'a uygulanabilecek bir sey varsa direkt soyle
5. Jargon YASAK — herkesin anlayacagi dilde yaz
6. "Ilginc bir gelisme" gibi pasif ifadeler YASAK — "Sunu yap", "Bunu dene", "Bu firsati kacirma" gibi aktif ifadeler kullan
7. Turkiye pazari acisi HER trendte olsun

Gorevlerin:
1. MANSET: Bugunun en onemli 1 cumlelik ozeti — gazete manseti gibi, vurucu
2. BUGUN NE YAP: Bu trendlerden BUGUN uygulanabilecek 3 somut aksiyon (link dahil). "Ilginc" degil, "SIMDI YAP" formatinda.
3. TOP 5 TREND: Her trend icin:
   - Kisa baslik (max 8 kelime)
   - 2 cumle neden onemli (jargonsuz)
   - "Sana ne:" 1 cumle — solo gelistirici olarak bana ne ifade ediyor, ne yapmaliyim
   - "Turkiye:" 1 cumle — bu trend Turkiye'de firsat mi, tehdit mi
   - Etki puani (1-10)
4. FIRSAT RADAR: En guclu 1 uygulama firsati — detayli:
   - Fikir adi + 1 cumle aciklama
   - Kime satilir?
   - Turkiye'de rakip var mi? (Varsa adini yaz)
   - Tek kisi MVP: kac hafta, hangi tech stack, tahmini maliyet
   - Zelimkhan modeli: ucretsiz ne verilir, ucretli ne satilir?
   - "Bu firsati kacirma cunku..." 1 cumle
5. AI SPOTLIGHT: Yeni cikan 1 AI tool/model/paper — teknik olmadan, "bunu su isine kullanabilirsin" formatinda
6. PARA NEREYE AKIYOR: Yatirim haberleri (varsa). Yoksa "Bu hafta one cikan fonlama haberi yok" de.
7. STORYPAL ICIN: Bu trendlerden StoryPal'a uygulanabilecek 1 sey varsa yaz. Yoksa null dondur.

Format: Sadece JSON dondur, baska hicbir sey yazma, markdown formati kullanma:
{{
  "date": "{TODAY}",
  "headline": "Vurucu manset, max 15 kelime",
  "today_actions": [
    {{"action": "Sunu yap (aktif cumle)", "link": "url", "why": "Cunku..."}},
    {{"action": "Bunu dene", "link": "url", "why": "Cunku..."}},
    {{"action": "Suna bak", "link": "url", "why": "Cunku..."}}
  ],
  "executive_summary": "3 cumle, herkesin anlayacagi dilde, aktif",
  "top_trends": [
    {{
      "title": "Max 8 kelime",
      "emoji": "tek emoji",
      "impact_score": 8,
      "why": "2 cumle, jargonsuz",
      "action_for_you": "Solo gelistirici olarak bugun ne yapmaliyim, 1 cumle",
      "turkey": "Turkiye'de bu ne anlama geliyor, 1 cumle",
      "sources": ["url1"],
      "category": "AI|Startup|Altyapi|Yaratici|Arastirma"
    }}
  ],
  "opportunity": {{
    "name": "Fikir adi",
    "one_liner": "1 cumle",
    "who_buys": "Kime satilir",
    "turkey_competitor": "Rakip var mi, adi ne",
    "mvp_weeks": "Kac hafta",
    "mvp_stack": "Hangi teknolojiler",
    "mvp_cost": "Tahmini maliyet",
    "free_hook": "Ucretsiz ne verilir",
    "paid_product": "Ucretli ne satilir",
    "why_now": "Bu firsati kacirma cunku..."
  }},
  "ai_tool": {{
    "name": "Tool/model adi",
    "what": "Ne yapiyor, 1 cumle",
    "use_case": "Sen bunu su isine kullanabilirsin",
    "link": "url"
  }},
  "money_flow": "1-2 cumle veya 'Bu hafta one cikan fonlama haberi yok'",
  "storypal_tip": "StoryPal'a uygulanabilecek 1 sey veya null",
  "sources": ["url1", "url2"]
}}
Turkce yaz. Kisa, net, aksiyon odakli. Beni harekete gecir.

VERILER:
{raw_data}
"""

    result = ask_claude(prompt, json_mode=True)
    print("  -> Analiz tamamlandi")
    return result


# ============================================================
# DOCX RAPOR OLUSTURMA
# ============================================================

def _set_cell_shading(cell, color_hex):
    """Hucreye arka plan rengi ekle"""
    shading = cell._element.get_or_add_tcPr()
    shading_elem = shading.makeelement(qn('w:shd'), {
        qn('w:val'): 'clear',
        qn('w:color'): 'auto',
        qn('w:fill'): color_hex
    })
    shading.append(shading_elem)


def create_docx_report(analysis):
    """Kisisel girisim danismani DOCX raporu"""
    print("\nDOCX rapor olusturuluyor...")

    doc = Document()

    style = doc.styles['Normal']
    font = style.font
    font.size = Pt(11)

    # Renk paleti
    BLUE_DARK = RGBColor(0x1B, 0x4F, 0x72)
    BLUE_MED = RGBColor(0x2E, 0x86, 0xC1)
    ORANGE = RGBColor(0xF3, 0x9C, 0x12)
    GREEN = RGBColor(0x27, 0xAE, 0x60)
    GRAY = RGBColor(0x7F, 0x8C, 0x8D)
    GRAY_LIGHT = RGBColor(0x95, 0xA5, 0xA6)

    def add_run(para, text, color=None, bold=False, italic=False, size=None):
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

    def heading(text, level=1):
        h = doc.add_heading(text, level=level)
        for run in h.runs:
            run.font.color.rgb = BLUE_DARK
        return h

    def separator():
        p = doc.add_paragraph()
        r = p.add_run('_' * 65)
        r.font.color.rgb = GRAY_LIGHT
        r.font.size = Pt(6)

    def stars(score):
        try:
            s = int(score)
        except (ValueError, TypeError):
            s = 5
        return '\u2B50' * s + '\u2606' * (10 - s)

    # ========== KAPAK ==========
    doc.add_paragraph()
    cover = doc.add_paragraph()
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(cover, '\U0001F4C8 TrendPulse', color=BLUE_DARK, bold=True, size=28)

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(date_p, analysis.get('date', TODAY), color=GRAY, size=12)

    hl = analysis.get('headline', analysis.get('daily_headline', ''))
    if hl:
        hl_p = doc.add_paragraph()
        hl_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_run(hl_p, hl, italic=True, color=BLUE_MED, size=18)

    separator()
    doc.add_page_break()

    # ========== BUGUN NE YAP (en ust, en gorunur) ==========
    heading('\U0001F3AF BUGUN NE YAP', level=1)

    actions = analysis.get('today_actions', [])
    if actions:
        for i, act in enumerate(actions[:3], 1):
            action_text = act.get('action', '') if isinstance(act, dict) else str(act)
            why_text = act.get('why', '') if isinstance(act, dict) else ''
            link_text = act.get('link', '') if isinstance(act, dict) else ''

            # Aksiyon satiri
            act_table = doc.add_table(rows=1, cols=1)
            act_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            cell = act_table.rows[0].cells[0]
            _set_cell_shading(cell, 'FEF9E7')

            cp = cell.paragraphs[0]
            add_run(cp, f'  {i}. ', bold=True, color=ORANGE, size=13)
            add_run(cp, action_text, bold=True, color=BLUE_DARK, size=12)
            if why_text:
                why_p = cell.add_paragraph()
                add_run(why_p, f'     {why_text}', color=GRAY, italic=True, size=9)
            if link_text:
                link_p = cell.add_paragraph()
                add_run(link_p, f'     {link_text}', color=BLUE_MED, size=8)
            doc.add_paragraph()  # bosluk
    else:
        # Fallback: eski format
        ta = analysis.get('today_action', '')
        if ta:
            p = doc.add_paragraph()
            add_run(p, ta, bold=True, color=BLUE_DARK, size=13)

    separator()

    # ========== YONETICI OZETI ==========
    heading('\u2615 Yonetici Ozeti', level=1)
    summary_table = doc.add_table(rows=1, cols=1)
    summary_cell = summary_table.rows[0].cells[0]
    _set_cell_shading(summary_cell, 'EBF5FB')
    sp = summary_cell.paragraphs[0]
    add_run(sp, analysis.get('executive_summary', 'Ozet mevcut degil.'), size=12)
    note_p = summary_cell.add_paragraph()
    note_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    add_run(note_p, '\u2615 2 dk okuma | 7 kaynak', color=GRAY_LIGHT, italic=True, size=8)
    doc.add_paragraph()

    # ========== TOP 5 TREND ==========
    heading('\U0001F525 TOP 5 TREND', level=1)

    trends = analysis.get('top_trends', [])
    for i, trend in enumerate(trends[:5], 1):
        emoji = trend.get('emoji', '\U0001F525')
        title = trend.get('title', '')
        score = trend.get('impact_score', 5)

        # Baslik
        th = doc.add_paragraph()
        add_run(th, f'{emoji} {i}. {title}', bold=True, color=BLUE_DARK, size=13)

        # Etki puani
        sp = doc.add_paragraph()
        add_run(sp, f'Etki: {stars(score)}', size=10)

        # Neden onemli
        why_text = trend.get('why', trend.get('why_important', ''))
        if why_text:
            wp = doc.add_paragraph()
            add_run(wp, why_text, size=11)

        # Sana ne
        action_text = trend.get('action_for_you', trend.get('so_what', ''))
        if action_text:
            ap = doc.add_paragraph()
            add_run(ap, '\U0001F3AF Sana ne: ', bold=True, color=BLUE_DARK, size=11)
            add_run(ap, action_text, color=BLUE_DARK, size=11)

        # Turkiye
        turkey_text = trend.get('turkey', trend.get('turkey_angle', ''))
        if turkey_text:
            tp = doc.add_paragraph()
            add_run(tp, '\U0001F1F9\U0001F1F7 Turkiye: ', bold=True, size=10)
            add_run(tp, turkey_text, italic=True, color=GRAY, size=10)

        # Kaynaklar
        trend_sources = trend.get('sources', [])
        if trend_sources:
            srcp = doc.add_paragraph()
            add_run(srcp, 'Kaynaklar: ' + ', '.join(str(s) for s in trend_sources), color=GRAY_LIGHT, size=8)

        if i < len(trends[:5]):
            separator()

    doc.add_paragraph()

    # ========== FIRSAT RADAR ==========
    heading('\U0001F4A1 FIRSAT RADAR', level=1)
    opp = analysis.get('opportunity', analysis.get('opportunity_radar', {}))
    if opp:
        opp_name = opp.get('name', opp.get('idea', ''))
        opp_one = opp.get('one_liner', '')
        if opp_name:
            np = doc.add_paragraph()
            add_run(np, f'{opp_name}', bold=True, color=BLUE_DARK, size=14)
            if opp_one:
                add_run(np, f' — {opp_one}', italic=True, color=GRAY, size=11)

        opp_table = doc.add_table(rows=6, cols=2)
        opp_table.style = 'Light Grid Accent 1'
        opp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        rows_data = [
            ('Kime Satilir', opp.get('who_buys', opp.get('target_market', ''))),
            ('Turkiye Rakip', opp.get('turkey_competitor', opp.get('competitors', ''))),
            ('MVP Suresi', opp.get('mvp_weeks', opp.get('mvp_time', ''))),
            ('Tech Stack', opp.get('mvp_stack', '')),
            ('Maliyet', opp.get('mvp_cost', '')),
            ('Turkiye Potansiyeli', opp.get('turkey_potential', '')),
        ]
        for i, (label, value) in enumerate(rows_data):
            opp_table.rows[i].cells[0].text = label
            opp_table.rows[i].cells[1].text = str(value) if value else ''

        doc.add_paragraph()

        # Zelimkhan Hook
        free_hook = opp.get('free_hook', opp.get('zelimkhan_hook', ''))
        paid_product = opp.get('paid_product', '')
        if free_hook:
            hp = doc.add_paragraph()
            add_run(hp, '\U0001F3A3 Zelimkhan Hook: ', bold=True, color=ORANGE, size=12)
            if paid_product:
                add_run(hp, f'Ucretsiz \u2192 {free_hook} | Ucretli \u2192 {paid_product}', color=ORANGE, size=11)
            else:
                add_run(hp, free_hook, color=ORANGE, size=11)

        # Why now
        why_now = opp.get('why_now', '')
        if why_now:
            wnp = doc.add_paragraph()
            add_run(wnp, f'\u26A1 {why_now}', bold=True, color=BLUE_MED, size=11)

    doc.add_paragraph()

    # ========== AI SPOTLIGHT ==========
    heading('\U0001F916 AI SPOTLIGHT', level=1)
    ai = analysis.get('ai_tool', analysis.get('ai_spotlight', {}))
    if ai:
        ai_name = ai.get('name', ai.get('title', ''))
        ai_what = ai.get('what', ai.get('detail', ''))
        ai_use = ai.get('use_case', ai.get('practical_use', ''))
        ai_link = ai.get('link', '')

        if ai_name:
            anp = doc.add_paragraph()
            add_run(anp, ai_name, bold=True, color=BLUE_DARK, size=13)
        if ai_what:
            awp = doc.add_paragraph()
            add_run(awp, ai_what, size=11)
        if ai_use:
            aup = doc.add_paragraph()
            add_run(aup, '\U0001F4A1 Senin icin: ', bold=True, color=BLUE_DARK, size=11)
            add_run(aup, ai_use, color=BLUE_DARK, size=11)
        if ai_link:
            alp = doc.add_paragraph()
            add_run(alp, ai_link, color=BLUE_MED, size=9)

    doc.add_paragraph()

    # ========== PARA NEREYE AKIYOR ==========
    heading('\U0001F4B0 PARA NEREYE AKIYOR', level=1)
    money = analysis.get('money_flow', '')
    if isinstance(money, dict):
        money_text = f"{money.get('title', '')} — {money.get('detail', '')}"
    else:
        money_text = str(money) if money else 'Bu hafta one cikan fonlama haberi yok'
    mp = doc.add_paragraph()
    add_run(mp, money_text, size=11)
    doc.add_paragraph()

    # ========== STORYPAL IPUCU ==========
    storypal = analysis.get('storypal_tip')
    if storypal:
        heading('\U0001F4F1 STORYPAL IPUCU', level=1)
        sp_table = doc.add_table(rows=1, cols=1)
        sp_cell = sp_table.rows[0].cells[0]
        _set_cell_shading(sp_cell, 'EAFAF1')
        spp = sp_cell.paragraphs[0]
        add_run(spp, str(storypal), color=GREEN, size=11)
        doc.add_paragraph()

    # ========== KAYNAKLAR ==========
    heading('\U0001F517 KAYNAKLAR', level=1)
    links = analysis.get('sources', analysis.get('source_links', []))
    for i, link in enumerate(links, 1):
        lp = doc.add_paragraph()
        add_run(lp, f'{i}. {link}', color=BLUE_MED, size=9)

    # Footer
    doc.add_paragraph()
    separator()
    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(footer, f'TrendPulse by Zelimkhan Automation | Kisisel girisim danismanin | {TODAY}', color=GRAY_LIGHT, size=8)

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

    headline = analysis.get('headline', analysis.get('daily_headline', ''))

    # Bugun ne yap
    actions = analysis.get('today_actions', [])
    actions_text = ""
    for i, act in enumerate(actions[:3], 1):
        if isinstance(act, dict):
            actions_text += f"\n{i}. {act.get('action', '')}"
        else:
            actions_text += f"\n{i}. {act}"
    if not actions_text:
        ta = analysis.get('today_action', '')
        if ta:
            actions_text = f"\n1. {ta}"

    # Top 5
    trends_text = ""
    for i, t in enumerate(analysis.get('top_trends', [])[:5], 1):
        emoji = t.get('emoji', '')
        title = t.get('title', '')
        trends_text += f"\n{i}. {emoji} {title}"

    # Firsat
    opp = analysis.get('opportunity', analysis.get('opportunity_radar', {}))
    opp_name = opp.get('name', opp.get('idea', ''))
    opp_one = opp.get('one_liner', '')
    opp_mvp = opp.get('mvp_weeks', opp.get('mvp_time', ''))
    opp_cost = opp.get('mvp_cost', '')

    # AI tool
    ai = analysis.get('ai_tool', analysis.get('ai_spotlight', {}))
    ai_name = ai.get('name', ai.get('title', ''))
    ai_use = ai.get('use_case', ai.get('practical_use', ''))

    message = f"""\U0001F4C8 *TrendPulse* \u2014 {TODAY}

\U0001F5DE *{headline}*

\U0001F3AF *BUGUN NE YAP:*{actions_text}

\U0001F525 *Top 5:*{trends_text}

\U0001F4A1 *Firsat:* {opp_name} \u2014 {opp_one}
\u23F1 MVP: {opp_mvp} | \U0001F4B0 {opp_cost}

\U0001F916 *Bugun dene:* {ai_name} \u2192 {ai_use}

_Detayli rapor_ \u2B07\uFE0F"""

    send_telegram(message)
    send_document(docx_path, caption=f"TrendPulse Raporu - {TODAY}")
    print("  -> Telegram gonderimi tamamlandi")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"{'='*50}")
    print(f"  TrendPulse - Kisisel Girisim Danismani")
    print(f"  {TODAY} | 7 kaynak")
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
