import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Strip, edgeNeighbors} from '../layout.js';

const area = {x: 0, y: 32, width: 1200, height: 768};

test('edge hints select the nearest hidden column and ignore a fitting pair', () => {
    const strip = new Strip();
    for (const id of ['a', 'b', 'c', 'd']) strip.add(id);
    strip.focus('b');
    let targets = strip.layout(area);
    assert.deepEqual(edgeNeighbors(strip.columns, targets, area, 8), {left: null, right: 'c'});
    strip.focus('d');
    targets = strip.layout(area);
    assert.deepEqual(edgeNeighbors(strip.columns, targets, area, 8), {left: 'b', right: null});
    strip.remove('a'); strip.remove('b');
    targets = strip.layout(area);
    assert.deepEqual(edgeNeighbors(strip.columns, targets, area, 8), {left: null, right: null});
});

test('edge hints handle partial windows and negative monitor origins', () => {
    const columns = [{id: 'a'}, {id: 'b'}, {id: 'c'}];
    const targets = new Map([['a', {x: -1300, width: 600}],
        ['b', {x: -600, width: 500}], ['c', {x: -90, width: 600}]]);
    assert.deepEqual(edgeNeighbors(columns, targets, {x: -1200, width: 1200}, 8), {left: 'a', right: 'c'});
});

test('new columns are inserted after focus; duplicates do not reset state', () => {
    const strip = new Strip();
    strip.add('a'); strip.add('b'); strip.focus('a'); strip.add('c'); strip.add('c');
    assert.deepEqual(strip.columns.map(c => c.id), ['a', 'c', 'b']);
    assert.equal(strip.focused, 'c');
});

test('opening windows never changes existing column widths', () => {
    const strip = new Strip(); strip.add('a'); strip.add('b');
    const initial = strip.layout(area).get('a');
    for (let n = 0; n < 30; n++) strip.add(n);
    const later = strip.layout(area).get('a');
    assert.equal(initial.width, later.width);
    assert.equal(initial.height, later.height);
});

test('focus scrolls real geometry into view, including negative monitor origins', () => {
    const strip = new Strip();
    for (let n = 0; n < 12; n++) strip.add(n);
    for (const origin of [-1920, 0, 1920]) {
        for (let n = 0; n < 12; n++) {
            strip.focus(n);
            const r = strip.layout({...area, x: origin}).get(n);
            assert.ok(r.x >= origin + 8);
            assert.ok(r.x + r.width <= origin + area.width - 8);
        }
    }
});

test('width presets cycle and full-width column fits the usable area', () => {
    const strip = new Strip(); strip.add('a'); strip.add('b'); strip.focus('a');
    const widths = [];
    for (let n = 0; n < 4; n++) {
        widths.push(strip.layout(area).get('a').width); strip.cycleWidth();
    }
    assert.deepEqual(widths, [588, 1184, 588, 1184]);
});

test('a lone column fills the screen and returns to its preset when another opens', () => {
    const strip = new Strip(); strip.add('a');
    assert.equal(strip.layout(area).get('a').width, 1184);
    strip.add('b');
    assert.equal(strip.layout(area).get('a').width, 588);
    strip.remove('b');
    assert.equal(strip.layout(area).get('a').width, 1184);
});

test('explicit centering works even at the beginning and end of a strip', () => {
    const strip = new Strip(); strip.add('a'); strip.add('b'); strip.add('c');
    for (const id of ['a', 'b', 'c']) {
        strip.focus(id); strip.center();
        const rect = strip.layout(area).get(id);
        assert.equal(rect.x + rect.width / 2, area.x + area.width / 2);
    }
});

test('two half-width windows never move when focus alternates, including odd budgets', () => {
    for (const width of [800, 1023, 1024, 1279, 1280, 1707, 1920, 2560]) {
        for (const outer of [0, 8, 13]) {
            for (const inner of [0, 7, 8, 13]) {
                const strip = new Strip(); strip.add('discord'); strip.add('opencode');
                const workspace = {...area, width};
                const expected = [...strip.layout(workspace, outer, inner)];
                assert.ok(expected[0][1].x >= outer);
                assert.ok(expected[1][1].x + expected[1][1].width <= width - outer);
                for (let n = 0; n < 100; n++) {
                    strip.focus(n % 2 ? 'discord' : 'opencode');
                    assert.deepEqual([...strip.layout(workspace, outer, inner)], expected);
                }
            }
        }
    }
});

test('client size hints do not enter the column or viewport model', () => {
    const strip = new Strip(); strip.add('discord'); strip.add('opencode');
    const expected = [...strip.layout(area)];
    // A slightly wider requested/committed client surface is not a column width.
    const clientWidth = expected[0][1].width + 16;
    assert.ok(clientWidth > expected[0][1].width);
    strip.focus('discord');
    assert.deepEqual([...strip.layout(area)], expected);
});

test('move/focus are bounded and removal selects a surviving neighbor', () => {
    const strip = new Strip(); strip.add('a'); strip.add('b'); strip.add('c');
    strip.move(1); assert.equal(strip.neighbor(1), null);
    strip.move(-1); assert.deepEqual(strip.columns.map(c => c.id), ['a', 'c', 'b']);
    strip.remove('c'); assert.equal(strip.focused, 'b');
    strip.remove('missing'); strip.remove('b'); strip.remove('a');
    assert.equal(strip.focused, null); assert.equal(strip.offset, 0);
    strip.move(1); strip.cycleWidth(); assert.deepEqual([...strip.layout(area)], []);
});

test('shrinking, growing, and tiny work areas preserve integer, positive geometry', () => {
    const strip = new Strip(); strip.add('a'); strip.add('b'); strip.cycleWidth();
    for (const width of [1, 2, 17, 800, 3840]) {
        for (const height of [1, 2, 17, 800]) {
            const a = {x: -10, y: 3, width, height};
            const r = strip.layout(a, 100).get('b');
            for (const value of Object.values(r)) assert.ok(Number.isInteger(value));
            assert.ok(r.width > 0 && r.height > 0);
            assert.ok(r.x >= a.x && r.x + r.width <= a.x + a.width);
            assert.ok(r.y >= a.y && r.y + r.height <= a.y + a.height);
        }
    }
    assert.throws(() => strip.layout({...area, width: 0}), RangeError);
});

test('seeded randomized lifecycle maintains ordering, visibility, and nonoverlap', () => {
    const strip = new Strip();
    let seed = 23051, nextId = 0;
    const random = max => {
        seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
        return seed % max;
    };
    for (let step = 0; step < 10000; step++) {
        const ids = strip.columns.map(c => c.id);
        switch (random(6)) {
        case 0: strip.add(nextId++); break;
        case 1: strip.remove(ids[random(Math.max(1, ids.length))]); break;
        case 2: strip.focus(ids[random(Math.max(1, ids.length))]); break;
        case 3: strip.move(random(2) ? 1 : -1); break;
        case 4: strip.cycleWidth(); break;
        case 5: strip.layout({...area, width: 300 + random(2000)}); break;
        }
        const rects = strip.layout(area);
        assert.equal(new Set(strip.columns.map(c => c.id)).size, strip.columns.length);
        const focused = rects.get(strip.focused);
        if (focused) {
            assert.ok(focused.x >= 8);
            assert.ok(focused.x + focused.width <= area.width - 8);
        }
        let end = -Infinity;
        for (const rect of rects.values()) {
            assert.ok(rect.x >= end + 8);
            end = rect.x + rect.width;
        }
    }
});
