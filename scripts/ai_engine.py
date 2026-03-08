# scripts/ai_engine.py
# Claude API wrapper - tüm pipeline'lar bunu kullanır

import os
import json
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
        max_tokens=4096,
        system=system,
        messages=[{'role': 'user', 'content': prompt}]
    )

    text = message.content[0].text

    if json_mode:
        # JSON parçala (bazen markdown fence içinde gelir)
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[1].rsplit('```', 1)[0]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"JSON parse hatası, raw text sarmalanıyor")
            return {"raw_analysis": text}

    return text
