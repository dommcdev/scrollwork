// Hyprland's configured CSS cubic curves, evaluated without a toolkit dependency.
export function cubicBezier(progress, x1, y1, x2, y2) {
    if (progress <= 0) return 0;
    if (progress >= 1) return 1;
    const sample = (t, p1, p2) => 3 * (1 - t) ** 2 * t * p1 +
        3 * (1 - t) * t ** 2 * p2 + t ** 3;
    let low = 0, high = 1;
    for (let i = 0; i < 16; i++) {
        const middle = (low + high) / 2;
        if (sample(middle, x1, x2) < progress) low = middle;
        else high = middle;
    }
    return sample((low + high) / 2, y1, y2);
}

export const borderProgress = p => cubicBezier(p, 0.23, 1, 0.32, 1);
export const fadeProgress = p => cubicBezier(p, 0.15, 0, 0.1, 1);
