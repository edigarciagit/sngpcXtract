import os
import json
import urllib.request
import urllib.parse
import time
from app.core.database import Database
from app.services.orchestrator import ExtractionOrchestrator

def main():
    print("Testing Report System...")
    Database.init_db()
    
    reg_keep = '9999990000001'
    reg_modify = '9999990000002'
    reg_new = '9999990000003'
    
    # 1. Ensure mock records do not exist
    conn = Database._get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM presentations WHERE registro IN (?, ?, ?)", (reg_keep, reg_modify, reg_new))
    cursor.execute("DELETE FROM bulk_products WHERE codigo_produto IN (999991, 999992, 999993)")
    
    # Insert reg_keep and reg_modify into database so they exist in pre-state
    cursor.execute("""
        INSERT INTO presentations (registro, numero_registro, codigo_produto, nome_comercial, principio_ativo, fabricante, lista_controle, ativa)
        VALUES (?, '999999000', 999991, 'MOCK KEEP', 'PRINCIPLE A', 'FAB A', 'N/A', 1)
    """, (reg_keep,))
    
    cursor.execute("""
        INSERT INTO presentations (registro, numero_registro, codigo_produto, nome_comercial, principio_ativo, fabricante, lista_controle, ativa)
        VALUES (?, '999999000', 999992, 'MOCK MODIFY', 'PRINCIPLE B', 'FAB B', 'N/A', 1)
    """, (reg_modify,))
    
    # Insert bulk queue products for correct stats
    cursor.execute("INSERT INTO bulk_products (codigo_produto, status) VALUES (999991, 'PROCESSED')")
    cursor.execute("INSERT INTO bulk_products (codigo_produto, status) VALUES (999992, 'PROCESSED')")
    cursor.execute("INSERT INTO bulk_products (codigo_produto, status) VALUES (999993, 'FAILED')")
    
    conn.commit()
    conn.close()
    
    # 2. Capture Pre-state from Database
    orchestrator = ExtractionOrchestrator()
    db_pre_state = {}
    conn = Database._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT registro, nome_comercial, principio_ativo, lista_controle, fabricante FROM presentations")
    for row in cursor.fetchall():
        db_pre_state[row[0]] = {
            "nome_comercial": row[1],
            "principio_ativo": row[2],
            "lista_controle": row[3],
            "fabricante": row[4]
        }
    conn.close()
    
    # 3. Simulate post-state database changes:
    # Modify reg_modify (change list_controle to 'A1') and insert reg_new
    conn = Database._get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE presentations SET lista_controle = 'A1' WHERE registro = ?", (reg_modify,))
    cursor.execute("""
        INSERT INTO presentations (registro, numero_registro, codigo_produto, nome_comercial, principio_ativo, fabricante, lista_controle, ativa)
        VALUES (?, '999999000', 999993, 'MOCK NEW', 'PRINCIPLE C', 'FAB C', 'B1', 1)
    """, (reg_new,))
    conn.commit()
    conn.close()
    
    # Set mock orchestrator status fields to calculate duration
    orchestrator.status["startTime"] = time.time() - 65
    orchestrator.status["state"] = "COMPLETED"
    orchestrator.status["message"] = "Mock sync run completed."
    
    # 4. Generate report
    print("Generating mock report...")
    orchestrator._generate_and_save_report(db_pre_state)
    
    # 5. Clean database mock entries
    conn = Database._get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM presentations WHERE registro IN (?, ?, ?)", (reg_keep, reg_modify, reg_new))
    cursor.execute("DELETE FROM bulk_products WHERE codigo_produto IN (999991, 999992, 999993)")
    conn.commit()
    conn.close()
    
    # 6. Test endpoints
    print("Testing GET /api/reports...")
    BASE = "http://localhost:8000"
    try:
        with urllib.request.urlopen(f"{BASE}/api/reports") as res:
            reports = json.loads(res.read().decode('utf-8'))
            print(f"Reports List: Found {len(reports)} reports.")
            if len(reports) > 0:
                print("PASS: Reports list is not empty.")
                latest_report = reports[0]
                print(f"Latest Report Summary: {latest_report}")
                
                # Check properties
                assert latest_report.get("report_id") is not None
                assert latest_report.get("new_presentations_count") == 1
                assert latest_report.get("updated_presentations_count") == 1
                print("PASS: Summary fields match expected diff count (1 new, 1 updated).")
                
                # Query detail
                report_id = latest_report.get("report_id")
                print(f"Testing GET /api/reports/detail?id={report_id}...")
                with urllib.request.urlopen(f"{BASE}/api/reports/detail?id={report_id}") as detail_res:
                    detail = json.loads(detail_res.read().decode('utf-8'))
                    print("PASS: Detail endpoint retrieved successfully.")
                    
                    new_list = detail.get("new_presentations", [])
                    updated_list = detail.get("updated_presentations", [])
                    print(f"New Presentations in report: {new_list}")
                    print(f"Updated Presentations in report: {updated_list}")
                    
                    assert len(new_list) == 1
                    assert new_list[0].get("registro") == reg_new
                    assert len(updated_list) == 1
                    assert updated_list[0].get("registro") == reg_modify
                    assert updated_list[0].get("lista_controle") == "A1"
                    assert updated_list[0].get("previous", {}).get("lista_controle") == "N/A"
                    print("PASS: All detailed differences match expected results exactly!")
            else:
                print("FAIL: Reports list is empty.")
    except Exception as e:
        print(f"FAIL: Error during endpoint tests: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()
