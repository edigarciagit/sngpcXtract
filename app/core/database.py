import sqlite3
import json
import os
from datetime import datetime

DB_NAME = "sngpc.db"

class Database:
    @staticmethod
    def _get_connection():
        return sqlite3.connect(DB_NAME)

    @staticmethod
    def init_db():
        conn = Database._get_connection()
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presentations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_produto INTEGER,
                nome_comercial TEXT,
                numero_registro TEXT,
                apresentacao TEXT,
                embalagem TEXT,
                validade TEXT,
                tarja TEXT,
                principio_ativo TEXT,
                classes_terapeuticas TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_codigo_produto ON presentations (codigo_produto)')
        
        conn.commit()
        conn.close()

    @staticmethod
    def clear_data():
        """Deletes all data from the presentations table"""
        conn = Database._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM presentations')
            conn.commit()
            print("Database cleared.", flush=True)
        except Exception as e:
            print(f"Error clearing database: {e}")
        finally:
            conn.close()

    @staticmethod
    def save_product(code, data):
        """
        Parses the product JSON and inserts flattened presentation rows.
        Deletes existing entries for this product code first to avoid duplicates on re-run.
        """
        if not data or not isinstance(data, (dict, list)):
            return

        conn = Database._get_connection()
        cursor = conn.cursor()

        try:
            # Delete existing for this product to allow updates
            cursor.execute('DELETE FROM presentations WHERE codigo_produto = ?', (code,))

            # Handle list or dict root
            if isinstance(data, list):
                root_objs = data
            else:
                content = data.get("content", []) if "content" in data else [data]
                root_objs = content

            for root in root_objs:
                if not root:
                    continue

                prod_data = root.get("produto") or {}
                codigo_produto = prod_data.get("codigo") or root.get("codigoProduto") or code
                nome_comercial = prod_data.get("nome") or root.get("nomeComercial")
                numero_registro = prod_data.get("numeroRegistro") or root.get("numeroRegistro")
                
                apresentacoes = root.get("apresentacoes", [])
                
                # If no presentations, insert a placeholder row? 
                # Or just skip? The requirement implies we want the results.
                # Let's insert a row with NULL/Empty presentation info if list is empty
                if not apresentacoes:
                     cursor.execute('''
                        INSERT INTO presentations (
                            codigo_produto, nome_comercial, numero_registro, 
                            apresentacao, embalagem, validade
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (codigo_produto, nome_comercial, numero_registro, "N/A", "N/A", "N/A"))
                else:
                    for apt in apresentacoes:
                        if not apt: 
                            continue
                            
                        apresentacao = apt.get("descricao") or apt.get("nome") or apt.get("apresentacao")
                        embalagem_primaria = apt.get("embalagemPrimaria") or {}
                        embalagem = embalagem_primaria.get("descricao")
                        validade = apt.get("validade")
                        
                        # New fields
                        tarja = apt.get("tarja")
                        
                        # Root fields
                        principio_ativo = root.get("principioAtivo")
                        
                        classes = root.get("classesTerapeuticas", [])
                        classes_str = ", ".join(classes) if isinstance(classes, list) else str(classes)

                        # New Mapping Logic per user request
                        # 1. numero_registro comes from distinct presentation (13 digits)
                        # 2. nome_comercial is concatenated with apresentacao
                        
                        registro_apresentacao = apt.get("registro")
                        
                        # Concatenate Name + Presentation
                        full_product_name = f"{nome_comercial} - {apresentacao}" if apresentacao else nome_comercial

                        cursor.execute('''
                            INSERT INTO presentations (
                                codigo_produto, nome_comercial, numero_registro, 
                                apresentacao, embalagem, validade,
                                tarja, principio_ativo, classes_terapeuticas
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (codigo_produto, full_product_name, registro_apresentacao, apresentacao, embalagem, validade, tarja, principio_ativo, classes_str))
            
            conn.commit()
        except Exception as e:
            print(f"DB Error saving {code}: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_presentations(page=1, size=10, search_query=None):
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row # Access columns by name
        cursor = conn.cursor()
        
        offset = (page - 1) * size
        
        where_clause = ""
        params = []
        
        if search_query:
            where_clause = """
                WHERE nome_comercial LIKE ? 
                OR principio_ativo LIKE ? 
                OR numero_registro LIKE ?
                OR classes_terapeuticas LIKE ?
                OR tarja LIKE ?
            """
            search_param = f"%{search_query}%"
            params = [search_param] * 5
            
        params.extend([size, offset])
        
        cursor.execute(f'''
            SELECT * FROM presentations 
            {where_clause}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
        ''', params)
        
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        
        conn.close()
        return result

    @staticmethod
    def get_total_count(search_query=None):
        conn = Database._get_connection()
        cursor = conn.cursor()
        
        if search_query:
            search_param = f"%{search_query}%"
            cursor.execute('''
                SELECT COUNT(*) FROM presentations 
                WHERE nome_comercial LIKE ? 
                OR principio_ativo LIKE ? 
                OR numero_registro LIKE ?
                OR classes_terapeuticas LIKE ?
                OR tarja LIKE ?
            ''', (search_param, search_param, search_param, search_param, search_param))
        else:
            cursor.execute('SELECT COUNT(*) FROM presentations')
            
        count = cursor.fetchone()[0]
        conn.close()
        return count

    @staticmethod
    def get_all_presentations_raw():
        conn = Database._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM presentations ORDER BY codigo_produto')
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result
