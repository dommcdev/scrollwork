// Pure layout policy. No GNOME dependencies; coordinates are logical pixels.
export const WIDTHS = [0.5, 1];

// Nearest partly/fully hidden column on either side of the usable viewport.
export function edgeNeighbors(columns, targets, area, gap) {
    const left = area.x + gap;
    const right = area.x + area.width - gap;
    let previous = null, next = null;
    for (const {id} of columns) {
        const rect = targets.get(id);
        if (!rect)
            continue;
        if (rect.x < left - 1 && (!previous || rect.x > targets.get(previous).x))
            previous = id;
        if (rect.x + rect.width > right + 1 && (!next || rect.x < targets.get(next).x))
            next = id;
    }
    return {left: previous, right: next};
}

export class Strip {
    constructor() {
        this.columns = [];
        this.focused = null;
        this.offset = 0;
        this.centered = false;
    }

    add(id) {
        if (this.columns.some(c => c.id === id))
            return;
        const index = this.columns.findIndex(c => c.id === this.focused);
        this.columns.splice(index < 0 ? this.columns.length : index + 1,
            0, {id, width: 0});
        this.focused = id;
        this.centered = false;
    }

    remove(id) {
        const index = this.columns.findIndex(c => c.id === id);
        if (index < 0)
            return;
        this.columns.splice(index, 1);
        if (this.focused === id)
            this.focused = this.columns[Math.min(index, this.columns.length - 1)]?.id ?? null;
        if (!this.columns.length)
            this.offset = 0;
    }

    focus(id) {
        if (this.columns.some(c => c.id === id)) {
            if (this.focused !== id)
                this.centered = false;
            this.focused = id;
        }
    }

    neighbor(direction) {
        const index = this.columns.findIndex(c => c.id === this.focused);
        return this.columns[index + direction]?.id ?? null;
    }

    move(direction) {
        const from = this.columns.findIndex(c => c.id === this.focused);
        const to = from + direction;
        if (from < 0 || to < 0 || to >= this.columns.length)
            return;
        [this.columns[from], this.columns[to]] = [this.columns[to], this.columns[from]];
    }

    cycleWidth() {
        const column = this.columns.find(c => c.id === this.focused);
        if (column)
            column.width = (column.width + 1) % WIDTHS.length;
    }

    center() {
        this.centered = true;
    }

    layout(area, requestedGap = 8, requestedInnerGap = 8) {
        if (area.width < 1 || area.height < 1)
            throw new RangeError('Work area must have positive dimensions');
        const gap = Math.max(0, Math.min(Math.floor(requestedGap),
            Math.floor((Math.min(area.width, area.height) - 1) / 2)));
        const available = area.width - 2 * gap;
        const innerGap = Math.max(0, Math.floor(requestedInnerGap));
        let x = 0;
        const positions = this.columns.map(column => {
            // Two halves share the between-column gap. Rounding down leaves at
            // most one unused pixel, rather than making focus scroll the pair.
            const width = this.columns.length === 1 || WIDTHS[column.width] === 1
                ? available : Math.max(1, Math.floor((available - innerGap) / 2));
            const item = {id: column.id, x, width};
            x += width + innerGap;
            return item;
        });
        const selected = positions.find(c => c.id === this.focused);
        if (selected) {
            if (this.centered)
                this.offset = selected.x - (available - selected.width) / 2;
            if (selected.x < this.offset)
                this.offset = selected.x;
            if (selected.x + selected.width > this.offset + available)
                this.offset = selected.x + selected.width - available;
        }
        const extent = Math.max(0, x - innerGap);
        if (!this.centered)
            this.offset = Math.max(0, Math.min(this.offset, Math.max(0, extent - available)));
        return new Map(positions.map(c => [c.id, {
            x: Math.round(area.x + gap + c.x - this.offset),
            y: area.y + gap,
            width: c.width,
            height: area.height - 2 * gap,
        }]));
    }
}
