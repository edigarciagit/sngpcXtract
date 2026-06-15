let pollInterval;
let currentPage = 1;
const pageSize = 50;
let searchTimeout;
let logPollInterval;
let isConfirming = false;
let loadedPresentations = [];

// --- Search Logic ---
document.getElementById('search-input').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadResults(1);
    }, 400);
});

document.getElementById('list-filter').addEventListener('change', () => {
    loadResults(1);
});

// --- Core Logic ---
async function startExtraction() {
    setLoading(true);
    isConfirming = false; // Reset lock for new run
    const reuse = document.getElementById('reuse-flag').checked;
    const inactiveOnly = document.getElementById('inactive-only-flag').checked;
    try {
        const res = await fetch('/api/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reuse: reuse, inactive_only: inactiveOnly })
        });
        const data = await res.json();

        if (data.success) {
            pollInterval = setInterval(checkProgress, 4000);
        } else {
            alert("Erro ao iniciar: " + data.message);
            setLoading(false);
        }
    } catch (e) {
        console.error(e);
        setLoading(false);
    }
}

async function checkProgress() {
    try {
        const res = await fetch('/api/progress');
        const status = await res.json();

        updateUI(status);

        if (status.state === 'AWAITING_CONFIRMATION' && !isConfirming) {
            isConfirming = true;
            const count = status.total || 0;
            document.getElementById('modal-message').textContent = `Foram encontrados ${count} produtos. Deseja prosseguir com a extração total?`;
            document.getElementById('confirm-modal').style.display = 'flex';
        }

        if (status.state === 'COMPLETED') {
            clearInterval(pollInterval);
            setLoading(false);
            loadResults(1);
        } else if (status.state === 'ERROR') {
            clearInterval(pollInterval);
            setLoading(false);
        }
    } catch (e) {
        console.error("Poll Error", e);
    }
}

// --- Log Polling Removed ---

// --- UI Updates ---
function updateUI(status) {
    document.getElementById('progress-fill').style.width = status.percent + '%';
    document.getElementById('percent-display').textContent = status.percent + '%';

    if (status.elapsedTime) {
        document.getElementById('timer-display').textContent = status.elapsedTime;
    }

    let msg = status.message;
    if (msg.length > 30) msg = msg.substring(0, 27) + '...';
    document.getElementById('status-text').textContent = `[${status.state}] ${msg}`;
}

function setLoading(isLoading) {
    const btn = document.getElementById('start-btn');
    const abortBtn = document.getElementById('abort-btn');
    btn.disabled = isLoading;
    btn.innerHTML = isLoading ? '<span>PROCESSANDO...</span>' : '<span>INICIAR PROCESSO</span>';

    // Toggle abort button
    abortBtn.style.display = isLoading ? 'flex' : 'none';
}

