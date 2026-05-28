/**
 * Pure helpers for server status display and log filtering (testable without DOM).
 */
const MAX_SERVER_LOG_LINES = 300;

const WEAPON_SPAM_SUBSTR = 'WEAPON       : wpn:';

const DEFAULT_MESSAGES = {
    'status.stopped': 'STOPPED',
    'status.starting': 'STARTING',
    'status.ready': 'READY',
    'warning.rpt_not_found': 'RPT not found — check profiles path',
    'warning.ready_timeout': 'Slow startup — READY marker not seen yet',
};

function getServerStatusDisplay(server, translate) {
    const msg = (key) => {
        if (typeof translate === 'function') {
            return translate(key);
        }
        return DEFAULT_MESSAGES[key] || key;
    };

    if (!server.running) {
        return { className: 'stopped', text: msg('status.stopped'), warning: '' };
    }
    const phase = server.startup_phase || 'starting';
    if (phase === 'ready') {
        return { className: 'ready', text: msg('status.ready'), warning: '' };
    }
    let warning = '';
    if (server.startup_warning === 'rpt_not_found') {
        warning = msg('warning.rpt_not_found');
    } else if (server.startup_warning === 'ready_timeout') {
        warning = msg('warning.ready_timeout');
    }
    return { className: 'starting', text: msg('status.starting'), warning };
}

function shouldHideWeaponLine(hideWeaponChecked, line) {
    if (hideWeaponChecked && line.includes(WEAPON_SPAM_SUBSTR)) {
        return true;
    }
    return false;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        MAX_SERVER_LOG_LINES,
        WEAPON_SPAM_SUBSTR,
        DEFAULT_MESSAGES,
        getServerStatusDisplay,
        shouldHideWeaponLine,
    };
}
