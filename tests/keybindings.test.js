import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {APP_BINDINGS, NATIVE_BINDINGS, normalizeAccelerator} from '../keybindings.js';

test('portable launcher commands match the Hyprland workflow without invoking Noctalia', () => {
    assert.deepEqual(APP_BINDINGS['scrollwork-launcher'], ['vicinae', 'toggle']);
    assert.deepEqual(APP_BINDINGS['scrollwork-terminal'], ['ghostty', '+new-window']);
    assert.ok(APP_BINDINGS['scrollwork-calculator'].includes('--class=com.dominic.calc'));
    assert.ok(Object.values(APP_BINDINGS).every(argv => !argv.includes('noctalia')));
    const schema = readFileSync(new URL('../schemas/org.gnome.shell.extensions.scrollwork.gschema.xml', import.meta.url), 'utf8');
    for (const name of Object.keys(APP_BINDINGS))
        assert.ok(schema.includes(`name="${name}"`), name);
});

test('shortcut conflict matching handles modifier order, aliases, case and Above_Tab', () => {
    assert.equal(normalizeAccelerator('<Shift><Super>S'), normalizeAccelerator('<Super><Shift>s'));
    assert.equal(normalizeAccelerator('<Ctrl>apostrophe'), normalizeAccelerator('<Control>apostrophe'));
    assert.equal(normalizeAccelerator('<Super>Above_Tab'), normalizeAccelerator('<Super>grave'));
    assert.notEqual(normalizeAccelerator('<Super>s'), normalizeAccelerator('<Super><Shift>s'));
});

test('GNOME native handlers supply screenshots and locking on the user bindings', () => {
    assert.ok(NATIVE_BINDINGS.some(([, key, keys]) => key === 'screensaver' && keys.includes('<Super>q')));
    assert.ok(NATIVE_BINDINGS.some(([, key, keys]) => key === 'screenshot' && keys.includes('<Super>s')));
});