async function loadResults(page) {
    currentPage = page;
    const tbody = document.querySelector('#results-table tbody');
    const empty = document.getElementById('empty-state');

    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-secondary); padding: 32px;">CARREGANDO DADOS...</td></tr>';
    empty.style.display = 'none';

    const searchQuery = document.getElementById('search-input').value;
    const selectedList = document.getElementById('list-filter').value;
    let url = `/api/results?page=${page}&size=${pageSize}`;
    if (searchQuery) {
        url += `&q=${encodeURIComponent(searchQuery)}`;
    }
    if (selectedList) {
        url += `&list=${encodeURIComponent(selectedList)}`;
    }

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (data.totalElements > 0) {
            loadedPresentations = []; // Reset loaded presentations array
            empty.style.display = 'none';
            document.getElementById('pagination').style.display = 'flex';
            document.getElementById('total-badge').textContent = data.totalElements;

            const pBadge = document.getElementById('pending-badge');
            pBadge.style.display = 'block';
            pBadge.textContent = `${data.totalElements} PRODUTOS NO BUFFER`;

            tbody.innerHTML = data.content.map((item, index) => `
                <tr class="product-row" style="animation-delay: ${index * 0.05}s; cursor: pointer; border-bottom: 1px solid var(--border);" onclick="toggleProductRow(this, '${item.numero_registro}')">
                    <td style="color: var(--text-secondary); font-size: 11px;">${index + 1 + (page - 1) * pageSize}</td>
                    <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-primary); font-weight: 600;">${item.numero_registro || '--'}</td>
                    <td style="font-weight: 600; text-transform: uppercase;">${item.nome_comercial || '--'}</td>
                    <td style="font-size: 11px; text-transform: uppercase; color: var(--text-secondary);">${item.principio_ativo || '--'}</td>
                    <td style="font-size: 11px; text-transform: uppercase;">${item.fabricante || '--'}</td>
                    <td style="text-align: center;"><span class="badge badge-default" style="background-color: var(--border); color: var(--text-primary); font-weight: 600; border: 1px solid var(--border);">${item.qtd_apresentacoes || 0}</span></td>
                    <td style="text-align: center;"><span class="badge ${item.ativa ? 'badge-black' : 'badge-default'}">${item.ativa ? 'SIM' : 'NÃO'}</span></td>
                </tr>
                <tr class="details-expanded-row" id="exp-${item.numero_registro}" style="display: none;">
                    <td colspan="7" style="padding: 16px 24px; background-color: rgba(255, 255, 255, 0.015); border-bottom: 1px solid var(--border);">
                        <div class="expanded-container" style="border: 1px solid var(--border); border-radius: 4px; padding: 12px; background-color: var(--bg);">
                            <div style="font-family: var(--font-mono); font-size: 10px; color: var(--text-secondary); margin-bottom: 8px; letter-spacing: 0.05em; text-transform: uppercase;">Apresentações Vinculadas (MS 13 dígitos)</div>
                            <table class="nested-presentations-table" style="width: 100%; border-collapse: collapse; font-size: 11px;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--border); text-align: left; color: var(--text-secondary); height: 28px;">
                                        <th style="padding: 6px; font-weight: 500;">REGISTRO MS (13 D.)</th>
                                        <th style="padding: 6px; font-weight: 500;">APRESENTAÇÃO</th>
                                        <th style="padding: 6px; font-weight: 500;">TARJA</th>
                                        <th style="padding: 6px; font-weight: 500;">LISTA</th>
                                        <th style="padding: 6px; font-weight: 500; text-align: center;">UNIDADE</th>
                                        <th style="padding: 6px; font-weight: 500; text-align: center;">STATUS</th>
                                        <th style="padding: 6px; font-weight: 500; text-align: center;">AÇÕES</th>
                                    </tr>
                                </thead>
                                <tbody class="presentations-list">
                                    <tr>
                                        <td colspan="7" style="text-align: center; padding: 12px; color: var(--text-secondary);">Carregando apresentações...</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </td>
                </tr>
            `).join('');

            renderPagination(data.totalPages, page);
        } else {
            loadedPresentations = [];
            tbody.innerHTML = '';
            empty.style.display = 'flex';
        }

    } catch (e) {
        loadedPresentations = [];
        console.error(e);
    }
}

async function toggleProductRow(rowElement, numeroRegistro) {
    const expRow = document.getElementById('exp-' + numeroRegistro);
    if (!expRow) return;

    if (expRow.style.display === 'none') {
        // Expand row
        expRow.style.display = 'table-row';
        rowElement.classList.add('expanded');
        
        const tbody = expRow.querySelector('.presentations-list');
        if (tbody && tbody.getAttribute('data-loaded') !== 'true') {
            try {
                const res = await fetch('/api/ms/' + numeroRegistro);
                const list = await res.json();
                
                if (list && list.length > 0) {
                    // Cache results in loadedPresentations so showProductDetails can access them
                    list.forEach(p => {
                        if (!loadedPresentations.some(x => x.id === p.id)) {
                            loadedPresentations.push(p);
                        }
                    });
                    
                    tbody.innerHTML = list.map(item => `
                        <tr style="border-bottom: 1px solid var(--border); transition: background-color 0.2s;" onmouseover="this.style.backgroundColor='rgba(255,255,255,0.02)'" onmouseout="this.style.backgroundColor='transparent'">
                            <td style="padding: 8px 6px; font-family: var(--font-mono); font-weight: 500; color: var(--text-primary);">${item.registro || '--'}</td>
                            <td style="padding: 8px 6px;">${item.apresentacao || '--'}</td>
                            <td style="padding: 8px 6px;">${renderTarja(item.tarja)}</td>
                            <td style="padding: 8px 6px;"><span class="badge badge-default">${item.lista_controle || '--'}</span></td>
                            <td style="padding: 8px 6px; text-align: center;">
                                ${item.unidade_medida_medicamento === 1 
                                    ? '<span class="badge badge-black" style="background-color:#111111; color:#ffffff; border:1px solid #333;">CX (1)</span>' 
                                    : item.unidade_medida_medicamento === 2 
                                        ? '<span class="badge badge-yellow">FR (2)</span>' 
                                        : '<span class="badge badge-default">--</span>'}
                            </td>
                            <td style="padding: 8px 6px; text-align: center;">
                                <span class="badge ${item.ativa ? 'badge-black' : 'badge-default'}">${item.ativa ? 'ATIVO' : 'INATIVO'}</span>
                            </td>
                            <td style="padding: 8px 6px; text-align: center;">
                                <button class="btn btn-secondary" style="font-size: 9px; padding: 4px 8px; height: auto;" onclick="event.stopPropagation(); showProductDetails(${item.id})">DETALHES</button>
                            </td>
                        </tr>
                    `).join('');
                    tbody.setAttribute('data-loaded', 'true');
                } else {
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 12px; color: var(--text-secondary);">Nenhuma apresentação encontrada.</td></tr>';
                }
            } catch (err) {
                console.error(err);
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 12px; color: var(--text-red);">Erro ao carregar apresentações.</td></tr>';
            }
        }
    } else {
        // Collapse row
        expRow.style.display = 'none';
        rowElement.classList.remove('expanded');
    }
}

