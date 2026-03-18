// ── State ──────────────────────────────────────────────────
let selectedAccountId = null;

// ── Polling ───────────────────────────────────────────────
function updateStats() {
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            // Aggregated header
            document.getElementById('total-profit').textContent = data.total_profit.toFixed(2);
            document.getElementById('total-profit').style.color = data.total_profit >= 0 ? '#238636' : '#da3633';
            document.getElementById('active-count').textContent = data.active_count;
            document.getElementById('total-accounts').textContent = data.total_accounts;

            // Render account cards
            renderAccountCards(data.accounts);

            // Update selected account's logs and digit
            if (selectedAccountId) {
                const acct = data.accounts.find(a => a.account_id === selectedAccountId);
                if (acct) {
                    // Logs
                    const logContainer = document.getElementById('logs');
                    logContainer.innerHTML = acct.logs.map(log => `<div class="log-entry">${log}</div>`).join('');

                    // Digit display
                    const digitDisplay = document.getElementById('digit-display');
                    if (acct.current_digit !== null) {
                        digitDisplay.innerText = acct.current_digit;
                    }
                }
            }
        })
        .catch(err => console.error('Status poll error:', err));
}

// ── Render Account Cards ──────────────────────────────────
function renderAccountCards(accounts) {
    const grid = document.getElementById('accounts-grid');
    const mainContent = document.getElementById('main-content');

    if (accounts.length === 0) {
        grid.innerHTML = '<div class="card" style="text-align: center; padding: 40px; color: var(--text-secondary);">No accounts added yet. Paste a Deriv API token above to get started.</div>';
        mainContent.style.display = 'none';
        return;
    }

    mainContent.style.display = '';

    // Auto-select if no selection exists
    if (!selectedAccountId && accounts.length > 0) {
        selectAccount(accounts[0].account_id, accounts[0]);
    }

    let html = '';
    for (const acct of accounts) {
        const isSelected = acct.account_id === selectedAccountId;
        const isRunning = acct.is_running;
        let classes = 'account-card';
        if (isSelected) classes += ' selected';
        if (isRunning) classes += ' running';

        const profitColor = acct.profit >= 0 ? '#238636' : '#da3633';
        const profitSign = acct.profit >= 0 ? '+' : '';

        html += `
        <div class="${classes}" onclick="selectAccount('${acct.account_id}')">
            <div class="account-id">${acct.account_id}</div>
            <div class="account-balance">${acct.balance.toFixed(2)} <span style="font-size: 14px; color: var(--text-secondary);">${acct.currency}</span></div>
            <div class="account-profit" style="color: ${profitColor};">${profitSign}${acct.profit.toFixed(2)} P/L</div>
            <div class="account-stats">W: ${acct.wins} | L: ${acct.losses} | Trades: ${acct.total_trades} | ${acct.running_time}</div>
            <div class="account-stats" style="margin-top: 2px;">Stake: <span style="color: var(--accent); font-weight: 600;">$${acct.settings.current_stake.toFixed(2)}</span>${acct.settings.martingale_enabled ? ' | Seq: <span style="color:' + (acct.settings.martingale_profit >= 0 ? '#238636' : '#da3633') + ';">$' + acct.settings.martingale_profit.toFixed(2) + '</span>' : ''}${acct.settings.cooldown_active ? ' | <span style="color: #d29922; font-weight: 600;">⏸ COOL-DOWN</span>' : ''}</div>
            ${IS_READONLY ? '' : `<div class="account-actions" onclick="event.stopPropagation();">
                <button class="btn-start" onclick="startAccount('${acct.account_id}')" ${isRunning ? 'disabled' : ''}>▶</button>
                <button class="btn-stop" onclick="stopAccount('${acct.account_id}')" ${!isRunning ? 'disabled' : ''}>⏹</button>
                <button class="btn-remove" onclick="removeAccount('${acct.account_id}')">✕</button>
            </div>`}
        </div>`;
    }
    grid.innerHTML = html;
}

