import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Mtk from 'gi://Mtk';
import Shell from 'gi://Shell';
import Clutter from 'gi://Clutter';
import St from 'gi://St';

import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';
import {WindowAppearance} from './appearance.js';
import {EdgeHints} from './edges.js';
import {Strip} from './layout.js';
import {SettingsLease} from './settings.js';
import {compileRules, matchRule, floatingRect} from './rules.js';
import {APP_BINDINGS, NATIVE_BINDINGS, EXTERNAL_SHORTCUTS, normalizeAccelerator} from './keybindings.js';

const sameRect = (a, b) => a && b && ['x', 'y', 'width', 'height'].every(k => a[k] === b[k]);
const COMMIT_RETRY_MS = 250;
const MAX_COMMIT_RETRIES = 4;
const DEFAULT_FLOAT = {center: true};

// Registered once per module, so disable/re-enable does not register a second GType.
const Constraint = GObject.registerClass({
    GTypeName: 'ScrollworkConstraint',
    Implements: [Meta.ExternalConstraint],
}, class Constraint extends GObject.Object {
    _init(owner) {
        super._init();
        this.owner = owner;
        this.calls = 0;
    }

    vfunc_constrain(window, info) {
        this.calls++;
        const target = this.owner?.targets.get(window);
        // Native fullscreen/maximize are intentional escape hatches.
        if (target && !window.is_fullscreen() && !window.is_maximized())
            info.set_rect(new Mtk.Rectangle(target));
        return true;
    }
});

export default class Scrollwork extends Extension {
    enable() {
        try {
            this._enable();
        } catch (error) {
            this.disable();
            throw error;
        }
    }