function renderPagination(totalPages, current) {
    const container = document.getElementById('pagination');
    container.innerHTML = '';

    if (totalPages <= 1) return;

    let pages = [];
    if (totalPages <= 7) {
        for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
        if (current < 5) pages = [1, 2, 3, 4, 5, '...', totalPages];
        else if (current > totalPages - 4) pages = [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
        else pages = [1, '...', current - 1, current, current + 1, '...', totalPages];
    }

    pages.forEach(p => {
        const btn = document.createElement('button');
        btn.className = `page-btn ${p === current ? 'active' : ''}`;
        btn.textContent = p;
        if (p !== '...') {
            btn.onclick = () => loadResults(p);
        }
        container.appendChild(btn);
    });
}

function renderTarja(tarja) {
    if (!tarja) return '<span class="badge badge-default">--</span>';

    const t = tarja.toLowerCase();
    if (t.includes('vermelha')) {
        return `<span class="badge badge-red">${tarja}</span>`;
    } else if (t.includes('preta')) {
        return `<span class="badge badge-black">${tarja}</span>`;
    } else {
        return `<span class="badge badge-yellow">${tarja}</span>`;
    }
}

function exportData() {
    window.location.href = '/api/export';
}

async function confirmExtraction(proceed) {
    document.getElementById('confirm-modal').style.display = 'none';

    try {
        await fetch('/api/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ proceed: proceed })
        });
    } catch (e) {
        console.error("Confirmation Error", e);
    }

    if (!proceed) {
        clearInterval(pollInterval);
        setLoading(false);
        isConfirming = false; // Allow re-confirming if they start again
    }
}

async function abortExtraction() {
    if (!confirm("Tem certeza que deseja abortar a extração atual?")) return;

    try {
        await fetch('/api/stop', { method: 'POST' });
        clearInterval(pollInterval);
        setLoading(false);
        isConfirming = false;
        document.getElementById('status-text').textContent = "[IDLE] Processo abortado pelo usuário.";
    } catch (e) {
        console.error("Abort Error", e);
    }
}

// Initial Bootstrap
document.addEventListener('DOMContentLoaded', () => {
    loadResults(1);
});

