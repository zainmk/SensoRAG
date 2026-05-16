const fileInput      = document.getElementById('file-input');
const samplesCheck   = document.getElementById('samples-check');
const searchBtn      = document.getElementById('search-btn');
const queryInput     = document.getElementById('query-input');
const answerBox      = document.getElementById('answer-box');
const resultsSection = document.getElementById('results-section');
const resultsTable   = document.getElementById('results-table');
const resultsBody    = document.getElementById('results-body');
const apiKeyInput    = document.getElementById('api-key-input');
const apiKeyToggle   = document.getElementById('api-key-toggle');
const apiKeyTrigger  = document.getElementById('api-key-trigger');
const apiKeyPopover  = document.getElementById('api-key-popover');

// -------------------------------------------------------
// API Key Management
// -------------------------------------------------------

apiKeyInput.value = localStorage.getItem('anthropic_api_key') || '';

function updateTriggerState() {
    apiKeyTrigger.classList.toggle('has-key', !!apiKeyInput.value.trim());
}
updateTriggerState();

apiKeyInput.addEventListener('input', () => {
    localStorage.setItem('anthropic_api_key', apiKeyInput.value.trim());
    updateTriggerState();
});

apiKeyToggle.addEventListener('click', () => {
    const isPassword = apiKeyInput.type === 'password';
    apiKeyInput.type = isPassword ? 'text' : 'password';
    apiKeyToggle.textContent = isPassword ? 'Hide' : 'Show';
});

apiKeyTrigger.addEventListener('click', (e) => {
    e.stopPropagation();
    apiKeyPopover.classList.toggle('hidden');
    if (!apiKeyPopover.classList.contains('hidden')) apiKeyInput.focus();
});

document.addEventListener('click', (e) => {
    if (!apiKeyPopover.contains(e.target) && e.target !== apiKeyTrigger) {
        apiKeyPopover.classList.add('hidden');
    }
});

// -------------------------------------------------------
// Search Handler
// -------------------------------------------------------

async function runSearch() {
    const query = queryInput.value.trim();
    if (!query) return;

    searchBtn.disabled = true;
    resultsSection.style.display = 'block';
    answerBox.textContent = 'Searching...';
    resultsBody.innerHTML = '';
    resultsTable.style.display = 'none';

    const formData = new FormData();
    formData.append('query', query);
    formData.append('samples', samplesCheck.checked ? 'true' : 'false');
    for (const file of fileInput.files) {
        formData.append('files[]', file);
    }

    const headers = {};
    const key = apiKeyInput.value.trim();
    if (key) headers['X-API-Key'] = key;

    try {
        const res = await fetch('/search', { method: 'POST', headers, body: formData });
        const data = await res.json();
        if (res.ok) {
            answerBox.textContent = data.answer || 'No answer generated.';
            renderResults(data.sources || []);
        } else {
            answerBox.innerHTML = '<span class="error">' + (data.error || 'Search failed.') + '</span>';
        }
    } catch (err) {
        answerBox.innerHTML = '<span class="error">Search failed: ' + err.message + '</span>';
    }

    searchBtn.disabled = false;
}

searchBtn.addEventListener('click', runSearch);
queryInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') runSearch(); });

// -------------------------------------------------------
// Render Helpers
// -------------------------------------------------------

function renderResults(sources) {
    if (!sources.length) {
        resultsTable.style.display = 'none';
        return;
    }
    resultsBody.innerHTML = sources.map(function(s) {
        var excerpt = s.chunk.length > 250 ? s.chunk.substring(0, 250) + '...' : s.chunk;
        var pct = (s.score * 100).toFixed(1) + '%';
        return '<tr><td><strong>' + s.source + '</strong></td><td>' + pct + '</td><td>' + excerpt + '</td></tr>';
    }).join('');
    resultsTable.style.display = 'table';
}
