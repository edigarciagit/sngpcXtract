from app.core.driver import WebDriverFactory
import json
import time

driver = WebDriverFactory.create_driver(headless=True)
try:
    driver.get("https://consultas.anvisa.gov.br/")
    time.sleep(5)
    
    # known failing code
    code = 34416
    url = f"https://consultas.anvisa.gov.br/api/consulta/medicamento/produtos/?column=&count=10&filter%5Bcodigo%5D={code}&order=asc&page=1"
    
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
    with open(f"data/inspect_{code}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Saved data/inspect_{code}.json")
finally:
    driver.quit()
