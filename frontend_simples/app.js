const API_BASE = 'http://localhost:8000/api/v1';
let currentUser = null;
let token = localStorage.getItem('claria_token');
let activeProcessoId = null;
let analisePollTimer = null;

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    if (token) {
        checkAuth();
    } else {
        showSection('auth');
    }

    // Forms
    document.getElementById('login-form').addEventListener('submit', login);
    document.getElementById('register-form').addEventListener('submit', register);
    document.getElementById('create-process-form').addEventListener('submit', createProcess);
    document.getElementById('upload-form').addEventListener('submit', uploadDocument);
    document.getElementById('upload-file').addEventListener('change', renderUploadTypes);
});

// Utilitários de UI
function showSection(sectionId) {
    document.querySelectorAll('section').forEach(s => s.classList.add('hidden'));
    document.getElementById(`${sectionId}-section`).classList.remove('hidden');

    if (sectionId !== 'detail') {
        stopAnalisePolling();
    }
    
    if (sectionId === 'dashboard') {
        updateDashboardUI();
        loadProcessos();
        document.getElementById('main-nav').classList.remove('hidden');
    } else if (sectionId === 'auth') {
        document.getElementById('main-nav').classList.add('hidden');
    }
}

function toggleAuth(isRegister) {
    document.getElementById('login-form').parentElement.classList.toggle('hidden', isRegister);
    document.getElementById('register-card').classList.toggle('hidden', !isRegister);
    document.getElementById('auth-title').innerText = isRegister ? 'Registro' : 'Login';
}

function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    toast.innerText = message;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), duration);
}

// Autenticação
async function checkAuth() {
    try {
        const resp = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (resp.ok) {
            currentUser = await resp.json();
            updateDashboardUI();
            showSection('dashboard');
        } else {
            logout();
        }
    } catch (err) {
        console.error(err);
        logout();
    }
}

async function login(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const senha = document.getElementById('password').value;

    try {
        const resp = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, senha })
        });

        if (resp.ok) {
            const data = await resp.json();
            token = data.access_token;
            localStorage.setItem('claria_token', token);
            await checkAuth();
            showToast('Login realizado com sucesso!');
        } else {
            const error = await resp.json();
            let detail = 'Falha no login';
            if (error.detail) {
                detail = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail);
            }
            showToast(`Erro: ${detail}`);
        }
    } catch (err) {
        showToast('Erro de conexão com o servidor.');
    }
}

async function register(e) {
    e.preventDefault();
    const data = {
        nome: document.getElementById('reg-nome').value,
        email: document.getElementById('reg-email').value,
        senha: document.getElementById('reg-password').value,
        role: document.getElementById('reg-role').value,
        setor: document.getElementById('reg-setor').value
    };

    try {
        const resp = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (resp.ok) {
            showToast('Registro concluído! Faça login.');
            toggleAuth(false);
        } else {
            const error = await resp.json();
            let detail = 'Falha no registro';
            if (error.detail) {
                detail = typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail);
            }
            showToast(`Erro: ${detail}`);
        }
    } catch (err) {
        showToast('Erro de conexão.');
    }
}

function logout() {
    stopAnalisePolling();
    token = null;
    currentUser = null;
    localStorage.removeItem('claria_token');
    showSection('auth');
}

function updateDashboardUI() {
    if (!currentUser) {
        return;
    }

    const novoProcessoBtn = document.getElementById('btn-novo-processo');
    const dashboardTitle = document.getElementById('dashboard-title');
    const dashboardSubtitle = document.getElementById('dashboard-subtitle');

    const isProfessor = currentUser.role === 'professor';
    novoProcessoBtn.classList.toggle('hidden', !isProfessor);

    dashboardTitle.innerText = isProfessor ? 'Minha área do professor' : 'Painel do administrador';
    dashboardSubtitle.innerText = isProfessor
        ? 'Abra um processo, suba os documentos e acompanhe a análise automática da IA.'
        : 'Os processos chegam automaticamente para análise. Abra os detalhes para acompanhar o status da IA.';
}

