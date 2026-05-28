/**
 * UI strings EN / RU for DayZ Server Manager (vanilla, no dependencies).
 */
const STRINGS = {
    en: {
        'app.title': 'DayZ Server Manager',
        'header.apiKey': 'API Key',
        'header.apiKeyTitle': 'API key for API authentication',
        'header.connected': 'Connected',
        'header.disconnected': 'Disconnected',
        'header.shuttingDown': 'Shutting down…',
        'header.shutdown': 'Shutdown',
        'header.shutdownTitle': 'Stop manager and all servers',
        'lang.en': 'EN',
        'lang.ru': 'RU',
        'servers.title': 'Servers',
        'servers.summary': '{total} configured · {online} online',
        'servers.refresh': 'Refresh',
        'servers.empty': 'No servers configured',
        'servers.add': '+ Add Server',
        'logs.title': 'Live Logs',
        'logs.clear': 'Clear',
        'card.expand': 'Expand server details',
        'card.collapse': 'Collapse server details',
        'card.start': 'Start',
        'card.stop': 'Stop',
        'card.restart': 'Restart',
        'card.remove': 'Remove',
        'card.fps': 'FPS',
        'card.players': 'Players',
        'card.playersOnline': 'Players online',
        'card.nobodyOnline': 'No players online',
        'card.serverStopped': 'Server stopped',
        'card.restartSection': 'Restart',
        'card.autoRestart': 'Auto restart',
        'card.autoRestartHint': 'Start server if process died',
        'card.plannedRestart': 'Planned restart',
        'card.plannedRestartHint': 'Scheduled restart from 00:00',
        'card.interval': 'Interval',
        'card.interval2h': 'Every 2 hours',
        'card.interval3h': 'Every 3 hours',
        'card.interval4h': 'Every 4 hours',
        'card.interval6h': 'Every 6 hours',
        'card.intervalCustom': 'Custom (hours)',
        'card.intervalTest': 'Test mode (minutes)',
        'card.customHours': 'Custom hours',
        'card.testMinutes': 'Test interval (minutes)',
        'card.plannedHint': 'Warnings at T-30, T-15, T-10 min. At T-5: say, pause 5 s, lock and kick. Requires RCON.',
        'card.savePlanned': 'Save planned restart',
        'card.nextRestart': 'Next',
        'card.nextDisabled': 'Disabled',
        'card.logRpt': 'Server log (RPT)',
        'card.hideWeapon': 'Hide WEAPON',
        'card.readyHint': 'READY: [IdleMode] Entering IN - save processed',
        'card.gameChat': 'In-game chat',
        'card.chatPlaceholder': 'Message to all players…',
        'card.chatSend': 'Send',
        'status.stopped': 'STOPPED',
        'status.starting': 'STARTING',
        'status.ready': 'READY',
        'warning.rpt_not_found': 'RPT not found — check profiles path',
        'warning.ready_timeout': 'Slow startup — READY marker not seen yet',
        'modal.addServer': 'Add Server',
        'modal.serverId': 'Server ID',
        'modal.serverIdPh': 'e.g., server1',
        'modal.name': 'Name',
        'modal.namePh': 'e.g., My DayZ Server',
        'modal.path': 'Path',
        'modal.pathPh': 'e.g., D:\\Servers\\MyServer',
        'modal.port': 'Port',
        'modal.portPh': 'e.g., 2302',
        'modal.rconPort': 'RCON Port',
        'modal.rconPortPh': 'e.g., 2304',
        'modal.rconPassword': 'RCON Password',
        'modal.cancel': 'Cancel',
        'toast.startFail': 'Failed to start: {detail}',
        'toast.starting': 'Server is starting…',
        'toast.stopFail': 'Failed to stop: {detail}',
        'toast.stopped': 'Server stopped',
        'toast.restartFail': 'Failed to restart: {detail}',
        'toast.restarting': 'Server is restarting…',
        'toast.autoRestartFail': 'Failed to change auto restart: {detail}',
        'toast.removeFail': 'Failed to remove server: {detail}',
        'toast.removed': 'Server «{id}» removed from config',
        'toast.addFail': 'Failed to add server: {detail}',
        'toast.added': 'Server added',
        'toast.plannedSaveFail': 'Failed to save planned restart: {detail}',
        'toast.plannedSaved': 'Planned restart saved',
        'toast.chatFail': 'Failed to send: {detail}',
        'toast.chatSent': 'Message sent in-game',
        'toast.error': 'Error: {detail}',
        'toast.shutdown': 'Stopping manager and all servers…',
        'toast.shutdownFail': 'Shutdown failed: {detail}',
    },
    ru: {
        'app.title': 'DayZ Server Manager',
        'header.apiKey': 'API-ключ',
        'header.apiKeyTitle': 'Ключ для доступа к API',
        'header.connected': 'Подключено',
        'header.disconnected': 'Нет связи',
        'header.shuttingDown': 'Выключение…',
        'header.shutdown': 'Выключить',
        'header.shutdownTitle': 'Остановить менеджер и все серверы',
        'lang.en': 'EN',
        'lang.ru': 'RU',
        'servers.title': 'Серверы',
        'servers.summary': '{total} в конфиге · {online} онлайн',
        'servers.refresh': 'Обновить',
        'servers.empty': 'Серверы не настроены',
        'servers.add': '+ Добавить сервер',
        'logs.title': 'Логи менеджера',
        'logs.clear': 'Очистить',
        'card.expand': 'Развернуть карточку сервера',
        'card.collapse': 'Свернуть карточку сервера',
        'card.start': 'Старт',
        'card.stop': 'Стоп',
        'card.restart': 'Рестарт',
        'card.remove': 'Удалить',
        'card.fps': 'FPS',
        'card.players': 'Игроки',
        'card.playersOnline': 'Игроки онлайн',
        'card.nobodyOnline': 'Никого онлайн',
        'card.serverStopped': 'Сервер остановлен',
        'card.restartSection': 'Рестарт',
        'card.autoRestart': 'Авто-рестарт',
        'card.autoRestartHint': 'Поднять сервер, если процесс упал',
        'card.plannedRestart': 'Плановый рестарт',
        'card.plannedRestartHint': 'Рестарт по расписанию от 00:00',
        'card.interval': 'Интервал',
        'card.interval2h': 'Каждые 2 часа',
        'card.interval3h': 'Каждые 3 часа',
        'card.interval4h': 'Каждые 4 часа',
        'card.interval6h': 'Каждые 6 часа',
        'card.intervalCustom': 'Свой (часы)',
        'card.intervalTest': 'Тест (минуты)',
        'card.customHours': 'Часы',
        'card.testMinutes': 'Интервал теста (мин)',
        'card.plannedHint': 'Предупреждения T-30, T-15, T-10. На T-5: say, пауза 5 с, lock и kick. Нужен RCON.',
        'card.savePlanned': 'Сохранить плановый рестарт',
        'card.nextRestart': 'След.',
        'card.nextDisabled': 'Выкл.',
        'card.logRpt': 'Лог сервера (RPT)',
        'card.hideWeapon': 'Скрыть WEAPON',
        'card.readyHint': 'READY: [IdleMode] Entering IN - save processed',
        'card.gameChat': 'Игровой чат',
        'card.chatPlaceholder': 'Сообщение всем игрокам…',
        'card.chatSend': 'Отправить',
        'status.stopped': 'ОСТАНОВЛЕН',
        'status.starting': 'ЗАПУСК',
        'status.ready': 'ГОТОВ',
        'warning.rpt_not_found': 'RPT не найден — проверьте profiles',
        'warning.ready_timeout': 'Долгая загрузка — маркер READY ещё не появился',
        'modal.addServer': 'Добавить сервер',
        'modal.serverId': 'ID сервера',
        'modal.serverIdPh': 'например, server1',
        'modal.name': 'Имя',
        'modal.namePh': 'например, Мой DayZ сервер',
        'modal.path': 'Путь',
        'modal.pathPh': 'например, D:\\Servers\\MyServer',
        'modal.port': 'Порт',
        'modal.portPh': 'например, 2302',
        'modal.rconPort': 'RCON порт',
        'modal.rconPortPh': 'например, 2304',
        'modal.rconPassword': 'RCON пароль',
        'modal.cancel': 'Отмена',
        'toast.startFail': 'Не удалось запустить: {detail}',
        'toast.starting': 'Сервер запускается…',
        'toast.stopFail': 'Не удалось остановить: {detail}',
        'toast.stopped': 'Сервер остановлен',
        'toast.restartFail': 'Не удалось перезапустить: {detail}',
        'toast.restarting': 'Сервер перезапускается…',
        'toast.autoRestartFail': 'Не удалось изменить авто-рестарт: {detail}',
        'toast.removeFail': 'Не удалось удалить сервер: {detail}',
        'toast.removed': 'Сервер «{id}» удалён из конфига',
        'toast.addFail': 'Не удалось добавить сервер: {detail}',
        'toast.added': 'Сервер добавлен',
        'toast.plannedSaveFail': 'Не удалось сохранить: {detail}',
        'toast.plannedSaved': 'Плановый рестарт сохранён',
        'toast.chatFail': 'Не удалось отправить: {detail}',
        'toast.chatSent': 'Сообщение отправлено в игру',
        'toast.error': 'Ошибка: {detail}',
        'toast.shutdown': 'Останавливаем менеджер и все серверы…',
        'toast.shutdownFail': 'Ошибка выключения: {detail}',
    },
};

