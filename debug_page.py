from app.core.driver import WebDriverFactory
import json
import time

driver = WebDriverFactory.create_driver(headless=True)
try:
    driver.get("https://consultas.anvisa.gov.br/")
    time.sleep(5)
    
    # Let's fetch page 1 and see the items
    url = "https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/?column=&count=100&filter%5BsituacaoRegistro%5D=V&order=asc&page=1"
    
    script = f"""
        var callback = arguments[arguments.length - 1];
        fetch('{url}', {{
            headers: {{
                'Accept': 'application/json',
                'Authorization': 'Guest',
                'X-Requested-With': 'XMLHttpRequest'
            }}
        }})
        .then(r => r.json())
        .then(data => callback(data))
        .catch(e => callback('ERROR: ' + e));
    """
    
    result = driver.execute_async_script(script)
    with open("data/bulk_page_1.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print("Saved data/bulk_page_1.json")
finally:
    driver.quit()
