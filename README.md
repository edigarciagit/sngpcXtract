# SNGPC Xtractor v2.5

Este projeto é uma ferramenta de extração, processamento e visualização de dados públicos da ANVISA referente a medicamentos controlados (SNGPC).

## 🎯 Objetivo

Automatizar a coleta de dados de produtos registrados na ANVISA, armazená-los de forma estruturada em um banco de dados local e fornecer uma interface web moderna e responsiva para consulta, filtragem e análise dessas informações.

## 🏗 Arquitetura

O projeto segue uma arquitetura modular baseada em serviços, separando claramente as responsabilidades de coleta, armazenamento, API e apresentação.

### Estrutura de Pastas

```
sngpcXtract/
├── app/                  # Núcleo da aplicação Python
│   ├── api/              # Servidor HTTP e endpoints JSON
│   ├── core/             # Gerenciamento de Banco de Dados (SQLite)
│   └── services/         # Lógica de scraping e orquestração
├── frontend/             # Interface Web (HTML/JS/CSS)
├── data/                 # Armazenamento de arquivos brutos (JSON)
├── main.py               # Ponto de entrada da aplicação
└── sngpc.db              # Banco de dados SQLite
```

### Tecnologias Utilizadas

- **Backend**: Python 3.x (com `http.server`, `sqlite3`, `urllib`)
- **Frontend**: Vanilla HTML5, CSS3 (Design System próprio), JavaScript (ES6+)
- **Banco de Dados**: SQLite
- **Scraping**: Requests/Urllib com simulação de headers

## 🚀 Funcionalidades

- **Extração Automatizada**: Coleta dados detalhados de medicamentos diretamente do portal de consultas da Anvisa.
- **Banco de Dados Local**: Armazena informações em SQLite para consultas instantâneas e persistência.
- **Interface Moderna**:
  - Tabela de resultados com paginação (50 itens por página).
  - Badges visuais para identificação rápida da Tarja (🔴 Vermelha, ⚫ Preta, 🟡 Outras).
  - Barra de progresso em tempo real durante a extração.
- **Busca Dinâmica**: Filtros integrados para pesquisar por:
  - Nome Comercial
  - Princípio Ativo
  - Número de Registro
  - Classes Terapêuticas
- **Resiliência**: Capacidade de retomar extrações e reutilizar dados já coletados.

## 🔌 API de Integração Externa (Oracle Sync)

A aplicação disponibiliza um endpoint REST dedicado para integração com sistemas externos (ex: sistemas em Java para sincronização com base Oracle):

* **Endpoint**: `GET /api/external/presentations`
* **Parâmetros de Consulta (Query Params)**:
  * `page` (opcional, padrão `1`): Página atual dos resultados.
  * `size` (opcional, padrão `100`): Quantidade de registros por página.
* **Modelo do Item Retornado**:
  ```json
  {
    "registro_ms": "1039001660013",
    "nome_medicamento": "NUTRICAL D",
    "principio_ativo": "CARBONATO DE CÁLCIO, COLECALCIFEROL",
    "lista_controle": "N/A",
    "cnpj_fabricante": "33349473000158",
    "sku_anvisa": 395088,
    "fabricante_laboratorio": "FARMOQUÍMICA S/A",
    "unidade_medida": 2,
    "codigo_dcb": "01748",
    "codigo_cas": "471-34-1",
    "status_registro_anvisa": "INATIVO"
  }
  ```
  *Nota*: Os campos `codigo_dcb` e `codigo_cas` extraem e retornam apenas os valores correspondentes ao IFA (Ingrediente Farmacêutico Ativo) principal de controle, priorizando a classificação `IFA` ou `BIO` e sem concatenação de múltiplos códigos.

## 🛠 Como Executar

1. **Pré-requisitos**: Python 3.10 ou superior instalado.
2. **Iniciar o Servidor**:
   Execute o comando na raiz do projeto:
   ```bash
   python main.py server
   ```
3. **Acessar a Aplicação**:
   Abra seu navegador e acesse: `http://localhost:8000`

## Autor
edigarciagit