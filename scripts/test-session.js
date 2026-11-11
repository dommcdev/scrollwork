// Windowed test profile only: show the demos rather than startup overview.
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export default class TestSession extends Extension {
    enable() {
        this.startup = Main.layoutManager.connect('startup-complete', () => Main.overview.hide());
        if (!Main.layoutManager._startingUp)
            Main.overview.hide();
    }

    disable() {
        Main.layoutManager.disconnect(this.startup);
    }
}
