import Clutter from 'gi://Clutter';
import St from 'gi://St';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {edgeNeighbors} from './layout.js';

export class EdgeHints {
    constructor(owner) {
        this.owner = owner;
        this.buttons = {};
        this.targets = {};
        for (const side of ['left', 'right']) {
            const button = new St.Button({name: `scrollwork-edge-${side}`, reactive: true,
                can_focus: false, visible: false, accessible_name: `Reveal ${side} window`});
            const content = new St.Widget({layout_manager: new Clutter.FixedLayout()});
            content.add_child(new St.Widget());
            button.set_child(content);
            button.connect('clicked', () => {
                const window = this.targets[side];
                if (!owner.windows.has(window))
                    return;
                // This click deliberately scrolls; ordinary hover never activates it.
                owner._cancelWarp();
                Main.activateWindow(window);
                owner._queue();
                this.hide();
            });
            Main.layoutManager.addChrome(button, {affectsStruts: false, trackFullscreen: true});
            this.buttons[side] = button;
            button.connect('destroy', () => { delete this.buttons[side]; });
        }
    }

    hide() {
        for (const button of Object.values(this.buttons))
            button.hide();
    }

    update(x, y) {
        const owner = this.owner;
        const focus = global.display.focus_window;
        if (!owner.enabled || owner.suspended || !owner.settings.get_boolean('edge-hints') ||
            Main.overview.visible || Main.actionMode !== Shell.ActionMode.NORMAL ||
            owner.grabbing || focus?.get_transient_for() || focus?.is_fullscreen() || focus?.is_maximized() ||
            Main.layoutManager.primaryIndex < 0) {
            this.hide();
            return;
        }
        const workspace = global.workspace_manager.get_active_workspace();
        const strip = owner.strips.get(workspace);
        if (!strip) {
            this.hide();
            return;
        }
        const area = workspace.get_work_area_for_monitor(Main.layoutManager.primaryIndex);
        const gap = owner.settings.get_int('gap');
        this.targets = edgeNeighbors(strip.columns, owner.targets, area, gap);
        const [, , modifiers] = global.get_pointer();
        const dragging = modifiers & (Clutter.ModifierType.BUTTON1_MASK |
            Clutter.ModifierType.BUTTON2_MASK | Clutter.ModifierType.BUTTON3_MASK);
        const width = Math.max(3, Math.min(gap, 8));
        const color = owner.settings.get_string('active-border');
        // Reject arbitrary CSS in a user-edited color setting.
        const border = /^#[0-9a-f]{6}$/i.test(color) ? color : '#cba6f7';
        for (const side of ['left', 'right']) {
            const button = this.buttons[side];
            if (!button)
                continue;
            const near = side === 'left' ? x >= area.x && x < area.x + 24
                : x < area.x + area.width && x >= area.x + area.width - 24;
            const visible = !!this.targets[side] && near && y >= area.y &&
                y < area.y + area.height && !dragging;
            // Keep the pressed actor alive until its release/click is dispatched.
            if (!visible && !button.pressed) {
                button.hide();
                continue;
            }
            button.set_position(side === 'left' ? area.x : area.x + area.width - width, area.y + gap);
            button.set_size(width, Math.max(1, area.height - gap * 2));
            // Retain an easy 3–8px click target, but paint only a thin border.
            const style = 'background-color: transparent; border-width: 0; border-radius: 0; padding: 0; box-shadow: none;';
            if (button.get_style() !== style)
                button.set_style(style);
            const content = button.get_child();
            content.set_size(width, Math.max(1, area.height - gap * 2));
            const line = content.get_first_child();
            line.set_position(side === 'left' ? 0 : width - 2, 0);
            line.set_size(2, Math.max(1, area.height - gap * 2));
            const lineStyle = `background-color: ${border};`;
            if (line.get_style() !== lineStyle)
                line.set_style(lineStyle);
            button.accessible_name = `Reveal ${this.targets[side]?.title ?? side}`;
            button.show();
        }
        return Object.values(this.buttons).some(button => button.visible);
    }

    destroy() {
        for (const button of Object.values(this.buttons)) {
            Main.layoutManager.removeChrome(button);
            button.destroy();
        }
        this.buttons = {};
        this.targets = {};
    }
}
