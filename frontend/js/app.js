let pollInterval;
let currentPage = 1;
const pageSize = 50;
let searchTimeout;
let logPollInterval;
let isConfirming = false;

// --- Search Logic ---
document.getElementById('search-input').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadResults(1);
    }, 400);
});

// --- Core Logic ---
async function startExtraction() {
    setLoading(true);
    isConfirming = false; // Reset lock for new run
    const reuse = document.getElementById('reuse-flag').checked;
    try {
        const res = await fetch('/api/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reuse: reuse })
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
            startLogPolling(10000);
        } else if (status.state === 'ERROR') {
            clearInterval(pollInterval);
            setLoading(false);
        }
    } catch (e) {
        console.error("Poll Error", e);
    }
}

// --- Log Polling ---
async function startLogPolling(interval = 3000) {
    if (logPollInterval) clearInterval(logPollInterval);
    fetchLogs();
    logPollInterval = setInterval(fetchLogs, interval);
}

async function fetchLogs() {
    try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        renderLogs(data.lines);
    } catch (e) {
        console.error("Log fetch error", e);
    }
}

function renderLogs(lines) {
    const terminal = document.getElementById('terminal');
    const isAtBottom = terminal.scrollHeight - terminal.clientHeight <= terminal.scrollTop + 50;

    terminal.innerHTML = lines.map(line => {
        const parts = line.split(' - ');
        if (parts.length < 4) return `<div class="log-line">${line}</div>`;

        const timestamp = parts[0];
        const module = parts[1];
        const level = parts[2];
        const message = parts.slice(3).join(' - ');

        const levelClass = `level-${level.toLowerCase()}`;

        return `
            <div class="log-line">
                <span class="timestamp">${timestamp}</span>
                [<span class="module">${module}</span>]
                <span class="${levelClass}">${level}</span>:
                <span class="message">${message}</span>
            </div>
        `;
    }).join('');

    if (isAtBottom) {
        terminal.scrollTop = terminal.scrollHeight;
    }
}

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

    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-secondary); padding: 32px;">CARREGANDO DADOS...</td></tr>';
    empty.style.display = 'none';

    const searchQuery = document.getElementById('search-input').value;
    const url = searchQuery
        ? `/api/results?page=${page}&size=${pageSize}&q=${encodeURIComponent(searchQuery)}`
        : `/api/results?page=${page}&size=${pageSize}`;

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (data.totalElements > 0) {
            empty.style.display = 'none';
            document.getElementById('pagination').style.display = 'flex';
            document.getElementById('total-badge').textContent = data.totalElements;

            const pBadge = document.getElementById('pending-badge');
            pBadge.style.display = 'block';
            pBadge.textContent = `${data.totalElements} PRODUTOS NO BUFFER`;

            tbody.innerHTML = data.content.map((item, index) => `
                <tr style="animation-delay: ${index * 0.05}s">
                    <td style="color: var(--text-secondary); font-size: 11px;">${index + 1 + (page - 1) * pageSize}</td>
                    <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-primary);">${item.numero_registro || '--'}</td>
                    <td style="font-family: var(--font-mono); font-size: 12px;">${item.codigo_produto || '--'}</td>
                    <td>
                        <div style="font-weight: 600; text-transform: uppercase;">${item.nome_comercial || '--'}</div>
                        <div style="font-size: 10px; color: var(--text-secondary); text-transform: uppercase; margin-top: 2px;">${item.principio_ativo || '--'}</div>
                    </td>
                    <td>
                        <div style="font-size: 11px;">${item.apresentacao || '--'}</div>
                        <div style="font-size: 10px; color: var(--text-secondary); text-transform: uppercase; margin-top: 2px;">${item.fabricante || '--'}</div>
                    </td>
                    <td style="text-align:center;">
                        <span class="badge ${item.lista_controle !== 'N/A' ? 'badge-black' : 'badge-default'}">${item.lista_controle || '--'}</span>
                    </td>
                </tr>
            `).join('');

            renderPagination(data.totalPages, page);
        } else {
            tbody.innerHTML = '';
            empty.style.display = 'flex';
        }

    } catch (e) {
        console.error(e);
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
    startLogPolling(3000);
});