const LANG_STORAGE_KEY = 'dayz_ui_lang';
const _langListeners = [];

function _detectDefaultLang() {
    const nav = (navigator.language || '').toLowerCase();
    return nav.startsWith('ru') ? 'ru' : 'en';
}

function getLang() {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    if (stored === 'en' || stored === 'ru') {
        return stored;
    }
    return _detectDefaultLang();
}

let _currentLang = getLang();

function t(key, vars) {
    const table = STRINGS[_currentLang] || STRINGS.en;
    let text = table[key] ?? STRINGS.en[key] ?? key;
    if (vars) {
        Object.keys(vars).forEach((k) => {
            text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(vars[k]));
        });
    }
    return text;
}

function onLangChange(fn) {
    _langListeners.push(fn);
}

function applyStaticI18n(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach((el) => {
        const key = el.getAttribute('data-i18n');
        if (key) {
            el.textContent = t(key);
        }
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (key) {
            el.placeholder = t(key);
        }
    });
    scope.querySelectorAll('[data-i18n-title]').forEach((el) => {
        const key = el.getAttribute('data-i18n-title');
        if (key) {
            el.title = t(key);
        }
    });
}

function setLang(lang) {
    if (lang !== 'en' && lang !== 'ru') {
        return;
    }
    _currentLang = lang;
    localStorage.setItem(LANG_STORAGE_KEY, lang);
    document.documentElement.lang = lang;
    document.title = t('app.title');
    document.querySelectorAll('.lang-switch-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.lang === lang);
    });
    applyStaticI18n(document);
    _langListeners.forEach((fn) => {
        try {
            fn(lang);
        } catch (e) {
            console.error('onLangChange', e);
        }
    });
}

function initI18n() {
    _currentLang = getLang();
    document.documentElement.lang = _currentLang;
    document.title = t('app.title');
    applyStaticI18n(document);
    document.querySelectorAll('.lang-switch-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.lang === _currentLang);
        btn.addEventListener('click', () => setLang(btn.dataset.lang));
    });
}

if (typeof window !== 'undefined') {
    window.t = t;
    window.getLang = getLang;
    window.setLang = setLang;
    window.initI18n = initI18n;
    window.onLangChange = onLangChange;
    window.applyStaticI18n = applyStaticI18n;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        STRINGS,
        getLang,
        setLang,
        t,
        applyStaticI18n,
    };
}
