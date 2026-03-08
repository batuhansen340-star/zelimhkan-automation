# scripts/ai_engine.py
# Claude API wrapper - tüm pipeline'lar bunu kullanır

import os
import json
import re
import anthropic

client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])


def ask_claude(prompt, json_mode=False, model='claude-sonnet-4-5-20250929'):
    """Claude API ile soru sor

    Args:
        prompt: Sorulacak metin
        json_mode: True ise sadece JSON döndürür
        model: Kullanılacak model (varsayılan Sonnet 4.5)
    """
    system = 'Sen bir yazılım geliştirme asistanısın. Türkçe yanıtla.'
    if json_mode:
        system += ' SADECE geçerli JSON döndür, başka metin ekleme. Markdown fence kullanma.'

    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{'role': 'user', 'content': prompt}]
    )

    text = message.content[0].text

    if json_mode:
        text = text.strip()
        # Markdown fence temizligi (```json ... ``` veya ``` ... ```)
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*\n?', '', text)
            text = re.sub(r'\n?```\s*$', '', text)
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"JSON parse hatası (ilk deneme), backtick temizleniyor...")
            # Ikinci deneme: tum backtick'leri kaldir
            cleaned = re.sub(r'```(?:json)?', '', text).strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                print(f"JSON parse hatası (ikinci deneme), raw text sarmalanıyor")
                return {"raw_analysis": text, "parse_error": True}

    return text