// ── Select Account ────────────────────────────────────────
function selectAccount(accountId, acctData) {
    selectedAccountId = accountId;
    document.getElementById('settings-account-label').textContent = `(${accountId})`;
    document.getElementById('logs-account-label').textContent = `(${accountId})`;

    // Load settings into form if we have the data
    if (acctData && acctData.settings) {
        loadSettingsToForm(acctData.settings);
    } else {
        // Fetch fresh data
        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                const acct = data.accounts.find(a => a.account_id === accountId);
                if (acct) loadSettingsToForm(acct.settings);
            });
    }
}

function loadSettingsToForm(settings) {
    document.getElementById('market').value = settings.market;
    document.getElementById('stake').value = settings.stake;
    document.getElementById('duration').value = settings.duration;
    document.getElementById('take-profit').value = settings.take_profit !== undefined ? settings.take_profit : 0;
    document.getElementById('prediction').value = settings.prediction;
    document.getElementById('consecutive').value = settings.consecutive;
    document.getElementById('smart-mode').checked = settings.smart_mode;
    document.getElementById('strategy').value = settings.strategy;
    document.getElementById('range-barrier').value = settings.range_barrier;
    document.getElementById('range-direction').value = settings.range_direction;
    document.getElementById('martingale-enabled').checked = settings.martingale_enabled;
    document.getElementById('martingale-mode').value = settings.martingale_mode;
    document.getElementById('martingale-multiplier').value = settings.martingale_multiplier;
    document.getElementById('martingale-increment').value = settings.martingale_increment;
    document.getElementById('martingale-max-stake').value = settings.martingale_max_stake;
    if (settings.trio_role) document.getElementById('trio-role').value = settings.trio_role;
    if (settings.trio_trigger) document.getElementById('trio-trigger').value = settings.trio_trigger;
    if (settings.trio_digit !== undefined) document.getElementById('trio-digit').value = settings.trio_digit;
    if (settings.duo_role) document.getElementById('duo-role').value = settings.duo_role;
    if (settings.duo_trigger) document.getElementById('duo-trigger').value = settings.duo_trigger;
    if (settings.duo_trigger_digit !== undefined) document.getElementById('duo-trigger-digit').value = settings.duo_trigger_digit;
    if (settings.duo_switch_enabled !== undefined) document.getElementById('duo-switch-enabled').checked = settings.duo_switch_enabled;
    if (settings.duo_switch_after !== undefined) document.getElementById('duo-switch-after').value = settings.duo_switch_after;
    if (settings.cooldown_enabled !== undefined) document.getElementById('cooldown-enabled').checked = settings.cooldown_enabled;
    if (settings.cooldown_after !== undefined) document.getElementById('cooldown-after').value = settings.cooldown_after;
    if (settings.cooldown_check !== undefined) document.getElementById('cooldown-check').value = settings.cooldown_check;
    toggleStrategySettings();
    toggleMartingaleSettings();
    toggleMartingaleMode();
}

// ── Add / Remove Account ──────────────────────────────────
function addAccount() {
    const token = document.getElementById('new-token').value.trim();
    if (!token) return alert('Please paste a Deriv API token.');

    const btn = document.getElementById('add-account-btn');
    btn.disabled = true;
    btn.innerText = 'Adding...';

    fetch('/api/add_account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'error') {
                alert(data.message);
            } else {
                document.getElementById('new-token').value = '';
                selectedAccountId = data.account_id;
                updateStats();
            }
        })
        .catch(err => alert('Error adding account: ' + err))
        .finally(() => {
            btn.disabled = false;
            btn.innerText = '+ Add';
        });
}

function removeAccount(accountId) {
    if (!confirm(`Remove account ${accountId}? This will stop any running bot.`)) return;

    fetch('/api/remove_account', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId })
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'error') alert(data.message);
            if (selectedAccountId === accountId) selectedAccountId = null;
            updateStats();
        });
}

