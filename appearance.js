import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import GObject from 'gi://GObject';
import GLib from 'gi://GLib';
import {borderProgress, fadeProgress} from './animation.js';

// Clip the actual window texture to its frame (excluding CSD shadows).
const declarations = `
uniform vec4 swBounds;
uniform vec2 swTexture;
uniform float swRadius;
uniform float swBorder;
uniform vec3 swColor;
uniform float swOpacity;
`;
const fragment = `
vec2 p = cogl_tex_coord_in[0].xy * swTexture - swBounds.xy;
vec2 halfSize = swBounds.zw * 0.5;
float radius = min(swRadius, min(halfSize.x, halfSize.y));
vec2 q = abs(p - halfSize) - halfSize + vec2(radius);
float distance = length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - radius;
float coverage = 1.0 - smoothstep(-0.75, 0.75, distance);
float ring = smoothstep(-swBorder - 0.75, -swBorder + 0.75, distance);
if (swBorder < 0.01) ring = 0.0;
cogl_color_out = mix(cogl_color_out, vec4(swColor, 1.0), ring);
cogl_color_out *= coverage * swOpacity;
`;

const FrameEffect = GObject.registerClass({GTypeName: 'ScrollworkFrameEffect'},
class FrameEffect extends Clutter.ShaderEffect {
    vfunc_get_static_snippet() {
        return Cogl.Snippet.new(Cogl.SnippetHook.FRAGMENT, declarations, fragment);
    }

    vfunc_paint_target(node, context) {
        this.owner?.updateGeometry();
        super.vfunc_paint_target(node, context);
    }
});

export class WindowAppearance {
    constructor(window, actor) {
        this.window = window;
        this.actor = actor;
        this.effect = new FrameEffect();
        this.effect.owner = this;
        this.animationSource = 0;
        actor.add_effect_with_name('scrollwork-appearance', this.effect);
        this.destroySignal = actor.connect('destroy', () => {
            this._stopAnimation();
            this.effect.owner = null;
            this.actor = null;
            this.effect = null;
            this.destroySignal = 0;
        });
    }

    update(settings, focused, animate = true) {
        if (!this.actor)
            return;
        const enabled = settings.get_boolean('style-windows') && !this.window.is_fullscreen();
        this.effect.set_enabled(enabled);
        if (!enabled) {
            this._stopAnimation();
            this.target = null;
            return;
        }
        const [, color] = Cogl.Color.from_string(settings.get_string(focused ? 'active-border' : 'inactive-border'));
        const uniform = (name, values) => this.effect.set_uniform_float(name, values.length, values);
        uniform('swRadius', [settings.get_int('corner-radius')]);
        uniform('swBorder', [settings.get_int('border-width')]);
        const target = {color: color ? [color.red / 255, color.green / 255, color.blue / 255] : [0.8, 0.65, 0.97],
            opacity: focused ? 1 : settings.get_double('inactive-opacity')};
        const changed = JSON.stringify(target) !== JSON.stringify(this.target);
        if (!changed && (animate || !this.animationSource))
            return;
        this._stopAnimation();
        const previous = this.visual;
        this.target = target;
        const borderDuration = settings.get_int('border-fade-duration');
        const fadeDuration = settings.get_int('focus-fade-duration');
        if (!previous || !animate || (!borderDuration && !fadeDuration)) {
            this._applyVisual(target);
            return;
        }
        const started = GLib.get_monotonic_time();
        this.animationSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 16, () => {
            const elapsed = (GLib.get_monotonic_time() - started) / 1000;
            const border = borderProgress(borderDuration ? elapsed / borderDuration : 1);
            const fade = fadeProgress(fadeDuration ? elapsed / fadeDuration : 1);
            this._applyVisual({color: previous.color.map((v, i) => v + (target.color[i] - v) * border),
                opacity: previous.opacity + (target.opacity - previous.opacity) * fade});
            if (elapsed >= Math.max(borderDuration, fadeDuration)) {
                this.animationSource = 0;
                return GLib.SOURCE_REMOVE;
            }
            return GLib.SOURCE_CONTINUE;
        });
    }

    _applyVisual(visual) {
        this.visual = visual;
        this.effect.set_uniform_float('swColor', 3, visual.color);
        this.effect.set_uniform_float('swOpacity', 1, [visual.opacity]);
        this.effect.queue_repaint();
    }

    _stopAnimation() {
        if (this.animationSource)
            GLib.source_remove(this.animationSource);
        this.animationSource = 0;
    }

    updateGeometry() {
        if (!this.actor)
            return;
        const frame = this.window.get_frame_rect();
        const buffer = this.window.get_buffer_rect();
        const volume = this.actor.get_paint_volume();
        const origin = volume?.get_origin() ?? {x: 0, y: 0};
        const width = Math.round(volume?.get_width() ?? this.actor.width);
        const height = Math.round(volume?.get_height() ?? this.actor.height);
        // Clutter 51's offscreen target pads the paint volume by three pixels
        // (clutter_actor_box_enlarge_for_effects). Texture UVs include that pad.
        const left = Math.ceil(origin.x + width + 0.75) - width - 3;
        const top = Math.ceil(origin.y + height + 0.75) - height - 3;
        const uniform = (name, values) => this.effect.set_uniform_float(name, values.length, values);
        uniform('swBounds', [frame.x - buffer.x - left, frame.y - buffer.y - top, frame.width, frame.height]);
        const [valid, textureWidth, textureHeight] = this.effect.get_target_size();
        const scale = Math.ceil(this.actor.get_resource_scale());
        uniform('swTexture', valid ? [textureWidth / scale, textureHeight / scale] : [width + 3, height + 3]);
    }

    destroy() {
        this._stopAnimation();
        if (this.actor) {
            this.effect.owner = null;
            this.actor.disconnect(this.destroySignal);
            this.actor.remove_effect(this.effect);
            this.actor = null;
            this.effect = null;
            this.destroySignal = 0;
        }
    }
}
