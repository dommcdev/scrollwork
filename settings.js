import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

// Journal before applying any native setting, so a shell crash cannot lose the
// original values. Recovery never replaces a value changed by the user meanwhile.
export class SettingsLease {
    constructor() {
        this.entries = [];
        this.file = Gio.File.new_for_path(GLib.build_filenamev([
            GLib.get_user_state_dir(), 'scrollwork', 'settings-backup.json',
        ]));
        this.recovered = this._recover();
    }

    _recover() {
        if (!this.file.query_exists(null))
            return 0;
        const [, bytes] = this.file.load_contents(null);
        const journal = JSON.parse(new TextDecoder().decode(bytes));
        if (journal.version !== 1 || !Array.isArray(journal.entries))
            throw new Error('Unrecognized Scrollwork settings backup; refusing to overwrite it');
        const entries = journal.entries.map(entry => ({
            settings: new Gio.Settings({schema_id: entry.schema}),
            key: entry.key,
            original: entry.original === null ? null : GLib.Variant.parse(null, entry.original, null, null),
            replacement: GLib.Variant.parse(null, entry.replacement, null, null),
        }));
        this._restore(entries);
        Gio.Settings.sync();
        this.file.delete(null);
        return entries.length;
    }

    _write() {
        GLib.mkdir_with_parents(this.file.get_parent().get_path(), 0o700);
        const entries = this.entries.map(({settings, key, original, replacement}) => ({
            schema: settings.settings_schema.get_id(), key,
            original: original?.print(true) ?? null,
            replacement: replacement.print(true),
        }));
        this.file.replace_contents(new TextEncoder().encode(JSON.stringify({version: 1, entries})),
            null, false, Gio.FileCreateFlags.PRIVATE, null);
    }

    override(settings, key, replacement) {
        if (settings.get_value(key).equal(replacement))
            return;
        this.entries.push({settings, key, original: settings.get_user_value(key), replacement});
        this._write();
        if (!settings.set_value(key, replacement))
            throw new Error(`Cannot override ${settings.settings_schema.get_id()}:${key}`);
    }

    _restore(entries) {
        for (const {settings, key, original, replacement} of [...entries].reverse()) {
            if (!settings.get_value(key).equal(replacement))
                continue;
            if (original === null)
                settings.reset(key);
            else
                settings.set_value(key, original);
        }
    }

    release() {
        this._restore(this.entries);
        Gio.Settings.sync();
        this.entries = [];
        if (this.file.query_exists(null))
            this.file.delete(null);
    }
}
