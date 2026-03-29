/* ============================================================
   API Fetch Wrapper — Chennai Election Portal
   ============================================================ */

const API_BASE = '';

async function api(method, path, body = null) {
    const opts = {
        method,
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' }
    };
    if (body) opts.body = JSON.stringify(body);

    try {
        const res = await fetch(API_BASE + path, opts);
        if (res.status === 401) {
            window.location.href = '/index.html';
            return null;
        }
        const data = await res.json();
        return data;
    } catch (err) {
        console.error('API Error:', err);
        showToast('Network error. Please try again.', 'error');
        return null;
    }
}

/* --- Toast Notifications --- */
function showToast(message, type = 'info', duration = 4000) {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* --- Session Helpers --- */
function requireVoterAuth() {
    // Check if we can reach voter/me
    return api('GET', '/api/voter/me').then(data => {
        if (!data || !data.success) {
            window.location.href = '/index.html';
            return null;
        }
        return data.voter;
    });
}

function requireAdminAuth() {
    return api('GET', '/api/admin/dashboard').then(data => {
        if (!data || !data.success) {
            window.location.href = '/index.html';
            return null;
        }
        return data;
    });
}

async function logout() {
    await api('POST', '/api/auth/logout');
    window.location.href = '/index.html';
}

/* --- Number Formatting --- */
function formatNumber(num) {
    if (num >= 100000) return (num / 100000).toFixed(1) + 'L';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatPercent(pct) {
    return (pct || 0).toFixed(1) + '%';
}
