# dashboard/app.py
# Zelimkhan Otomasyon Dashboard - Streamlit Cloud'da host edilir

import streamlit as st
import json
import os
from datetime import datetime

st.set_page_config(
    page_title='Zelimkhan Otomasyon',
    page_icon='⚙️',
    layout='wide'
)

st.title('⚙️ Zelimkhan Otomasyon Dashboard')
st.caption('StoryPal Ops - Bug Dedektifi | Marketing Fabrikası | Günlük Özet')

# Sidebar
page = st.sidebar.selectbox(
    'Pipeline Seç',
    ['🐛 Bug Dedektifi', '🎭 Marketing Fabrikası', '📊 Günlük Özet']
)

st.sidebar.divider()
st.sidebar.caption('Veriler her gün otomatik güncellenir.')
st.sidebar.caption('GitHub Actions → Python → Telegram')


def load_data(filename):
    """JSON veri dosyasını yükle"""
    path = f'data/{filename}'
    if os.path.exists(path):
        try:
            return json.loads(open(path).read())
        except json.JSONDecodeError:
            return []
    return []


# ============ BUG DEDEKTİFİ ============
if '🐛' in page:
    st.header('🐛 Bug Dedektifi')
    data = load_data('bugs.json')
    
    if data:
        latest = data[-1]
        date = latest['date'][:16].replace('T', ' ')
        
        # Metrikler
        col1, col2, col3 = st.columns(3)
        bugs = latest['analysis'].get('bugs', [])
        p0 = sum(1 for b in bugs if b.get('priority') == 'P0')
        p1 = sum(1 for b in bugs if b.get('priority') == 'P1')
        
        col1.metric('Toplam Açık Issue', latest['total_issues'])
        col2.metric('🔴 P0 Kritik', p0)
        col3.metric('🟠 P1 Yüksek', p1)
        
        st.caption(f'Son tarama: {date}')
        st.divider()
        
        # Bug listesi
        for b in bugs:
            priority = b.get('priority', 'P3')
            color = '🔴' if priority == 'P0' else '🟠' if priority == 'P1' else '🟡' if priority == 'P2' else '⚪'
            
            with st.expander(f"{color} #{b.get('number', '?')} [{priority}] - Fix: {b.get('fix_time', '?')}"):
                st.write(b.get('suggestion', 'Öneri yok.'))
        
        # Özet
        if latest['analysis'].get('summary'):
            st.info(f"📝 {latest['analysis']['summary']}")
    else:
        st.info('Henüz veri yok. İlk scan çalıştığında burada göreceksin.')


# ============ MARKETING FABRİKASI ============
elif '🎭' in page:
    st.header('🎭 Marketing Fabrikası')
    data = load_data('marketing.json')
    
    if data:
        # Tarih seçici
        dates = [d['date'][:10] for d in data]
        selected_idx = st.selectbox(
            'Tarih seç',
            range(len(dates) - 1, -1, -1),
            format_func=lambda i: dates[i]
        )
        
        entry = data[selected_idx]
        items = entry['content'].get('contents', [])
        
        for item in items:
            platform = item.get('platform', 'unknown')
            emoji = '🐦' if platform == 'twitter' else '📷' if platform == 'instagram' else '📝'
            
            with st.expander(f"{emoji} {platform.title()} - {item.get('type', '')}"):
                st.write(item.get('content', ''))
                
                if item.get('hashtags'):
                    st.caption(f"Hashtags: {' '.join(item['hashtags'])}")
                if item.get('visual_idea'):
                    st.caption(f"🖼️ Görsel: {item['visual_idea']}")
        
        # Kopyala butonu
        if items:
            all_content = '\n\n---\n\n'.join([
                f"[{i['platform'].upper()}]\n{i['content']}"
                for i in items
            ])
            st.text_area('Hepsini kopyala', all_content, height=200)
    else:
        st.info('Henüz içerik yok. İlk üretim sonrası burada göreceksin.')


# ============ GÜNLÜK ÖZET ============
elif '📊' in page:
    st.header('📊 Günlük Özetler')
    data = load_data('summaries.json')
    
    if data:
        # Son 7 günün commit grafiği
        recent = data[-7:]
        if len(recent) > 1:
            chart_data = {
                'Tarih': [d['date'][:10] for d in recent],
                'Commit': [d.get('commits', 0) for d in recent]
            }
            st.bar_chart(chart_data, x='Tarih', y='Commit')
        
        st.divider()
        
        # Özet listesi
        for entry in reversed(data[-7:]):
            date = entry['date'][:10]
            commits = entry.get('commits', 0)
            
            st.subheader(f'📅 {date}  •  {commits} commit')
            st.write(entry.get('summary', 'Özet yok.'))
            st.divider()
    else:
        st.info('Henüz özet yok. İlk rapor sonrası burada göreceksin.')
