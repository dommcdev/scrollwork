// Floating/initial-placement rules ported from the user's Hyprland profile.
// Focus traps and dimming are deliberately not part of these rules.
export const DEFAULT_RULES = [
    {appId: 'vicinae', mode: 'float', center: true},
    {appId: 'xdg-desktop-portal-gtk', mode: 'float', center: true, size: [0.5, 0.6]},
    {initialTitle: 'Open Files', mode: 'float', center: true, size: [0.7, 0.6]},
    {appId: 'com.dominic.wlctl', mode: 'float', center: true, size: [0.55, 0.55]},
    {appId: ['com.dominic.bluetui', 'com.dominic.wiremix'], mode: 'float', center: true, size: [0.5, 0.5]},
    {appId: 'com.dominic.calc', mode: 'float', center: true, size: [0.3, 0.5]},
    {appId: 'com.dominic.btop', mode: 'float', center: true, size: [0.7, 0.7]},
    {appId: 'com.dominic.cal', mode: 'float', center: true, size: [750, 820]},
    {appId: 'com.dominic.powerbutton', mode: 'float', center: true, size: [500, 250]},
    {appId: 'com.dominic.screensaver', mode: 'float', fullscreen: true},
    {appId: 'org.gnome.NautilusPreviewer', mode: 'float', center: true, size: [0.8, 0.9]},
    {appId: 'GrandOrgue', initialTitle: '^(Open organ|Program Settings)$',
        mode: 'float', center: true, size: [0.7, 0.75]},
    {appId: 'dev.noctalia.Noctalia', mode: 'float', size: [1080, 920]},
];

export function compileRules(json = '[]') {
    const custom = JSON.parse(json);
    if (!Array.isArray(custom))
        throw new Error('window-rules must be a JSON array');
    return [...DEFAULT_RULES, ...custom].map((rule, index) => {
        const invalid = message => { throw new Error(`Window rule ${index + 1}: ${message}`); };
        if (!rule || typeof rule !== 'object' || Array.isArray(rule))
            invalid('expected an object');
        const allowed = ['appId', 'initialTitle', 'mode', 'center', 'size', 'fullscreen'];
        if (Object.keys(rule).some(key => !allowed.includes(key)))
            invalid('unknown field');
        const ids = rule.appId === undefined ? null
            : Array.isArray(rule.appId) ? rule.appId : [rule.appId];
        if (ids && (!ids.length || ids.some(id => typeof id !== 'string' || !id.length)))
            invalid('appId must be a nonempty string or array of strings');
        if (rule.initialTitle !== undefined && typeof rule.initialTitle !== 'string')
            invalid('initialTitle must be a regular-expression string');
        if (!ids && rule.initialTitle === undefined)
            invalid('specify appId or initialTitle');
        if (!['float', 'tile'].includes(rule.mode))
            invalid('mode must be float or tile');
        for (const key of ['center', 'fullscreen']) {
            if (rule[key] !== undefined && typeof rule[key] !== 'boolean')
                invalid(`${key} must be a boolean`);
        }
        if (rule.size !== undefined && (!Array.isArray(rule.size) || rule.size.length !== 2 ||
            rule.size.some(n => typeof n !== 'number' || !Number.isFinite(n) || n <= 0) ||
            !((rule.size[0] <= 1 && rule.size[1] <= 1) || (rule.size[0] >= 1 && rule.size[1] >= 1))))
            invalid('size must contain two positive fractions (<=1) or two logical-pixel sizes (>=1)');
        if (rule.mode === 'tile' && (rule.size || rule.center || rule.fullscreen))
            invalid('placement options require float mode');
        return {...rule, ids, titlePattern: rule.initialTitle === undefined ? null : new RegExp(rule.initialTitle)};
    });
}

// Exact app IDs, initial-title expressions, last match wins.
export function matchRule(rules, {appIds, initialTitle}) {
    let result = null;
    for (const rule of rules) {
        if (rule.ids && !rule.ids.some(id => appIds.includes(id)))
            continue;
        if (rule.titlePattern && !rule.titlePattern.test(initialTitle))
            continue;
        result = rule;
    }
    return result;
}

export function floatingRect(rule, area, current) {
    let width = current.width, height = current.height;
    if (rule.size) {
        const fractional = rule.size.every(n => n <= 1);
        width = Math.round(rule.size[0] * (fractional ? area.width : 1));
        height = Math.round(rule.size[1] * (fractional ? area.height : 1));
    }
    width = Math.max(1, Math.min(width, area.width));
    height = Math.max(1, Math.min(height, area.height));
    return {
        x: rule.center ? Math.round(area.x + (area.width - width) / 2)
            : Math.max(area.x, Math.min(current.x, area.x + area.width - width)),
        y: rule.center ? Math.round(area.y + (area.height - height) / 2)
            : Math.max(area.y, Math.min(current.y, area.y + area.height - height)),
        width, height,
    };
}
