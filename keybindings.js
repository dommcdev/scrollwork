// Portable commands from ~/.config/hypr/keybindings.lua. Never start Noctalia
// inside GNOME; shell-owned operations below use GNOME's native handlers.
export const APP_BINDINGS = {
    'scrollwork-launcher': ['vicinae', 'toggle'],
    'scrollwork-terminal': ['ghostty', '+new-window'],
    'scrollwork-browser': ['google-chrome-stable'],
    'scrollwork-browser-private': ['google-chrome-stable', '--incognito'],
    'scrollwork-files': ['nautilus', '--new-window'],
    'scrollwork-yazi': ['ghostty', '-e', 'yazi'],
    'scrollwork-notes': ['obsidian'],
    'scrollwork-calculator': ['ghostty', '--class=com.dominic.calc', '-e', 'qalc'],
    'scrollwork-audio': ['ghostty', '--class=com.dominic.wiremix', '-e', 'wiremix'],
    'scrollwork-bluetooth': ['ghostty', '--class=com.dominic.bluetui', '-e', 'bluetui'],
    'scrollwork-system-monitor': ['ghostty', '--class=com.dominic.btop', '-e', 'btop'],
    'scrollwork-wifi': ['ghostty', '--class=com.dominic.wlctl', '-e', 'wlctl'],
    'scrollwork-network-restart': ['systemctl', 'restart', 'NetworkManager'],
    'scrollwork-grandorgue': ['~/.local/bin/launch-grandorgue.sh'],
    'scrollwork-gemini': ['google-chrome-stable', '--app=https://gemini.google.com/app'],
    'scrollwork-chatgpt': ['google-chrome-stable', '--app=https://chatgpt.com'],
    'scrollwork-parabolic': ['flatpak', 'run', 'org.nickvision.tubeconverter'],
    'scrollwork-watch-later': ['google-chrome-stable', '--app=https://youtube.com/playlist?list=WL'],
    'scrollwork-settings': ['gnome-control-center'],
};

export const NATIVE_BINDINGS = [
    ['org.gnome.settings-daemon.plugins.media-keys', 'screensaver',
        ['<Super>q']],
    ['org.gnome.shell.keybindings', 'screenshot', ['Print', '<Super>s']],
    ['org.gnome.shell.keybindings', 'show-screenshot-ui',
        ['<Shift>Print', '<Super><Shift>s', '<Super><Alt>s']],
    ['org.gnome.shell.keybindings', 'focus-active-notification', ['<Super><Shift>a']],
];

// Keep Hex's own portal bindings/press-and-release semantics. Only release the
// GNOME input-source shortcuts that would compete with those accelerators.
export const EXTERNAL_SHORTCUTS = ['<Super>space', '<Super><Shift>space', '<Shift><Alt>XF86TouchpadOff'];

export function normalizeAccelerator(accelerator) {
    const modifiers = [];
    const aliases = {ctrl: 'control', primary: 'control', mod4: 'super'};
    const key = accelerator.replace(/<([^>]+)>/g, (_match, modifier) => {
        modifier = modifier.toLowerCase();
        modifiers.push(aliases[modifier] ?? modifier);
        return '';
    }).toLowerCase();
    return `${[...new Set(modifiers)].sort().join('+')}:${key === 'above_tab' ? 'grave' : key}`;
}
