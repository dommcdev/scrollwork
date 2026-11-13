// Read-only smoke-test observations. No Eval or arbitrary-command interface.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export default class Probe extends Extension {
    enable() {
        const directory = GLib.build_filenamev([GLib.get_user_state_dir(), 'scrollwork']);
        GLib.mkdir_with_parents(directory, 0o700);
        const file = Gio.File.new_for_path(`${directory}/interactive-probe.json`);
        this.source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
            const e = Main.extensionManager.lookup('scrollwork@dommcdev.github.io')?.stateObj;
            if (!e?.enabled)
                return GLib.SOURCE_CONTINUE;
            const report = {patched: e.tiledStateSupported, overview: Main.overview.visible,
                focus: global.display.focus_window?.title,
                monitors: Main.layoutManager.monitors.length,
                windows: [...e.targets].map(([window, target]) => {
                    const r = window.get_frame_rect();
                    const actual = {x: r.x, y: r.y, width: r.width, height: r.height};
                    return {title: window.title, actual, target,
                        settled: Object.keys(actual).every(k => actual[k] === target[k])};
                })};
            file.replace_contents(new TextEncoder().encode(JSON.stringify(report)), null, false,
                Gio.FileCreateFlags.PRIVATE, null);
            return GLib.SOURCE_CONTINUE;
        });
    }

    disable() {
        if (this.source)
            GLib.source_remove(this.source);
        this.source = 0;
    }
}
