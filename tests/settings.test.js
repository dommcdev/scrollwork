import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {SettingsLease} from '../settings.js';

function assert(condition, description) {
    if (!condition)
        throw new Error(description);
    print(`PASS ${description}`);
}

const settings = new Gio.Settings({schema_id: 'org.gnome.desktop.wm.keybindings'});
const key = 'minimize';
const original = settings.get_value(key);
let lease = new SettingsLease();
lease.override(settings, key, new GLib.Variant('as', []));
assert(settings.get_strv(key).length === 0, 'lease applies an override');
assert(lease.file.query_exists(null), 'original settings journal exists before release');
lease.release();
assert(settings.get_value(key).equal(original), 'release restores the original value');
assert(settings.get_user_value(key) === null, 'release preserves originally unset settings');
assert(!lease.file.query_exists(null), 'release removes its journal');

settings.set_strv(key, ['<Super>F10']);
lease = new SettingsLease();
lease.override(settings, key, new GLib.Variant('as', []));
lease.release();
assert(settings.get_strv(key)[0] === '<Super>F10', 'release restores an explicit user value');

lease = new SettingsLease();
lease.override(settings, key, new GLib.Variant('as', []));
settings.set_strv(key, ['<Super>F11']);
lease.release();
assert(settings.get_strv(key)[0] === '<Super>F11', 'release does not overwrite changes made while leased');

settings.reset(key);
lease = new SettingsLease();
lease.override(settings, key, new GLib.Variant('as', []));
// Simulate a crashed owner: do not call release().
const recovered = new SettingsLease();
assert(recovered.recovered === 1, 'a fresh instance recovers an abandoned journal');
assert(settings.get_value(key).equal(original), 'crash recovery restores the native setting');
assert(settings.get_user_value(key) === null, 'crash recovery preserves unset state');
assert(!recovered.file.query_exists(null), 'crash recovery removes the consumed journal');

lease = new SettingsLease();
lease.override(settings, key, new GLib.Variant('as', []));
settings.set_strv(key, ['<Super>F12']);
new SettingsLease();
assert(settings.get_strv(key)[0] === '<Super>F12', 'crash recovery preserves subsequent user changes');

lease.file.replace_contents(new TextEncoder().encode('{broken json'), null, false,
    Gio.FileCreateFlags.PRIVATE, null);
let refused = false;
try { new SettingsLease(); } catch { refused = true; }
assert(refused && lease.file.query_exists(null), 'invalid journal is refused, not overwritten');
assert(settings.get_strv(key)[0] === '<Super>F12', 'invalid journal leaves settings alone');
lease.file.delete(null);
