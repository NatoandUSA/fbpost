document.addEventListener('DOMContentLoaded', () => {
    const statusBadge = document.getElementById('auth-status');
    const authBtn = document.getElementById('auth-btn');
    const postBtn = document.getElementById('post-btn');
    const targetLabel = document.getElementById('target-label');
    const targetInput = document.getElementById('target-input');
    const postContent = document.getElementById('post-content');
    const logOutput = document.getElementById('log-output');
    const clearLogBtn = document.getElementById('clear-log');
    
    // UI Elements for mode switcher
    const manualSection = document.getElementById('manual-section');
    const csvSection = document.getElementById('csv-section');
    const inputModeRadios = document.getElementsByName('inputMode');
    const csvUrlInput = document.getElementById('csv-url');
    
    let currentMode = 'group';
    let isCsvMode = false;

    // Check Auth Status
    async function checkStatus() {
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            if (data.authenticated) {
                statusBadge.textContent = 'Authenticated';
                statusBadge.className = 'status-badge authenticated';
                authBtn.classList.add('hidden');
                postBtn.disabled = false;
            } else {
                statusBadge.textContent = 'Unauthenticated';
                statusBadge.className = 'status-badge unauthenticated';
                authBtn.classList.remove('hidden');
                postBtn.disabled = true;
            }
        } catch (e) {
            statusBadge.textContent = 'Server Offline';
            statusBadge.className = 'status-badge unauthenticated';
        }
    }

    // Input Mode Switcher logic
    inputModeRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            isCsvMode = (e.target.value === 'csv');
            if (isCsvMode) {
                manualSection.classList.add('hidden');
                csvSection.classList.remove('hidden');
            } else {
                manualSection.classList.remove('hidden');
                csvSection.classList.add('hidden');
            }
        });
    });

    // Tabs logic
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            currentMode = e.target.dataset.target;
            
            if (currentMode === 'group') {
                targetLabel.textContent = 'Group URLs (One per line)';
                targetInput.placeholder = 'https://facebook.com/groups/...';
            } else if (currentMode === 'page') {
                targetLabel.textContent = 'Page URLs (One per line)';
                targetInput.placeholder = 'https://facebook.com/...';
            } else {
                targetLabel.textContent = 'Thread IDs / Usernames (One per line)';
                targetInput.placeholder = 'e.g. markzuckerberg\njohndoe';
            }
        });
    });

    // Logging helper
    function appendLog(text) {
        const line = document.createElement('div');
        line.className = 'log-line';
        line.textContent = text;
        logOutput.appendChild(line);
        logOutput.scrollTop = logOutput.scrollHeight;
    }

    clearLogBtn.addEventListener('click', () => {
        logOutput.innerHTML = '';
    });

    // Run Command via Streaming API
    async function runCommand(command, payload = {}) {
        postBtn.disabled = true;
        authBtn.disabled = true;
        appendLog(`> Starting ${command}... (Check terminal if browser pops up)`);
        
        try {
            const response = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command, ...payload })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                // Split lines to append correctly
                const lines = chunk.split('\n');
                for (const l of lines) {
                    if (l.trim()) appendLog(l);
                }
            }
            appendLog(`[Process Finished]`);
        } catch (error) {
            appendLog(`Error: ${error.message}`);
        } finally {
            checkStatus(); // Re-check status in case auth was run
            postBtn.disabled = false;
            authBtn.disabled = false;
        }
    }

    // Button Actions
    authBtn.addEventListener('click', () => {
        runCommand('auth');
    });

    postBtn.addEventListener('click', async () => {
        let tasks = [];

        if (isCsvMode) {
            const csvUrl = csvUrlInput.value.trim();
            if (!csvUrl) {
                alert('Please enter a valid Google Sheets CSV URL.');
                return;
            }
            appendLog(`> Fetching CSV data from Google Sheets...`);
            try {
                const res = await fetch(csvUrl);
                const text = await res.text();
                // Simple CSV parser (assumes no quoted commas for simplicity)
                const lines = text.split('\n');
                // Skip header row if it looks like a header (optional, but we assume raw data or we just process all)
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (!line) continue;
                    // Handle simple comma split. Note: if content has commas, it breaks unless quoted.
                    // A better naive split that respects quotes:
                    const row = line.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g);
                    if (!row || row.length < 2) continue;
                    
                    let target = row[0].replace(/^"|"$/g, '').trim();
                    let content = row[1].replace(/^"|"$/g, '').trim();
                    let image = row.length > 2 ? row[2].replace(/^"|"$/g, '').trim() : null;
                    
                    if (target && content) {
                        tasks.push({ target, content, image });
                    }
                }
                
                if (tasks.length === 0) {
                    appendLog('Error: No valid data found in CSV.');
                    return;
                }
            } catch (err) {
                appendLog(`Error fetching CSV: ${err.message}`);
                return;
            }
        } else {
            const rawTargets = targetInput.value.trim();
            const content = postContent.value.trim();
            
            if (!rawTargets || !content) {
                alert('Please fill in both the targets and content fields.');
                return;
            }
            
            const targets = rawTargets.split('\n').map(t => t.trim()).filter(t => t);
            tasks = targets.map(t => ({ target: t, content: content, image: null }));
        }
        
        runCommand(currentMode, { tasks });
    });

    // Initial check
    checkStatus();
});