// ── Save Settings ─────────────────────────────────────────
function getSettingsPayload() {
    return {
        market: document.getElementById('market').value,
        stake: document.getElementById('stake').value,
        duration: document.getElementById('duration').value,
        take_profit: parseFloat(document.getElementById('take-profit').value) || 0.0,
        prediction: document.getElementById('prediction').value,
        consecutive: document.getElementById('consecutive').value,
        smart_mode: document.getElementById('smart-mode').checked,
        strategy: document.getElementById('strategy').value,
        range_barrier: document.getElementById('range-barrier').value,
        range_direction: document.getElementById('range-direction').value,
        martingale_enabled: document.getElementById('martingale-enabled').checked,
        martingale_mode: document.getElementById('martingale-mode').value,
        martingale_multiplier: document.getElementById('martingale-multiplier').value,
        martingale_increment: document.getElementById('martingale-increment').value,
        martingale_max_stake: document.getElementById('martingale-max-stake').value,
        trio_role: document.getElementById('trio-role').value,
        trio_trigger: document.getElementById('trio-trigger').value,
        trio_digit: document.getElementById('trio-digit').value,
        duo_role: document.getElementById('duo-role').value,
        duo_trigger: document.getElementById('duo-trigger').value,
        duo_trigger_digit: document.getElementById('duo-trigger-digit').value,
        duo_switch_enabled: document.getElementById('duo-switch-enabled').checked,
        duo_switch_after: document.getElementById('duo-switch-after').value,
        cooldown_enabled: document.getElementById('cooldown-enabled').checked,
        cooldown_after: document.getElementById('cooldown-after').value,
        cooldown_check: document.getElementById('cooldown-check').value,
    };
}

function saveSettings() {
    if (!selectedAccountId) return alert('Select an account first.');
    const payload = getSettingsPayload();
    payload.account_id = selectedAccountId;

    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(res => res.json())
        .then(data => {
            const btn = document.getElementById('save-btn');
            const original = btn.innerText;
            btn.innerText = '✓ Saved!';
            setTimeout(() => { btn.innerText = original; }, 2000);
        })
        .catch(err => alert('Error saving: ' + err));
}

function applyToAll() {
    const payload = getSettingsPayload();
    payload.apply_to_all = true;

    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(res => res.json())
        .then(data => {
            const btn = document.getElementById('apply-all-btn');
            const original = btn.innerText;
            btn.innerText = '✓ Applied!';
            setTimeout(() => { btn.innerText = original; }, 2000);
        })
        .catch(err => alert('Error: ' + err));
}

// ── Start / Stop ──────────────────────────────────────────
function startAccount(accountId) {
    fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId })
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'error') alert(data.message);
            updateStats();
        });
}

function stopAccount(accountId) {
    fetch('/api/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId })
    })
        .then(res => res.json())
        .then(data => updateStats());
}

function startAll() {
    fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ start_all: true })
    })
        .then(res => res.json())
        .then(data => updateStats());
}

function stopAll() {
    fetch('/api/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stop_all: true })
    })
        .then(res => res.json())
        .then(data => updateStats());
}

// ── Reset / Export ────────────────────────────────────────
function resetStats() {
    if (!selectedAccountId) return alert('Select an account first.');
    if (!confirm(`Reset stats for ${selectedAccountId}?`)) return;
    fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: selectedAccountId })
    })
        .then(res => res.json())
        .then(data => updateStats());
}

function exportLogs() {
    if (!selectedAccountId) return alert('Select an account first.');
    window.location.href = `/api/export_logs?account_id=${selectedAccountId}`;
}

function exportAllLogs() {
    window.location.href = '/api/export_all_logs';
}

// ── Strategy / Martingale Toggles ─────────────────────────
function toggleStrategySettings() {
    const strategy = document.getElementById('strategy').value;
    const digitSettings = document.getElementById('digit-streak-settings');
    const rangeSettings = document.getElementById('range-threshold-settings');
    const trioSettings = document.getElementById('trio-coverage-settings');
    const duoSettings = document.getElementById('duo-coverage-settings');
    digitSettings.classList.add('hidden');
    rangeSettings.classList.add('hidden');
    trioSettings.classList.add('hidden');
    duoSettings.classList.add('hidden');
    if (strategy === 'digit_streak') {
        digitSettings.classList.remove('hidden');
    } else if (strategy === 'range_threshold') {
        rangeSettings.classList.remove('hidden');
    } else if (strategy === 'trio_coverage') {
        trioSettings.classList.remove('hidden');
    } else if (strategy === 'duo_coverage') {
        duoSettings.classList.remove('hidden');
    }
}