    _enable() {
        if (!Meta.ExternalConstraint || !Meta.ExternalConstraintInfo.prototype.set_rect)
            throw new Error('Scrollwork requires Mutter 51 external constraints with set_rect()');
        this.targets = new Map();
        this.windows = new Map();
        this.strips = new Map();
        this.signals = [];
        this.pending = 0;
        this.warpSource = 0;
        this.grabbing = false;
        this.hoverTarget = null;
        this.registeredBindings = [];
        this.enabled = true;
        this.settings = this.getSettings();
        this.interfaceSettings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this.rules = compileRules(this.settings.get_string('window-rules'));
        this.ruleError = null;
        this.tiledStateSupported = typeof Meta.Window.prototype.set_external_tiled === 'function';
        this.lease = new SettingsLease();
        this.injections = new InjectionManager();
        // Workspace transitions stay instant even when window movement is eased.
        this.injections.overrideMethod(Main.wm._workspaceAnimation, 'animateSwitch',
            () => (_from, _to, _direction, onComplete) => onComplete());
        this.injections.overrideMethod(Main.wm._workspaceAnimation, '_switchWorkspaceEnd',
            original => function (tracker, _duration, progress) {
                return original.call(this, tracker, 0, progress);
            });
        this._override(new Gio.Settings({schema_id: 'org.gnome.mutter'}), 'dynamic-workspaces',
            new GLib.Variant('b', false));
        this._override(new Gio.Settings({schema_id: 'org.gnome.desktop.wm.preferences'}),
            'num-workspaces', new GLib.Variant('i', 10));
        this._override(new Gio.Settings({schema_id: 'org.gnome.desktop.wm.preferences'}),
            'focus-mode', new GLib.Variant('s', 'click'));
        const mutter = new Gio.Settings({schema_id: 'org.gnome.mutter'});
        this._override(mutter, 'attach-modal-dialogs', new GLib.Variant('b', false));
        this._override(mutter, 'center-new-windows', new GLib.Variant('b', true));
        this._override(mutter, 'overlay-key', new GLib.Variant('s', ''));
        this._override(this.interfaceSettings, 'enable-hot-corners', new GLib.Variant('b', false));
        const preferences = new Gio.Settings({schema_id: 'org.gnome.desktop.wm.preferences'});
        this._override(preferences, 'mouse-button-modifier', new GLib.Variant('s', '<Super>'));
        this._override(preferences, 'resize-with-right-button', new GLib.Variant('b', true));
        this.edges = new EdgeHints(this);
        this.lastPointer = global.get_pointer().slice(0, 2);
        this.pointerWatch = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 30, () => {
            const [x, y] = global.get_pointer();
            const edgeActive = this.edges.update(x, y);
            if (x !== this.lastPointer[0] || y !== this.lastPointer[1]) {
                this.lastPointer = [x, y];
                if (!this.warpSource && !edgeActive)
                    this._hoverFocus(x, y);
            }
            return GLib.SOURCE_CONTINUE;
        });
        this._connect(global.display, 'grab-op-begin', () => {
            this.grabbing = true;
            this._cancelWarp();
            for (const record of this.windows.values())
                this._cancelPlacement(record);
        });
        this._connect(global.display, 'grab-op-end', () => { this.grabbing = false; });
        this.suspended = false;
        this._connect(global.display, 'window-created', (_display, window) => this._watch(window));
        this._connect(global.window_manager, 'map', (_wm, actor) => {
            const record = this.windows.get(actor.meta_window);
            if (record) {
                record.mapped = true;
                record.initialTitle ??= actor.meta_window.title || null;
            }
            this._queue();
        });
        this._connect(global.display, 'notify::focus-window', () => this._focusChanged());
        this._connect(Main.layoutManager, 'monitors-changed', () => this._queue());
        this._connect(global.display, 'workareas-changed', () => this._queue());
        this._connect(this.settings, 'changed::gap', () => this._queue());
        this._connect(this.settings, 'changed::inner-gap', () => this._queue());
        this._connect(this.settings, 'changed::suppress-maximize', () => this._queue());
        this._connect(this.interfaceSettings, 'changed::enable-animations', () => this._queue());
        for (const key of ['style-windows', 'corner-radius', 'border-width',
            'active-border', 'inactive-border', 'inactive-opacity', 'edge-hints',
            'border-fade-duration', 'focus-fade-duration'])
            this._connect(this.settings, `changed::${key}`, () => this._queue());
        this._connect(this.settings, 'changed::window-rules', () => {
            try {
                this.rules = compileRules(this.settings.get_string('window-rules'));
                this.ruleError = null;
            } catch (error) {
                this.ruleError = error.message;
                console.warn(`Scrollwork: keeping previous window rules: ${error.message}`);
            }
            this._queue();
        });
        this.bindings = {
            'scrollwork-dismiss-notification': () => Main.messageTray._notification?.destroy(),
            'scrollwork-color-picker': () => this._pickColor(),
            'focus-left': () => this.focus(-1),
            'focus-right': () => this.focus(1),
            'move-left': () => this.move(-1),
            'move-right': () => this.move(1),
            'cycle-width': () => this.cycleWidth(),
            'toggle-floating': () => this.toggleFloating(),
            'center-column': () => {
                this._activeStrip()?.center();
                this._queue();
            },
            'close-window': () => global.display.focus_window?.delete(global.get_current_time()),
            'scrollwork-toggle-fullscreen': () => {
                const window = global.display.focus_window;
                if (window?.is_fullscreen())
                    window.unmake_fullscreen();
                else
                    window?.make_fullscreen();
            },
        };
        for (const [name, argv] of Object.entries(APP_BINDINGS))
            this.bindings[name] = () => this._launchCommand(argv);
        for (let i = 1; i <= 10; i++) {
            this.bindings[`workspace-${i}`] = () => this.workspace(i - 1, false);
            this.bindings[`scrollwork-move-to-workspace-${i}`] = () => this.workspace(i - 1, true);
        }
        this._claimBindings();
        for (const [schema, key, shortcuts] of NATIVE_BINDINGS)
            this._override(new Gio.Settings({schema_id: schema}), key, new GLib.Variant('as', shortcuts));
        for (const [name, callback] of Object.entries(this.bindings)) {
            const flags = APP_BINDINGS[name] || name === 'scrollwork-color-picker' ||
                name === 'scrollwork-dismiss-notification' ? Meta.KeyBindingFlags.IGNORE_AUTOREPEAT : Meta.KeyBindingFlags.NONE;
            const action = Main.wm.addKeybinding(name, this.settings, flags,
                Shell.ActionMode.NORMAL, callback);
            if (action === Meta.KeyBindingAction.NONE)
                throw new Error(`Could not register Scrollwork keybinding ${name}`);
            this.registeredBindings.push(name);
        }
        for (const actor of global.get_window_actors())
            this._watch(actor.meta_window);
        this._focusChanged();
        this._queue();
    }

    _connect(object, signal, callback, collection = this.signals) {
        collection.push([object, object.connect(signal, callback)]);
    }

    _override(settings, key, replacement) {
        this.lease.override(settings, key, replacement);
    }

    _claimBindings() {
        const claimed = new Set([...Object.keys(this.bindings).flatMap(key => this.settings.get_strv(key)),
            ...NATIVE_BINDINGS.flatMap(([, , shortcuts]) => shortcuts), ...EXTERNAL_SHORTCUTS]
            .map(normalizeAccelerator));
        for (const schema_id of ['org.gnome.desktop.wm.keybindings',
            'org.gnome.settings-daemon.plugins.media-keys', 'org.gnome.shell.keybindings']) {
            const settings = new Gio.Settings({schema_id});
            for (const key of settings.settings_schema.list_keys()) {
                if (settings.get_value(key).get_type_string() !== 'as')
                    continue;
                const accelerators = settings.get_strv(key);
                const filtered = accelerators.filter(a => !claimed.has(normalizeAccelerator(a)));
                if (filtered.length !== accelerators.length)
                    this._override(settings, key, new GLib.Variant('as', filtered));
            }
        }
    }

    _launchCommand(argv) {
        Util.spawn(argv.map(arg => arg.startsWith('~/') ? `${GLib.get_home_dir()}/${arg.slice(2)}` : arg));
    }

    _pickColor() {
        Gio.DBus.session.call('org.gnome.Shell.Screenshot', '/org/gnome/Shell/Screenshot',
            'org.gnome.Shell.Screenshot', 'PickColor', null, null, Gio.DBusCallFlags.NONE, -1, null,
            (connection, result) => {
                try {
                    const [values] = connection.call_finish(result).deepUnpack();
                    const color = values.color.deepUnpack();
                    if (this.enabled) {
                        const hex = color.map(c => Math.round(c * 255).toString(16).padStart(2, '0')).join('');
                        St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, `#${hex}`);
                    }
                } catch (error) {
                    // Escape/cancellation is an ordinary exit from the native picker.
                    if (!error.matches?.(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                        console.warn(`Scrollwork color picker: ${error.message}`);
                }
            });
    }

    _watch(window) {
        if (this.windows.has(window) || ![Meta.WindowType.NORMAL, Meta.WindowType.DIALOG,
            Meta.WindowType.MODAL_DIALOG].includes(window.get_window_type()) || window.is_override_redirect())
            return;
        const record = {constraint: new Constraint(this), signals: [], attached: false,
            floating: false, manualFloating: null, fallbackFloating: false,
            initialTitle: null, mapped: window.get_compositor_private()?.mapped ?? false,
            placedRule: null, retries: 0, repairSource: 0,
            placementSource: 0, placing: false, appearance: null};
        if (record.mapped)
            record.initialTitle = window.title || null;
        this.windows.set(window, record);
        this._connect(window, 'unmanaged', () => this._forget(window), record.signals);
        for (const signal of ['workspace-changed', 'notify::minimized',
            'notify::fullscreen', 'notify::maximized-horizontally', 'notify::maximized-vertically',
            'notify::window-type', 'notify::transient-for', 'notify::on-all-workspaces',
            'notify::wm-class', 'notify::gtk-application-id', 'notify::title'])
            this._connect(window, signal, () => {
                if (signal.includes('fullscreen') || signal.includes('maximized')) {
                    record.retries = 0;
                    this._cancelRepair(record);
                }
                this._queue();
            }, record.signals);
        this._connect(window, 'size-changed', () => {
            if (record.placing)
                this._settlePlacement(window, record);
            if (record.attached) {
                if (sameRect(window.get_frame_rect(), this.targets.get(window)))
                    record.retries = 0;
                else
                    this._queue();
            }
            this._queue();
        }, record.signals);
        this._queue();
    }

    _forget(window) {
        const record = this.windows.get(window);
        if (!record)
            return;
        this._detach(window, record);
        this._cancelPlacement(record);
        record.appearance?.destroy();
        record.constraint.owner = null;
        for (const [object, id] of record.signals)
            object.disconnect(id);
        this.windows.delete(window);
        for (const strip of this.strips.values())
            strip.remove(window);
        this._queue();
    }

    _detach(window, record) {
        this._cancelRepair(record);
        this.targets.delete(window);
        if (record.attached) {
            window.remove_external_constraint(record.constraint);
            window.set_external_tiled?.(false);
            record.attached = false;
        }
    }

    _bringOnscreen(window) {
        if (window.is_fullscreen() || window.is_maximized() || window.minimized)
            return;
        const workspace = window.get_workspace();
        if (!workspace || Main.layoutManager.primaryIndex < 0)
            return;
        const area = workspace.get_work_area_for_monitor(Main.layoutManager.primaryIndex);
        const rect = window.get_frame_rect();
        window.move_frame(false,
            Math.max(area.x, Math.min(rect.x, area.x + area.width - rect.width)),
            Math.max(area.y, Math.min(rect.y, area.y + area.height - rect.height)));
    }

    _cancelRepair(record) {
        if (record.repairSource) {
            GLib.source_remove(record.repairSource);
            record.repairSource = 0;
        }
    }

    _checkCommit(window, record) {
        if (record.repairSource)
            return;
        record.repairSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, COMMIT_RETRY_MS, () => {
            record.repairSource = 0;
            if (!sameRect(window.get_frame_rect(), this.targets.get(window)))
                this._queue();
            else
                record.retries = 0;
            return GLib.SOURCE_REMOVE;
        });
    }

    _queue() {
        if (!this.enabled || this.pending)
            return;
        this.pending = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this.pending = 0;
            this._layout();
            return GLib.SOURCE_REMOVE;
        });
    }

    _focusChanged() {
        const window = global.display.focus_window;
        const strip = this.strips.get(window?.get_workspace());
        strip?.focus(window);
        this._queue();
        this.hoverTarget = null;
    }

    _hoverFocus(x, y) {
        if (!this.settings.get_boolean('hover-focus') || Main.overview.visible ||
            Main.actionMode !== Shell.ActionMode.NORMAL || this.grabbing)
            return;
        const [, , modifiers] = global.get_pointer();
        if (modifiers & (Clutter.ModifierType.BUTTON1_MASK | Clutter.ModifierType.BUTTON2_MASK |
            Clutter.ModifierType.BUTTON3_MASK))
            return;
        const picked = global.stage.get_actor_at_pos(Clutter.PickMode.REACTIVE, x, y);
        const actor = picked && global.get_window_actors().find(a => a === picked || a.contains(picked));
        const window = actor?.meta_window;
        if (window && this.windows.has(window) && window !== global.display.focus_window &&
            window.located_on_workspace(global.workspace_manager.get_active_workspace())) {
            this._cancelWarp();
            // Unlike activateWindow(), focus() does not raise a floating window.
            this.hoverTarget = window;
            window.focus(global.get_current_time());
        }
    }

    _cancelWarp() {
        if (this.warpSource)
            GLib.source_remove(this.warpSource);
        this.warpSource = 0;
    }

    _warpAfterLayout(window) {
        this._cancelWarp();
        if (!window || !this.settings.get_boolean('warp-pointer'))
            return;
        const started = GLib.get_monotonic_time();
        this.warpSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 16, () => {
            const actor = window.get_compositor_private();
            if (!this.windows.has(window) || Main.overview.visible ||
                global.display.focus_window !== window || GLib.get_monotonic_time() - started > 1500000) {
                this.warpSource = 0;
                return GLib.SOURCE_REMOVE;
            }
            const target = this.targets.get(window);
            if (this.pending || (target && !sameRect(window.get_frame_rect(), target)) ||
                actor?.get_transition('translation-x') || actor?.get_transition('translation-y'))
                return GLib.SOURCE_CONTINUE;
            const rect = window.get_frame_rect();
            const [x, y] = global.get_pointer();
            if (x < rect.x || y < rect.y || x >= rect.x + rect.width || y >= rect.y + rect.height)
                global.stage.context.get_backend().get_default_seat().warp_pointer(
                    rect.x + Math.floor(rect.width / 2), rect.y + Math.floor(rect.height / 2));
            this.warpSource = 0;
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelPlacement(record) {
        if (record.placementSource)
            GLib.source_remove(record.placementSource);
        record.placementSource = 0;
        record.placing = false;
    }

    _settlePlacement(window, record) {
        if (record.placementSource)
            GLib.source_remove(record.placementSource);
        record.placementSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 120, () => {
            record.placementSource = 0;
            record.placing = false;
            if (!window.is_fullscreen() && !window.minimized && window.get_workspace() &&
                Main.layoutManager.primaryIndex >= 0) {
                const area = window.get_workspace().get_work_area_for_monitor(Main.layoutManager.primaryIndex);
                const rect = floatingRect(DEFAULT_FLOAT, area, window.get_frame_rect());
                window.move_frame(false, rect.x, rect.y);
            }
            return GLib.SOURCE_REMOVE;
        });
    }

    _updateAppearance(window, record) {
        const actor = window.get_compositor_private();
        if (!actor || !record.mapped)
            return;
        record.appearance ??= new WindowAppearance(window, actor);
        record.appearance.update(this.settings, window.has_focus(),
            this.interfaceSettings.get_boolean('enable-animations') && !Main.overview.visible);
    }

    _animateMove(window, previous, target) {
        const actor = window.get_compositor_private();
        const duration = this.settings.get_int('movement-duration');
        if (!actor || !duration || Main.overview.visible ||
            !this.interfaceSettings.get_boolean('enable-animations') ||
            !window.located_on_workspace(global.workspace_manager.get_active_workspace()) ||
            previous.width !== target.width || previous.height !== target.height)
            return;
        const x = previous.x - target.x + actor.translation_x;
        const y = previous.y - target.y + actor.translation_y;
        actor.remove_transition('translation-x');
        actor.remove_transition('translation-y');
        actor.translation_x = x;
        actor.translation_y = y;
        actor.ease({translation_x: 0, translation_y: 0, duration,
            mode: Clutter.AnimationMode.EASE_OUT_QUINT});
    }

    _layout() {
        // Until output-local rendering AND input are proven, fail safely on multi-monitor.
        this.suspended = Main.layoutManager.monitors.length !== 1;
        for (const [window, record] of this.windows) {
            const workspace = window.get_workspace();
            if (record.mapped)
                record.initialTitle ??= window.title || null;
            const rule = matchRule(this.rules, {
                appIds: [window.get_gtk_application_id(), window.get_wm_class(),
                    window.get_wm_class_instance()].filter(Boolean),
                initialTitle: record.initialTitle ?? '',
            });
            const dialog = !!window.get_transient_for() || window.get_window_type() !== Meta.WindowType.NORMAL;
            record.floating = dialog || record.fallbackFloating || (record.manualFloating ?? (rule?.mode === 'float'));
            this._updateAppearance(window, record);
            const eligible = !this.suspended && !record.floating && workspace && !window.minimized &&
                !window.is_on_all_workspaces() && !window.get_transient_for() &&
                window.get_window_type() === Meta.WindowType.NORMAL;
            for (const [ws, strip] of this.strips) {
                if (!eligible || ws !== workspace)
                    strip.remove(window);
            }
            if (!eligible) {
                const wasAttached = record.attached;
                this._detach(window, record);
                if (wasAttached)
                    this._bringOnscreen(window);
                if (!this.suspended && workspace && record.mapped && !window.minimized &&
                    record.floating && record.placedRule !== (rule ?? DEFAULT_FLOAT)) {
                    record.placedRule = rule ?? DEFAULT_FLOAT;
                    if (rule?.fullscreen) {
                        window.make_fullscreen();
                    } else if (!window.is_fullscreen()) {
                        if (window.is_maximized())
                            window.unmaximize();
                        const area = workspace.get_work_area_for_monitor(Main.layoutManager.primaryIndex);
                        const rect = floatingRect({...rule, center: true}, area, window.get_frame_rect());
                        record.placing = true;
                        window.move_resize_frame(false, rect.x, rect.y, rect.width, rect.height);
                        this._settlePlacement(window, record);
                    }
                }
                continue;
            }
            record.placedRule = null;
            if (!this.strips.has(workspace))
                this.strips.set(workspace, new Strip());
            this.strips.get(workspace).add(window);
            if (!record.attached) {
                window.add_external_constraint(record.constraint);
                window.set_external_tiled?.(true);
                record.attached = true;
            }
            if (this.settings.get_boolean('suppress-maximize') && window.is_maximized() &&
                !window.is_fullscreen())
                window.unmaximize();
        }
        for (const [workspace, strip] of this.strips) {
            if (!strip.columns.length) {
                this.strips.delete(workspace);
                continue;
            }
            strip.focus(global.display.focus_window);
            const area = workspace.get_work_area_for_monitor(Main.layoutManager.primaryIndex);
            for (const [window, target] of strip.layout(area, this.settings.get_int('gap'),
                this.settings.get_int('inner-gap'))) {
                const record = this.windows.get(window);
                const changed = !sameRect(this.targets.get(window), target);
                if (changed) {
                    record.retries = 0;
                    this._cancelRepair(record);
                }
                this.targets.set(window, target);
                if (!window.is_fullscreen() && !window.is_maximized()) {
                    if (changed || !sameRect(window.get_frame_rect(), target)) {
                        // A pending configure gets time to commit before another is sent.
                        if (!changed && record.repairSource)
                            continue;
                        if (!changed && ++record.retries >= MAX_COMMIT_RETRIES) {
                            record.fallbackFloating = true;
                            record.floating = true;
                            this._detach(window, record);
                            this._bringOnscreen(window);
                            console.warn(`Scrollwork: floating ${window.title}: client did not accept assigned geometry`);
                            this._queue();
                            continue;
                        }
                        const previous = window.get_frame_rect();
                        window.move_resize_frame(false, target.x, target.y, target.width, target.height);
                        if (changed)
                            this._animateMove(window, previous, target);
                        this._checkCommit(window, record);
                    }
                } else {
                    this._cancelRepair(record);
                }
            }
        }
    }

    _activeStrip() {
        return this.strips.get(global.workspace_manager.get_active_workspace());
    }

    focus(direction) {
        const window = this._activeStrip()?.neighbor(direction);
        if (window) {
            Main.activateWindow(window);
            this._warpAfterLayout(window);
        }
    }

    move(direction) {
        this._activeStrip()?.move(direction);
        this._queue();
    }

    cycleWidth() {
        this._activeStrip()?.cycleWidth();
        this._queue();
    }

    toggleFloating() {
        const record = this.windows.get(global.display.focus_window);
        if (record) {
            record.manualFloating = !record.floating;
            record.fallbackFloating = false;
            record.retries = 0;
            this._queue();
        }
    }

    workspace(index, moveWindow) {
        const workspace = global.workspace_manager.get_workspace_by_index(index);
        if (!workspace)
            return;
        if (moveWindow)
            global.display.focus_window?.change_workspace(workspace);
        else {
            workspace.activate(global.get_current_time());
            this._warpAfterLayout(global.display.focus_window);
        }
    }

    disable() {
        this.enabled = false;
        if (this.pointerWatch)
            GLib.source_remove(this.pointerWatch);
        this.pointerWatch = 0;
        this._cancelWarp();
        this.edges?.destroy();
        this.edges = null;
        if (this.pending) {
            GLib.source_remove(this.pending);
            this.pending = 0;
        }
        for (const name of this.registeredBindings ?? [])
            Main.wm.removeKeybinding(name);
        this.registeredBindings = [];
        for (const [object, id] of this.signals ?? [])
            object.disconnect(id);
        for (const [window, record] of this.windows ?? []) {
            this._detach(window, record);
            this._cancelPlacement(record);
            record.appearance?.destroy();
            const actor = window.get_compositor_private();
            if (actor) {
                actor.remove_transition('translation-x');
                actor.remove_transition('translation-y');
                actor.translation_x = 0;
                actor.translation_y = 0;
            }
            this._bringOnscreen(window);
            record.constraint.owner = null;
            for (const [object, id] of record.signals)
                object.disconnect(id);
        }
        this.windows?.clear();
        this.targets?.clear();
        this.strips?.clear();
        this.signals = [];
        this.injections?.clear();
        this.lease?.release();
        this.lease = null;
        this.settings = null;
        this.interfaceSettings = null;
        this.rules = null;
    }
}
