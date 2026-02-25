import requests
import json

url = "https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/?column=&count=10&filter%5BsituacaoRegistro%5D=V&order=asc&page=1"
headers = {
    'Accept': 'application/json',
    'Authorization': 'Guest',
    'X-Requested-With': 'XMLHttpRequest'
}

response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = response.json()
    items = data.get("content", [])
    if items:
        print(json.dumps(items[0], indent=2))
    else:
        print("No items found.")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