function toggleMartingaleSettings() {
    const enabled = document.getElementById('martingale-enabled').checked;
    const settings = document.getElementById('martingale-settings');
    if (enabled) {
        settings.classList.remove('hidden');
    } else {
        settings.classList.add('hidden');
    }
}

function toggleMartingaleMode() {
    const mode = document.getElementById('martingale-mode').value;
    const multGroup = document.getElementById('martingale-multiplier-group');
    const addGroup = document.getElementById('martingale-increment-group');
    multGroup.classList.add('hidden');
    addGroup.classList.add('hidden');
    if (mode === 'multiply') {
        multGroup.classList.remove('hidden');
    } else if (mode === 'additive') {
        addGroup.classList.remove('hidden');
    }
}

// ── Init ──────────────────────────────────────────────────
updateStats();
setInterval(updateStats, 1000);
fetchCollaborators();
setInterval(fetchCollaborators, 3000);

// Disable settings panel for viewers
if (typeof IS_READONLY !== 'undefined' && IS_READONLY) {
    document.addEventListener('DOMContentLoaded', () => {
        const settingsPanel = document.querySelector('.settings-panel');
        if (settingsPanel) {
            settingsPanel.querySelectorAll('input, select, button').forEach(el => {
                el.disabled = true;
                el.style.opacity = '0.5';
                el.style.pointerEvents = 'none';
            });
        }
        // Hide reset button
        const resetBtn = document.getElementById('reset-btn');
        if (resetBtn) resetBtn.style.display = 'none';
    });
}

// ── Collaborator Functions ───────────────────────────────────────

function fetchCollaborators() {
    fetch('/api/collaborators')
        .then(res => res.json())
        .then(data => renderCollaborators(data))
        .catch(err => console.error('Collab fetch error:', err));
}

function renderCollaborators(data) {
    const container = document.getElementById('collab-breakdown');
    if (!container) return;
    
    const collabs = data.collaborators || [];
    if (collabs.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.9rem;">No collaborators added yet.</div>';
        return;
    }
    
    const isReadonly = (typeof IS_READONLY !== 'undefined' && IS_READONLY);
    
    let html = '<div style="display: flex; flex-direction: column; gap: 8px;">';
    collabs.forEach((c, i) => {
        const pnlColor = c.pnl >= 0 ? '#238636' : '#da3633';
        const pnlSign = c.pnl >= 0 ? '+' : '';
        html += `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: #0d1117; border-radius: 8px; border: 1px solid #21262d;">
                <div>
                    <span style="font-weight: 600; color: #e6edf3;">${i + 1}. ${c.name}</span>
                    <span style="color: #8b949e; margin-left: 8px;">${c.percentage}%</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-weight: 700; color: ${pnlColor}; font-size: 1.05rem;">${pnlSign}${c.pnl.toFixed(2)} USD</span>
                    ${isReadonly ? '' : `<button onclick="removeCollaborator('${c.name}')" style="background: none; border: 1px solid #da3633; color: #da3633; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">✕</button>`}
                </div>
            </div>`;
    });
    html += '</div>';
    
    // Total percentage
    const totalPct = collabs.reduce((sum, c) => sum + c.percentage, 0);
    html += `<div style="margin-top: 8px; font-size: 0.85rem; color: #8b949e;">Total allocated: <strong style="color: ${totalPct === 100 ? '#238636' : '#d29922'};">${totalPct}%</strong> / 100%</div>`;
    
    container.innerHTML = html;
}

function addCollaborator() {
    const nameEl = document.getElementById('collab-name');
    const pctEl = document.getElementById('collab-pct');
    if (!nameEl || !pctEl) return;
    
    const name = nameEl.value.trim();
    const percentage = parseFloat(pctEl.value);
    
    if (!name) return alert('Enter a name');
    if (!percentage || percentage <= 0) return alert('Enter a valid percentage');
    
    fetch('/api/collaborators', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, percentage })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'error') {
            alert(data.message);
        } else {
            nameEl.value = '';
            pctEl.value = '';
            fetchCollaborators();
        }
    });
}

function removeCollaborator(name) {
    if (!confirm(`Remove ${name}?`)) return;
    
    fetch('/api/collaborators', {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
    })
    .then(res => res.json())
    .then(() => fetchCollaborators());
}
