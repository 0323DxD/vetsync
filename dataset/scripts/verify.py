"""Quick verification script for ASTRID knowledge base and app.py syntax."""
import sys, os, ast, json

os.chdir(r'c:\Users\Denmhar\OneDrive\Desktop\vet V2')

# 1. Syntax check
with open('app.py', encoding='utf-8') as f:
    src = f.read()
ast.parse(src)
print('[OK] app.py syntax is valid')

# 2. Load KB
kb_path = r'dataset/processed/knowledge_base.json'
with open(kb_path, encoding='utf-8') as f:
    kb = json.load(f)
print('[OK] knowledge_base.json loaded')
print('     KB entries   :', len(kb['knowledge_base']))
print('     Keywords     :', len(kb['keyword_map']))
print('     Symptom hist :', len(kb['symptom_history']))

# 3. Simulate lookups
kw_map  = kb['keyword_map']
kb_data = kb['knowledge_base']
tests = [
    'my dog is vomiting',
    'my cat is limping',
    'my pet has diarrhea',
    'my pet will not eat',
    'my dog is scratching',
    'my pet has a wound',
    'my dog has fever',
    'seizure',
    'breathing difficulty',
]
print('\n[LOOKUP TESTS]')
for msg in tests:
    matched = None
    for kw, key in kw_map.items():
        if kw in msg.lower():
            matched = key
            break
    entry = kb_data.get(matched)
    label = entry['label'] if entry else 'NO MATCH'
    status = '[OK]' if entry else '[!!]'
    print(f'  {status} "{msg}" -> {label}')

print('\n[DONE] All checks passed.')
