const fileInput          = document.getElementById('file-input');
const samplesCheck       = document.getElementById('samples-check');
const searchBtn          = document.getElementById('search-btn');
const queryInput         = document.getElementById('query-input');
const resultsSection     = document.getElementById('results-section');
const resultsLoading     = document.getElementById('results-loading');
const resultsMessage     = document.getElementById('results-message');
const topResult          = document.getElementById('top-result');
const topSourceName      = document.getElementById('top-source-name');
const topSourceScore     = document.getElementById('top-source-score');
const recommendationText = document.getElementById('recommendation-text');
const assumptionsSection = document.getElementById('assumptions-section');
const assumptionsList    = document.getElementById('assumptions-list');
const matchesSection     = document.getElementById('matches-section');
const resultsBody        = document.getElementById('results-body');
const apiKeyInput        = document.getElementById('api-key-input');
const apiKeyToggle       = document.getElementById('api-key-toggle');
const apiKeyTrigger      = document.getElementById('api-key-trigger');
const apiKeyPopover      = document.getElementById('api-key-popover');

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
// State helpers
// -------------------------------------------------------

function showLoading() {
    resultsSection.style.display = 'block';
    resultsLoading.classList.remove('hidden');
    resultsMessage.classList.add('hidden');
    topResult.classList.add('hidden');
    assumptionsSection.classList.add('hidden');
    matchesSection.classList.add('hidden');
}

function showMessage(msg, isError) {
    resultsLoading.classList.add('hidden');
    resultsMessage.textContent = msg;
    resultsMessage.className = 'results-message ' + (isError ? 'error' : 'muted');
}

function hideLoading() {
    resultsLoading.classList.add('hidden');
}

// -------------------------------------------------------
// Search Handler
// -------------------------------------------------------

async function runSearch() {
    const query = queryInput.value.trim();
    if (!query) return;

    searchBtn.disabled = true;
    showLoading();

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
        const text = await res.text();
        let data;
        try {
            data = JSON.parse(text);
        } catch {
            showMessage('Server error ' + res.status + ' — ' + res.statusText, true);
            searchBtn.disabled = false;
            return;
        }

        if (!res.ok) {
            showMessage(data.error || 'Search failed.', true);
            searchBtn.disabled = false;
            return;
        }

        hideLoading();
        renderResponse(data);
    } catch (err) {
        showMessage('Search failed: ' + err.message, true);
    }

    searchBtn.disabled = false;
}

searchBtn.addEventListener('click', runSearch);
queryInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') runSearch(); });

// -------------------------------------------------------
// Render
// -------------------------------------------------------

function renderResponse(data) {
    // No results
    if (!data.sources || !data.sources.length) {
        showMessage(data.message || 'No results found.', false);
        return;
    }

    const top = data.sources[0];

    // Best match card
    topSourceName.textContent = top.source;
    topSourceScore.textContent = (top.score * 100).toFixed(1) + '%';

    if (data.recommendation) {
        recommendationText.textContent = data.recommendation;
    } else {
        recommendationText.innerHTML =
            '<span class="muted-text">Set an Anthropic API key to get AI-generated recommendations.</span>';
    }
    topResult.classList.remove('hidden');

    // Assumptions
    if (data.assumptions && data.assumptions.length) {
        assumptionsList.innerHTML = data.assumptions
            .map(a => '<li>' + a + '</li>')
            .join('');
        assumptionsSection.classList.remove('hidden');
    }

    // All matches table
    resultsBody.innerHTML = data.sources.map(function(s) {
        var excerpt = s.chunk.length > 250 ? s.chunk.substring(0, 250) + '...' : s.chunk;
        var pct = (s.score * 100).toFixed(1) + '%';
        return '<tr><td><strong>' + s.source + '</strong></td><td>' + pct + '</td><td>' + excerpt + '</td></tr>';
    }).join('');
    matchesSection.classList.remove('hidden');
}
