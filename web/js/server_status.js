/**
 * Pure helpers for server status display and log filtering (testable without DOM).
 */
const MAX_SERVER_LOG_LINES = 300;

const WEAPON_SPAM_SUBSTR = 'WEAPON       : wpn:';

function getServerStatusDisplay(server) {
    if (!server.running) {
        return { className: 'stopped', text: 'STOPPED', warning: '' };
    }
    const phase = server.startup_phase || 'starting';
    if (phase === 'ready') {
        return { className: 'ready', text: 'READY', warning: '' };
    }
    let warning = '';
    if (server.startup_warning === 'rpt_not_found') {
        warning = 'RPT не найден — проверьте profiles';
    } else if (server.startup_warning === 'ready_timeout') {
        warning = 'Долгая загрузка — маркер READY ещё не появился';
    }
    return { className: 'starting', text: 'STARTING', warning };
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
        getServerStatusDisplay,
        shouldHideWeaponLine,
    };
}
