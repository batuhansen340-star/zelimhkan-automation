# ⚙️ Zelimkhan Otomasyon Sistemi

StoryPal için otomatik ops pipeline'ları.

## Pipeline'lar

| Saat | Pipeline | İş |
|------|----------|----|
| 07:00 | 🐛 Bug Dedektifi | GitHub Issues tara, öncelikle, fix öner |
| 08:00 | 🎭 Marketing Fabrikası | Sosyal medya içerik üret |
| 20:00 | 📊 Günlük Özet | Commit özeti + metrik raporu |

## Teknoloji

- **Scheduler:** GitHub Actions (cron)
- **Scripts:** Python 3.12
- **AI:** Claude Sonnet 4.5 (Anthropic API)
- **Bildirim:** Telegram Bot
- **Dashboard:** Streamlit Cloud
- **Maliyet:** ~$1-3/ay (sadece Claude API)

## Kurulum

1. Repo'yu fork/clone et
2. GitHub Secrets ekle: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
3. Actions sekmesinden manuel tetikle
4. Streamlit Cloud'a deploy et (dashboard/app.py)

## Yapı

```
.github/workflows/     → Cron job tanımları
scripts/               → Python pipeline scriptleri
dashboard/             → Streamlit dashboard
data/                  → JSON veri deposu (git tracked)
```
