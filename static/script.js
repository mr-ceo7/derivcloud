function updateStats() {
    fetch('/api/status')
        .then(res => res.json())
        .then(data => {
            // Update Stats
            document.getElementById('balance').innerText = data.balance ? `$${data.balance}` : '---';
            document.getElementById('profit').innerText = `$${data.profit}`;
            document.getElementById('profit').style.color = data.profit >= 0 ? '#238636' : '#da3633';
            document.getElementById('wins').innerText = data.wins;
            document.getElementById('losses').innerText = data.losses;

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
    const payload = {
        token: document.getElementById('token').value,
        market: document.getElementById('market').value,
        stake: document.getElementById('stake').value,
        duration: document.getElementById('duration').value,
        prediction: document.getElementById('prediction').value,
        consecutive: document.getElementById('consecutive').value
    };

    fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(res => res.json())
        .then(data => alert(data.message));
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

// Initial Settings Load
fetch('/api/status').then(res => res.json()).then(data => {
    document.getElementById('market').value = data.settings.market;
    document.getElementById('stake').value = data.settings.stake;
    document.getElementById('duration').value = data.settings.duration;
    document.getElementById('prediction').value = data.settings.prediction;
    document.getElementById('consecutive').value = data.settings.consecutive;
});

// Poll every 1s
setInterval(updateStats, 1000);
