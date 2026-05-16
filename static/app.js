const fileInput      = document.getElementById('file-input');
const uploadBtn      = document.getElementById('upload-btn');
const uploadStatus   = document.getElementById('upload-status');
const documentList   = document.getElementById('document-list');
const queryInput     = document.getElementById('query-input');
const queryBtn       = document.getElementById('query-btn');
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

// helper: build headers for /query requests, including the API key if set
function getQueryHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const key = apiKeyInput.value.trim();
    // only attach the header if the user has entered a key
    if (key) headers['X-API-Key'] = key;
    return headers;
}

// -------------------------------------------------------
// Upload Handler
// -------------------------------------------------------

uploadBtn.addEventListener('click', async () => {
    const files = fileInput.files;
    if (!files.length) {
        uploadStatus.innerHTML = '<span class="error">Please select a file first.</span>';
        return;
    }
    uploadBtn.disabled = true;
    uploadStatus.innerHTML = 'Uploading and indexing...';
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetch('/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok) {
                uploadStatus.innerHTML = '<span class="success">' + data.message + '</span>';
                renderDocumentList(data.documents);
            } else {
                uploadStatus.innerHTML = '<span class="error">' + data.error + '</span>';
            }
        } catch (err) {
            uploadStatus.innerHTML = '<span class="error">Upload failed: ' + err.message + '</span>';
        }
    }
    uploadBtn.disabled = false;
    fileInput.value = '';
});

// -------------------------------------------------------
// Query Handler
// -------------------------------------------------------

queryBtn.addEventListener('click', async () => {
    const query = queryInput.value.trim();
    if (!query) return;
    queryBtn.disabled = true;
    resultsSection.style.display = 'block';
    answerBox.textContent = 'Searching...';
    resultsBody.innerHTML = '';
    try {
        // send query with the user's API key (if set) via X-API-Key header
        const res = await fetch('/query', {
            method: 'POST',
            headers: getQueryHeaders(),
            body: JSON.stringify({ query })
        });
        const data = await res.json();
        answerBox.textContent = data.answer || 'No answer generated.';
        renderResults(data.sources || []);
    } catch (err) {
        answerBox.innerHTML = '<span class="error">Query failed: ' + err.message + '</span>';
    }
    queryBtn.disabled = false;
});

// allow pressing Enter in the query input to trigger search
queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') queryBtn.click();
});

// -------------------------------------------------------
// Render Helpers
// -------------------------------------------------------

function renderDocumentList(docs) {
    if (!docs || !docs.length) {
        documentList.innerHTML = '<span style="color:#64748b;font-size:0.85rem;">No documents uploaded yet.</span>';
        return;
    }
    documentList.innerHTML = docs.map(function(d) {
        return '<span class="doc-tag">' + d.filename + ' (' + d.chunks + ' chunks)</span>';
    }).join('');
}

function renderResults(sources) {
    if (!sources.length) {
        resultsTable.style.display = 'none';
        return;
    }
    resultsBody.innerHTML = sources.map(function(s) {
        var excerpt = s.chunk.length > 250 ? s.chunk.substring(0, 250) + '...' : s.chunk;
        // convert similarity score (0-1) to percentage for display
        var pct = (s.score * 100).toFixed(1) + '%';
        return '<tr><td><strong>' + s.source + '</strong></td><td>' + pct + '</td><td>' + excerpt + '</td></tr>';
    }).join('');
    resultsTable.style.display = 'table';
}

// -------------------------------------------------------
// Initial Load - fetch existing documents on page load
// -------------------------------------------------------

(async function() {
    try {
        const res = await fetch('/documents');
        const data = await res.json();
        renderDocumentList(data.documents || []);
    } catch (e) {
        // server not ready yet
    }
})();