// --- Product Details Modal ---
function showProductDetails(id) {
    const item = loadedPresentations.find(p => p.id === id);
    if (!item) return;

    // Header
    document.getElementById('details-title').textContent = item.nome_comercial || '--';
    document.getElementById('details-subtitle').textContent = item.principio_ativo || '--';

    // Section 1: Identificação Geral
    document.getElementById('detail-sku').textContent = item.codigo_produto || '--';
    document.getElementById('detail-registro-ms').textContent = item.registro || '--';
    document.getElementById('detail-registro-9').textContent = item.numero_registro || '--';
    document.getElementById('detail-fabricante').textContent = item.fabricante || '--';
    document.getElementById('detail-cnpj').textContent = item.cnpj_empresa || '--';
    document.getElementById('detail-afe').textContent = item.numero_autorizacao_empresa || '--';
    document.getElementById('detail-categoria').textContent = item.categoria_regulatoria || '--';

    // Section 2: Controle SNGPC
    const unidadeVal = item.unidade_medida_medicamento;
    const unidadeText = unidadeVal === 1 ? '1 - CAIXA (BOX / BLISTER)' : unidadeVal === 2 ? '2 - FRASCO / AMPOLA' : `-- (${unidadeVal})`;
    document.getElementById('detail-unidade-sngpc').innerHTML = `<span class="badge ${unidadeVal === 1 ? 'badge-black' : unidadeVal === 2 ? 'badge-yellow' : 'badge-default'}">${unidadeText}</span>`;
    
    document.getElementById('detail-tarja').textContent = item.tarja || '--';
    document.getElementById('detail-lista').textContent = item.lista_controle || '--';
    document.getElementById('detail-fracionado').textContent = item.apresentacao_fracionada === 'S' ? 'SIM' : item.apresentacao_fracionada === 'N' ? 'NÃO' : (item.apresentacao_fracionada || '--');
    document.getElementById('detail-qtd-medida').textContent = item.qtd_unidade_medida || '--';
    document.getElementById('detail-status').innerHTML = `<span class="badge ${item.ativa ? 'badge-black' : 'badge-default'}">${item.ativa ? 'ATIVO' : 'INATIVO'}</span>`;

    // Section 3: Uso & Conservação
    document.getElementById('detail-forma').textContent = item.formas_farmaceuticas || '--';
    document.getElementById('detail-via').textContent = item.vias_administracao || '--';
    document.getElementById('detail-destinacao').textContent = item.destinacao || '--';
    document.getElementById('detail-conservacao').textContent = item.conservacao || '--';
    document.getElementById('detail-restricao-hosp').textContent = item.restricao_hospitais === 'S' ? 'SIM' : item.restricao_hospitais === 'N' ? 'NÃO' : (item.restricao_hospitais || '--');
    document.getElementById('detail-restricao-presc').textContent = item.restricao_prescricao || '--';
    document.getElementById('detail-restricao-uso').textContent = item.restricao_uso || '--';

    // Section 4: Registro & Bula
    document.getElementById('detail-data-registro').textContent = formatDate(item.data_produto);
    document.getElementById('detail-validade').textContent = item.validade ? `${item.validade} MESES` : '--';
    document.getElementById('detail-vencimento-registro').textContent = formatDate(item.data_vencimento_registro_produto);
    document.getElementById('detail-referencia').textContent = item.medicamento_referencia || '--';

    // Bulas
    const parseBula = (code) => {
        if (!code) return '--';
        const url = `https://consultas.anvisa.gov.br/api/consulta/medicamento/bula/download/${code}`;
        return `<a href="${url}" target="_blank" onclick="event.stopPropagation()">VISUALIZAR BULA</a>`;
    };
    document.getElementById('detail-bula-paciente').innerHTML = parseBula(item.codigo_bula_paciente);
    document.getElementById('detail-bula-profissional').innerHTML = parseBula(item.codigo_bula_profissional);

    // Section DCB: Denominações Comuns Brasileiras
    const dcbSection = document.getElementById('dcb-section');
    const dcbContainer = document.getElementById('dcb-container');
    
    if (item.dcb_list && item.dcb_list.length > 0) {
        dcbSection.style.display = 'block';
        dcbContainer.innerHTML = item.dcb_list.map(dcb => {
            const isMatched = dcb.codigo_dcb !== 'N/A';
            const badgeStyle = dcb.classificacao === 'IFA' 
                ? 'background-color:#1b4d3e; color:#a3e635; border:1px solid #2e7d32;' 
                : dcb.classificacao === 'BIO' 
                    ? 'background-color:#0d47a1; color:#90caf9; border:1px solid #1565c0;' 
                    : 'background-color:#333333; color:#cccccc; border:1px solid #444444;';
                    
            return `
                <div class="dcb-card" style="border: 1px solid var(--border); padding: 12px; border-radius: 4px; background: rgba(255, 255, 255, 0.02); display: flex; flex-direction: column; gap: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-family: var(--font-mono); font-size: 13px; font-weight: bold; color: ${isMatched ? 'var(--text-primary)' : 'var(--error)'};">
                            ${isMatched ? `DCB #${dcb.codigo_dcb}` : 'DCB NÃO ENCONTRADO'}
                        </span>
                        ${isMatched ? `<span class="badge" style="font-size: 9px; padding: 2px 6px; ${badgeStyle}">${dcb.classificacao}</span>` : ''}
                    </div>
                    <div class="detail-item" style="margin: 0; padding: 0;">
                        <span class="detail-label" style="font-size: 9px; margin-bottom: 2px;">Substância</span>
                        <span class="detail-value" style="font-size: 11px; text-transform: uppercase;">${dcb.substancia_oficial || '--'}</span>
                    </div>
                    ${dcb.cas && dcb.cas !== 'N/A' ? `
                    <div class="detail-item" style="margin: 0; padding: 0;">
                        <span class="detail-label" style="font-size: 9px; margin-bottom: 2px;">CAS</span>
                        <span class="detail-value" style="font-family: var(--font-mono); font-size: 10px;">${dcb.cas}</span>
                    </div>
                    ` : ''}
                </div>
            `;
        }).join('');
    } else {
        dcbSection.style.display = 'none';
        dcbContainer.innerHTML = '';
    }

    // Open Modal
    document.getElementById('details-modal').style.display = 'flex';
}

function closeDetailsModal() {
    document.getElementById('details-modal').style.display = 'none';
}

function handleDetailsModalClick(event) {
    // Close modal if clicked outside the content box
    if (event.target === document.getElementById('details-modal')) {
        closeDetailsModal();
    }
}

function formatDate(isoString) {
    if (!isoString) return '--';
    try {
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return isoString;
        return d.toLocaleDateString('pt-BR');
    } catch {
        return isoString;
    }
}

// Global escape listener to close the modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeDetailsModal();
    }
});
