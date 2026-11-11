import {test} from 'node:test';
import assert from 'node:assert/strict';
import {compileRules, matchRule, floatingRect} from '../rules.js';

const rules = compileRules();
const match = (appId, initialTitle = '') => matchRule(rules, {appIds: [appId], initialTitle});

test('the floating apps in the Hyprland profile float by default', () => {
    for (const id of ['com.dominic.wlctl', 'com.dominic.bluetui', 'com.dominic.wiremix',
        'com.dominic.calc', 'com.dominic.btop', 'com.dominic.cal', 'com.dominic.powerbutton',
        'com.dominic.screensaver', 'org.gnome.NautilusPreviewer', 'dev.noctalia.Noctalia',
        'xdg-desktop-portal-gtk', 'vicinae'])
        assert.equal(match(id)?.mode, 'float', id);
});

test('Discord, OpenCode, browsers and ordinary terminals remain tiled', () => {
    for (const id of ['discord', 'ai.opencode.desktop', 'Google-chrome', 'com.mitchellh.ghostty'])
        assert.equal(match(id), null);
    assert.equal(match('com.dominic.calc.other'), null); // Exact IDs, not substring matches.
});

test('title rules are scoped, including the floating GrandOrgue dialogs only', () => {
    assert.equal(match('anything', 'Open Files')?.mode, 'float');
    assert.equal(match('GrandOrgue', 'Open organ')?.mode, 'float');
    assert.equal(match('GrandOrgue', 'Program Settings')?.mode, 'float');
    assert.equal(match('GrandOrgue', 'GrandOrgue v3.15'), null);
    assert.equal(match('GrandOrgue', 'Console'), null);
    assert.equal(match('OtherApp', 'Program Settings'), null);
});

test('custom rules can float other apps or explicitly tile profile defaults; last match wins', () => {
    const custom = compileRules(JSON.stringify([
        {appId: 'discord', mode: 'float'},
        {appId: 'com.dominic.calc', mode: 'tile'},
        {appId: 'discord', initialTitle: '^Main$', mode: 'tile'},
    ]));
    const find = (id, initialTitle = '') => matchRule(custom, {appIds: [id], initialTitle});
    assert.equal(find('discord', 'Popout').mode, 'float');
    assert.equal(find('discord', 'Main').mode, 'tile');
    assert.equal(find('com.dominic.calc').mode, 'tile');
    assert.equal(matchRule(custom, {appIds: ['gtk.id', 'discord'], initialTitle: ''}).mode, 'float');
});

test('fractional floating size and centering use the usable work area', () => {
    assert.deepEqual(floatingRect(match('com.dominic.calc'),
        {x: -1200, y: 32, width: 1200, height: 800}, {x: 0, y: 0, width: 320, height: 240}),
    {x: -780, y: 232, width: 360, height: 400});
});

test('pixel sizes are clamped to fit; size-less rules retain current geometry', () => {
    const area = {x: 0, y: 32, width: 800, height: 600};
    assert.deepEqual(floatingRect(match('com.dominic.cal'), area,
        {x: 10, y: 10, width: 100, height: 100}), {x: 25, y: 32, width: 750, height: 600});
    assert.deepEqual(floatingRect({mode: 'float'}, area,
        {x: 100, y: 100, width: 300, height: 200}), {x: 100, y: 100, width: 300, height: 200});
});

test('invalid rule data is rejected rather than partly applied', () => {
    for (const json of ['{', '{}', '[null]', '[[]]', '[{}]',
        '[{"appId":"test","mode":"oops"}]', '[{"appId":[],"mode":"float"}]',
        '[{"appId":"test","mode":"float","unknown":true}]',
        '[{"appId":"test","mode":"float","size":[-1,100]}]',
        '[{"appId":"test","mode":"float","size":[0.5,100]}]',
        '[{"appId":"test","mode":"tile","center":true}]',
        '[{"initialTitle":"[","mode":"float"}]'])
        assert.throws(() => compileRules(json), json);
});
