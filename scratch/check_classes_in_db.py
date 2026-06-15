import sqlite3

def main():
    conn = sqlite3.connect('sngpc.db')
    cursor = conn.cursor()
    
    # Query records where principio_ativo matches antibiotic names but classes_terapeuticas does NOT match the keywords
    cursor.execute("""
        SELECT DISTINCT principio_ativo, classes_terapeuticas FROM presentations 
        WHERE lista_controle = 'N/A' 
          AND (
              principio_ativo LIKE '%AMOXICILINA%' 
              OR principio_ativo LIKE '%CEFALEXINA%' 
              OR principio_ativo LIKE '%AZITROMICINA%'
              OR principio_ativo LIKE '%CIPROFLOXACINO%'
              OR principio_ativo LIKE '%CLARITROMICINA%'
              OR principio_ativo LIKE '%ERITROMICINA%'
              OR principio_ativo LIKE '%METRONIDAZOL%'
              OR principio_ativo LIKE '%DOXICICLINA%'
          )
          AND NOT (
              classes_terapeuticas LIKE '%ANTIBIOTICO%'
              OR classes_terapeuticas LIKE '%ANTIBACTERIANO%'
              OR classes_terapeuticas LIKE '%CEFALOSPORINA%'
              OR classes_terapeuticas LIKE '%PENICILINA%'
              OR classes_terapeuticas LIKE '%QUINOLONA%'
              OR classes_terapeuticas LIKE '%RIFAMPICINA%'
              OR classes_terapeuticas LIKE '%RIFAXIMINA%'
              OR classes_terapeuticas LIKE '%SULFA%'
              OR classes_terapeuticas LIKE '%TUBERCULOSTATICO%'
              OR classes_terapeuticas LIKE '%TUBERCULOSE%'
          )
    """)
    rows = cursor.fetchall()
    print(f"Number of items matching PA but not class keywords: {len(rows)}")
    for row in rows[:20]:
        print(f"  PA: {row[0]} | Class: {row[1]}")
        
    conn.close()

if __name__ == "__main__":
    main()