// Gestão de Processos
async function loadProcessos() {
    const list = document.getElementById('processos-list');
    list.innerHTML = '<p>Carregando...</p>';

    // Se professor, carrega apenas os dele. Se avaliador, todos.
    const endpoint = currentUser.role === 'professor' ? '/processos/my' : '/processos/';

    try {
        const resp = await fetch(`${API_BASE}${endpoint}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (resp.ok) {
            const processos = await resp.json();
            if (processos.length === 0) {
                list.innerHTML = currentUser.role === 'professor'
                    ? '<p>Nenhum processo criado ainda. Clique em "Novo Processo" para começar.</p>'
                    : '<p>Nenhum processo recebido ainda. Assim que um professor submeter documentos, ele aparecerá aqui.</p>';
                return;
            }
            list.innerHTML = processos.map(p => `
                <div class="card processo-card" onclick="viewProcesso('${p.id}')">
                    <h4>${p.numero}</h4>
                    <p>Tipo: ${p.tipo.replace('_', ' ')}</p>
                    <p><small>IA: ${formatAnaliseStatus(p.analise_status)}</small></p>
                    <span class="status-badge status-${p.status.includes('pendente') ? 'pendente' : (p.status === 'concluido' ? 'concluido' : 'aguardando')}">
                        ${p.status.replace('_', ' ')}
                    </span>
                    <p><small>Criado em: ${new Date(p.criado_em).toLocaleDateString()}</small></p>
                </div>
            `).join('');
        }
    } catch (err) {
        list.innerHTML = '<p>Erro ao carregar processos.</p>';
    }
}

function showCreateProcess() {
    document.getElementById('modal-processo').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal-processo').classList.add('hidden');
}

function renderUploadTypes() {
    const fileInput = document.getElementById('upload-file');
    const container = document.getElementById('upload-types-container');
    const files = Array.from(fileInput.files || []);

    if (files.length === 0) {
        container.innerHTML = '<p class="muted">Selecione arquivos para informar o tipo de cada um.</p>';
        return;
    }

    container.innerHTML = files.map((file, index) => `
        <div class="upload-type-row">
            <label for="upload-type-${index}">${file.name}</label>
            <input
                type="text"
                id="upload-type-${index}"
                name="upload-type-${index}"
                placeholder="Ex: requerimento, cpf"
                required
            >
        </div>
    `).join('');
}

async function createProcess(e) {
    e.preventDefault();
    const tipo = document.getElementById('proc-tipo').value;

    try {
        const resp = await fetch(`${API_BASE}/processos/`, {
            method: 'POST',
            headers: { 
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ tipo })
        });

        if (resp.ok) {
            closeModal();
            loadProcessos();
            showToast('Processo criado com sucesso!');
        }
    } catch (err) {
        showToast('Erro ao criar processo.');
    }
}

async function viewProcesso(id) {
    activeProcessoId = id;
    showSection('detail');
    await refreshProcessoDetalhes(id, true);
}

async function refreshProcessoDetalhes(id, allowAutoStart = false) {
    const infoArea = document.getElementById('processo-info');
    infoArea.innerHTML = 'Carregando detalhes...';
    
    try {
        const resp = await fetch(`${API_BASE}/processos/${id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (resp.ok) {
            const p = await resp.json();
            renderProcessoDetalhes(p);

            if (allowAutoStart && currentUser?.role === 'avaliador' && p.documentos && p.documentos.length > 0 && p.analise_status === 'pending') {
                await triggerAnalysis();
                return;
            }

            updateIASection(p);

            if (p.analise_status === 'processing' || p.analise_status === 'pending') {
                startAnalisePolling();
            } else {
                stopAnalisePolling();
            }
        }
    } catch (err) {
        infoArea.innerHTML = 'Erro ao carregar detalhes.';
    }
}

function renderProcessoDetalhes(p) {
    const infoArea = document.getElementById('processo-info');
    const ownerLabel = currentUser.role === 'professor' ? 'Seu processo' : 'Processo do professor';
    infoArea.innerHTML = `
                <h2>${ownerLabel} ${p.numero}</h2>
                <div class="grid-2-cols">
                    <div>
                        <p><strong>Tipo:</strong> ${p.tipo}</p>
                        <p><strong>Status:</strong> ${p.status}</p>
                        <p><strong>Status da IA:</strong> ${formatAnaliseStatus(p.analise_status)}</p>
                    </div>
                    <div>
                        <p><strong>ID:</strong> ${p.id}</p>
                        <p><strong>Data:</strong> ${new Date(p.criado_em).toLocaleString()}</p>
                    </div>
                </div>
            `;

    const docList = document.getElementById('documentos-list');
    if (p.documentos && p.documentos.length > 0) {
        docList.innerHTML = p.documentos.map(d => `
            <li>
                <strong>${d.tipo_doc}:</strong> ${d.nome_arquivo} 
                <a href="http://localhost:8000/${d.caminho_arquivo}" target="_blank">📄 Abrir</a>
            </li>
        `).join('');
    } else {
        docList.innerHTML = '<li>Nenhum documento anexado.</li>';
    }

    const isOwner = p.usuario_id === currentUser.id;
    document.getElementById('upload-area').classList.toggle('hidden', !isOwner || p.status === 'concluido');
    document.getElementById('ia-actions').classList.toggle('hidden', p.documentos.length === 0);
}

function updateIASection(processo) {
    const area = document.getElementById('ia-analysis');
    const status = processo.analise_status || 'pending';

    if (status === 'processing') {
        area.innerHTML = `
            <div class="card" style="background: #eff6ff; border-left: 4px solid #2563eb;">
                <h4>Análise em andamento</h4>
                <p>A IA está processando os documentos. A tela será atualizada automaticamente.</p>
            </div>
        `;
        return;
    }

    if (status === 'error') {
        area.innerHTML = `
            <div class="card" style="background: #fef2f2; border-left: 4px solid #dc2626;">
                <h4>Erro na análise</h4>
                <p>${processo.analise_erro || 'A IA não conseguiu concluir o processamento.'}</p>
            </div>
        `;
        return;
    }

    if (status === 'completed') {
        stopAnalisePolling();
        const resumo = processo.resumo_ia ? `<p><strong>Resumo:</strong> ${processo.resumo_ia}</p>` : '';
        const checklist = processo.checklist_ia ? `<p><strong>Checklist:</strong> ${processo.checklist_ia}</p>` : '';
        const despacho = processo.despacho_automatico ? `<p><strong>Despacho automático:</strong> ${processo.despacho_automatico}</p>` : '';
        area.innerHTML = `
            <div class="card" style="background: #f0fdf4; border-left: 4px solid #16a34a;">
                <h4>Análise concluída</h4>
                ${resumo}
                ${checklist}
                ${despacho}
            </div>
        `;
        return;
    }

    area.innerHTML = '<p class="muted">Aguardando o início automático da análise.</p>';
    if (processo.documentos && processo.documentos.length > 0) {
        startAnalisePolling();
    }
}

function formatAnaliseStatus(status) {
    const labels = {
        pending: 'Pendente',
        processing: 'Processando',
        completed: 'Concluída',
        error: 'Erro',
    };
    return labels[status] || status || 'Pendente';
}

function startAnalisePolling() {
    if (analisePollTimer || !activeProcessoId) {
        return;
    }

    analisePollTimer = setInterval(() => {
        if (document.getElementById('detail-section').classList.contains('hidden')) {
            stopAnalisePolling();
            return;
        }
        refreshProcessoDetalhes(activeProcessoId, false);
    }, 4000);
}

function stopAnalisePolling() {
    if (analisePollTimer) {
        clearInterval(analisePollTimer);
        analisePollTimer = null;
    }
}

async function uploadDocument(e) {
    e.preventDefault();
    const fileInput = document.getElementById('upload-file');
    const files = Array.from(fileInput.files || []);
    const typeInputs = files.map((_, index) => document.getElementById(`upload-type-${index}`));

    if (files.length === 0) {
        showToast('Selecione pelo menos um arquivo.');
        return;
    }

    const types = typeInputs.map(input => input?.value?.trim()).filter(Boolean);
    if (types.length !== files.length) {
        showToast('Preencha o tipo de todos os arquivos.');
        return;
    }

    const formData = new FormData();
    files.forEach(file => {
        formData.append('arquivos', file);
    });
    types.forEach(type => {
        formData.append('tipos_doc', type);
    });

    try {
        showToast(files.length > 1 ? 'Enviando documentos...' : 'Enviando documento...');
        const resp = await fetch(`${API_BASE}/processos/${activeProcessoId}/documentos`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData
        });

        if (resp.ok) {
            showToast(files.length > 1 ? 'Documentos enviados! A IA iniciará a análise em segundo plano.' : 'Documento enviado! A IA iniciará a análise em segundo plano.');
            await refreshProcessoDetalhes(activeProcessoId, true);
            document.getElementById('upload-form').reset();
            document.getElementById('upload-types-container').innerHTML = '';
        } else {
            showToast('Falha no upload.');
        }
    } catch (err) {
        showToast('Erro de rede.');
    }
}

async function triggerAnalysis() {
    if (!activeProcessoId) {
        return;
    }

    const area = document.getElementById('ia-analysis');
    area.innerHTML = '<p>A IA está sendo acionada... Isso pode levar alguns segundos.</p>';

    try {
        const resp = await fetch(`${API_BASE}/processos/${activeProcessoId}/analise`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (resp.ok) {
            const data = await resp.json();
            showToast(`Análise ${formatAnaliseStatus(data.analise_status).toLowerCase()}.`);
            await refreshProcessoDetalhes(activeProcessoId, false);
            if (data.analise_status === 'pending' || data.analise_status === 'processing') {
                startAnalisePolling();
            }
        } else {
            const errData = await resp.json();
            area.innerHTML = `<p>Erro na análise da IA: ${errData.detail || 'Falha desconhecida'}</p>`;
        }
    } catch (err) {
        area.innerHTML = '<p>Erro de conexão com o serviço de IA.</p>';
    }
}
