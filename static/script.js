function updateStats() {
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            // Update Stats
            // Assuming statusText is a defined element, otherwise this would cause an error.
            // If statusText is meant to replace the 'badge' logic, that would be a larger change.
            // For now, inserting as provided, assuming statusText is defined elsewhere or will be.
            // The instruction provided these lines directly after fetch, but they must be inside the .then(data => {}) block.
            // Also, the instruction seems to be a partial replacement for the 'Update Stats' section.
            // I will replace the existing 'Update Stats' block with the provided lines,
            // and ensure the `statusText` lines are within the `data` scope.

            // The instruction implies these lines should be added/modified within the data processing block.
            // The `statusText` variable is not defined in the original code.
            // Assuming `statusText` refers to an element that needs to be retrieved, e.g., `document.getElementById('status-text')`.
            // Since the instruction doesn't define it, I'll add a placeholder definition for `statusText` for syntactic correctness.
            // If the user intended to replace the 'badge' logic, the instruction is incomplete.
            const statusText = document.getElementById('status-text'); // Placeholder: assuming this element exists
            if (statusText) { // Check if element exists to prevent errors if it's not in HTML
                statusText.textContent = data.is_running ? "Running" : "Stopped";
                statusText.className = data.is_running ? "status-running" : "status-stopped";
            }

            document.getElementById('runtime').textContent = data.running_time || "00:00:00";
            document.getElementById('balance').textContent = data.balance ? data.balance.toFixed(2) : "---";
            document.getElementById('profit').textContent = data.profit.toFixed(2);
            document.getElementById('profit').style.color = data.profit >= 0 ? '#238636' : '#da3633';
            document.getElementById('wins').innerText = data.wins;
            document.getElementById('losses').innerText = data.losses;

            // Update Current Digit
            const digitDisplay = document.getElementById('digit-display');
            if (data.current_digit !== null) {
                digitDisplay.innerText = data.current_digit;
                // Simple animation/color feedback?
                // For now just plain text update.
            }

            // Update Martingale live display
            const currentStakeEl = document.getElementById('current-stake');
            const martingalePlEl = document.getElementById('martingale-pl');
            if (currentStakeEl && data.settings) {
                currentStakeEl.textContent = '$' + data.settings.current_stake.toFixed(2);
                const mpl = data.settings.martingale_profit;
                martingalePlEl.textContent = '$' + mpl.toFixed(2);
                martingalePlEl.style.color = mpl >= 0 ? '#238636' : '#da3633';
            }

            // Update Badge & Buttons
            const badge = document.getElementById('status-badge');
            if (data.is_running) {
                badge.className = 'badge running';
                badge.innerText = 'RUNNING';
                document.getElementById('start-btn').disabled = true;
                document.getElementById('stop-btn').disabled = false;
                document.getElementById('save-btn').disabled = true;
            } else {
                badge.className = 'badge stopped';
                badge.innerText = 'STOPPED';
                document.getElementById('start-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
                document.getElementById('save-btn').disabled = false;
            }

            // Sync Settings if not editing (optional - maybe annoying if user is typing, so skipping for now)
            // But we should load them on first load.

            // Update Logs
            const logContainer = document.getElementById('logs');
            logContainer.innerHTML = data.logs.map(log => `<div class="log-entry">${log}</div>`).join('');
        });
}

function saveSettings() {
    const token = document.getElementById('token').value;
    const market = document.getElementById('market').value;
    const stake = document.getElementById('stake').value;
    const duration = document.getElementById('duration').value;
    const prediction = document.getElementById('prediction').value;
    const consecutive = document.getElementById('consecutive').value;
    const smartMode = document.getElementById('smart-mode').checked;
    const strategy = document.getElementById('strategy').value;
    const rangeBarrier = document.getElementById('range-barrier').value;
    const rangeDirection = document.getElementById('range-direction').value;
    const martingaleEnabled = document.getElementById('martingale-enabled').checked;
    const martingaleMode = document.getElementById('martingale-mode').value;
    const martingaleMultiplier = document.getElementById('martingale-multiplier').value;
    const martingaleIncrement = document.getElementById('martingale-increment').value;
    const martingaleMaxStake = document.getElementById('martingale-max-stake').value;

    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            token, market, stake, duration, prediction, consecutive,
            smart_mode: smartMode, strategy,
            range_barrier: rangeBarrier, range_direction: rangeDirection,
            martingale_enabled: martingaleEnabled,
            martingale_mode: martingaleMode,
            martingale_multiplier: martingaleMultiplier,
            martingale_increment: martingaleIncrement,
            martingale_max_stake: martingaleMaxStake
        })
    })
        .then(res => res.json())
        .then(data => alert(data.message));
}

function toggleStrategySettings() {
    const strategy = document.getElementById('strategy').value;
    const digitSettings = document.getElementById('digit-streak-settings');
    const rangeSettings = document.getElementById('range-threshold-settings');
    if (strategy === 'digit_streak') {
        digitSettings.classList.remove('hidden');
        rangeSettings.classList.add('hidden');
    } else {
        digitSettings.classList.add('hidden');
        rangeSettings.classList.remove('hidden');
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
    if (mode === 'multiply') {
        multGroup.classList.remove('hidden');
        addGroup.classList.add('hidden');
    } else {
        multGroup.classList.add('hidden');
        addGroup.classList.remove('hidden');
    }
}

function startBot() {
    fetch('/api/start', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'error') alert(data.message);
            updateStats();
        });
}

function stopBot() {
    fetch('/api/stop', { method: 'POST' });
}

function resetStats() {
    if (confirm("Are you sure you want to reset all profit/loss stats?")) {
        fetch('/api/reset', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                alert(data.message);
                updateStats();
            });
    }
}

function exportLogs() {
    window.location.href = '/api/export_logs';
}

// Initial Settings Load
fetch('/api/status').then(res => res.json()).then(data => {
    document.getElementById('market').value = data.settings.market;
    document.getElementById('stake').value = data.settings.stake;
    document.getElementById('duration').value = data.settings.duration;
    document.getElementById('prediction').value = data.settings.prediction;
    document.getElementById('consecutive').value = data.settings.consecutive;
    document.getElementById('smart-mode').checked = data.settings.smart_mode;
    document.getElementById('strategy').value = data.settings.strategy;
    document.getElementById('range-barrier').value = data.settings.range_barrier;
    document.getElementById('range-direction').value = data.settings.range_direction;
    document.getElementById('martingale-enabled').checked = data.settings.martingale_enabled;
    document.getElementById('martingale-mode').value = data.settings.martingale_mode;
    document.getElementById('martingale-multiplier').value = data.settings.martingale_multiplier;
    document.getElementById('martingale-increment').value = data.settings.martingale_increment;
    document.getElementById('martingale-max-stake').value = data.settings.martingale_max_stake;
    toggleStrategySettings();
    toggleMartingaleSettings();
    toggleMartingaleMode();

    updateUI(data);
});

// Poll every 1s
setInterval(updateStats, 1000);
