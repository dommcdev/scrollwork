import {test} from 'node:test';
import assert from 'node:assert/strict';
import {borderProgress, fadeProgress} from '../animation.js';

test('Hyprland focus curves are bounded, monotonic and finish exactly', () => {
    for (const curve of [borderProgress, fadeProgress]) {
        assert.equal(curve(-1), 0);
        assert.equal(curve(0), 0);
        assert.equal(curve(1), 1);
        assert.equal(curve(2), 1);
        let previous = 0;
        for (let i = 0; i <= 1000; i++) {
            const value = curve(i / 1000);
            assert.ok(value >= previous && value <= 1);
            previous = value;
        }
    }
});

test('border ease-out is front-loaded while opacity stays a subtle 3% change', () => {
    assert.ok(borderProgress(0.2) > 0.6);
    for (let i = 0; i <= 100; i++) {
        const opacity = 1 + (0.97 - 1) * fadeProgress(i / 100);
        assert.ok(opacity >= 0.97 && opacity <= 1);
    }
});
