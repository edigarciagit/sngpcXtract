import json
try:
    with open('data/bulk_page_1.json', encoding='utf-8') as f:
        data = json.load(f)
    items = data.get('content', [])
    print(f"Total items in page: {len(items)}")
    
    ghosts = []
    for i in items:
        p = i.get('produto', {})
        situacao = p.get('situacaoApresentacao')
        acancelar = p.get('acancelar')
        tipo = p.get('tipoAutorizacao')
        
        if situacao != 'Ativo' or acancelar is True or tipo != 'REGISTRADO':
            ghosts.append({
                "codigo": p.get('codigo'),
                "situacao": situacao,
                "acancelar": acancelar,
                "tipo": tipo
            })
            
    print(f"Potential ghost items found: {len(ghosts)}")
    for g in ghosts:
        print(g)
except Exception as e:
    print(f"Error: {e}")
