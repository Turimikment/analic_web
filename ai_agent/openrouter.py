import os
import requests

API_URL = 'https://openrouter.ai/api/v1/chat/completions'


def _call(messages, temperature=0.45):
    api_key = os.environ.get('OPENROUTER_API_KEY','').strip()
    model = os.environ.get('OPENROUTER_MODEL','openrouter/free').strip()
    if not api_key:
        raise RuntimeError('OPENROUTER_API_KEY не настроен')
    response=requests.post(API_URL,headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json'},json={'model':model,'messages':messages,'temperature':temperature},timeout=30)
    if not response.ok:
        raise RuntimeError(f'OpenRouter HTTP {response.status_code}: {(response.text or "")[:300]}')
    data=response.json()
    try:
        return data['choices'][0]['message']['content'].strip()
    except Exception as exc:
        raise RuntimeError('OpenRouter вернул неожиданный ответ') from exc


def customer_answer(system_prompt, history, question):
    messages=[{'role':'system','content':system_prompt}]
    messages.extend(history)
    messages.append({'role':'user','content':question})
    return _call(messages)


def make_review(review_prompt, scenario_prompt, history):
    transcript='\n'.join(f"{m['role'].upper()}: {m['content']}" for m in history)
    return _call([{'role':'system','content':review_prompt},{'role':'user','content':f'Эталон сценария:\n{scenario_prompt}\n\nИстория интервью:\n{transcript}'}],temperature=0.2)
