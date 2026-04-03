const API_BASE = window.location.origin;

const statusPill = document.getElementById('status-pill');
const healthJson = document.getElementById('health-json');
const lastCheck = document.getElementById('last-check');
const checkHealthBtn = document.getElementById('check-health');
const testResetBtn = document.getElementById('test-reset');

checkHealthBtn.addEventListener('click', checkHealth);
testResetBtn.addEventListener('click', testReset);

window.addEventListener('load', async () => {
    await checkHealth();
});

async function checkHealth() {
    statusPill.textContent = 'Checking...';
    statusPill.className = 'pill pending';

    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await safeJson(response);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        statusPill.textContent = 'OK';
        statusPill.className = 'pill ok';
        healthJson.textContent = JSON.stringify(data || { status: 'ok' }, null, 2);
    } catch (error) {
        statusPill.textContent = 'ERROR';
        statusPill.className = 'pill error';
        healthJson.textContent = JSON.stringify({ error: String(error.message || error) }, null, 2);
    } finally {
        lastCheck.textContent = new Date().toLocaleString();
    }
}

async function testReset() {
    testResetBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/reset`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: 'easy' }),
        });

        const data = await safeJson(response);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const preview = {
            test: 'reset',
            ok: true,
            inbox_count: Array.isArray(data?.observation?.inbox) ? data.observation.inbox.length : 0,
            task_id: data?.observation?.task_id || 'unknown',
        };
        healthJson.textContent = JSON.stringify(preview, null, 2);
        statusPill.textContent = 'OK';
        statusPill.className = 'pill ok';
    } catch (error) {
        statusPill.textContent = 'ERROR';
        statusPill.className = 'pill error';
        healthJson.textContent = JSON.stringify({ test: 'reset', ok: false, error: String(error.message || error) }, null, 2);
    } finally {
        lastCheck.textContent = new Date().toLocaleString();
        testResetBtn.disabled = false;
    }
}

async function safeJson(response) {
    try {
        return await response.json();
    } catch {
        return null;
    }
}
