import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const statusPath = path.join(__dirname, '..', 'web', 'js', 'server_status.js');
const {
    getServerStatusDisplay,
    shouldHideWeaponLine,
    WEAPON_SPAM_SUBSTR,
    MAX_SERVER_LOG_LINES,
} = require(statusPath);

describe('getServerStatusDisplay', () => {
    it('returns STOPPED when not running', () => {
        const s = getServerStatusDisplay({ running: false });
        assert.equal(s.text, 'STOPPED');
        assert.equal(s.className, 'stopped');
    });

    it('returns READY when running and phase ready', () => {
        const s = getServerStatusDisplay({ running: true, startup_phase: 'ready' });
        assert.equal(s.text, 'READY');
        assert.equal(s.className, 'ready');
    });

    it('returns STARTING when running without ready', () => {
        const s = getServerStatusDisplay({ running: true, startup_phase: 'starting' });
        assert.equal(s.text, 'STARTING');
        assert.equal(s.className, 'starting');
    });

    it('shows rpt_not_found warning', () => {
        const s = getServerStatusDisplay({
            running: true,
            startup_phase: 'starting',
            startup_warning: 'rpt_not_found',
        });
        assert.ok(s.warning.includes('profiles'));
    });

    it('shows ready_timeout warning', () => {
        const s = getServerStatusDisplay({
            running: true,
            startup_phase: 'starting',
            startup_warning: 'ready_timeout',
        });
        assert.ok(s.warning.includes('READY'));
    });
});

describe('shouldHideWeaponLine', () => {
    it('hides WEAPON when checkbox checked', () => {
        assert.equal(
            shouldHideWeaponLine(true, `prefix ${WEAPON_SPAM_SUBSTR} AKM`),
            true
        );
    });

    it('shows WEAPON when checkbox unchecked', () => {
        assert.equal(
            shouldHideWeaponLine(false, `prefix ${WEAPON_SPAM_SUBSTR} AKM`),
            false
        );
    });

    it('does not hide normal lines', () => {
        assert.equal(shouldHideWeaponLine(true, 'Player connected'), false);
    });
});

describe('constants', () => {
    it('MAX_SERVER_LOG_LINES is 300', () => {
        assert.equal(MAX_SERVER_LOG_LINES, 300);
    });
});
