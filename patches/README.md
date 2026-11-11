# Experimental strict-layout Mutter patch

`mutter-51.1-external-layout.patch` applies to upstream Mutter **51.1**,
commit `9134e3a5869ce232bf95b77519005865747ba603`. This is a research patch,
not an upstream-supported API or a recommendation to replace the system package.
The normal extension ZIP neither contains nor installs a patched compositor.

## Why geometry constraints alone were insufficient

### Windowed viewer runtime

The installed **Scrollwork Test** launcher uses a saved runtime under
`~/.local/share/scrollwork-test/runtime`, with hashes in the sibling `runtime.json`.
It overlays libraries only inside a private mount namespace; system Mutter is
unchanged. `/tmp/opencode` is masked and the saved runtime bound at its original
embedded prefix, so the temporary build tree is not required at startup.

Build with `-Ddevkit=enabled` and apply `mdk-default-keyboard-capture.patch` for
the viewer. This separate one-line change defaults **Inhibit system shortcuts**
to enabled; it does not alter the compositor's strict-layout policy. The viewer
is launched manually against the saved outer Wayland socket, while Shell uses
`--headless --devkit`. Private PipeWire **and WirePlumber** are required to link
the screencast stream. Rendering uses software/cairo; GPU behavior is untested.

See [../TRY-TOMORROW.md](../TRY-TOMORROW.md) for using the prepared launcher.

### Geometry constraint limitations

The offline Electron fixture requests a minimum width of 644 logical pixels,
while its half-screen slot is 628. On stock Mutter, this client does not remain
at the assigned width and the extension eventually floats it. That is a failure
of the desired strict-tiling behavior, not a passing fallback solution for Discord.

Setting the four tiled-edge states alone was tested and did **not** fix it.
An experiment advertising maximized state was also insufficient and is **not**
included in the patch.

Mutter's `meta_window_wayland_move_resize_internal()` explicitly chooses the
unconstrained client size on normal surface commits, even if constraints computed
another size. The patch adds an opt-in `Meta.Window.set_external_tiled()` API and:

1. Advertises tiled edges without selecting Mutter's built-in tile geometry.
2. Runs constraints on commits for those windows and retains the constrained
   rectangle, rather than replacing it with the client's size.
3. Clips both actor painting and picking to that rectangle. Frame authority alone
   was insufficient: an oversized buffer still painted/received input outside
   its slot until this clipping was added.
4. Removes the owned clip when external tiling ends, including unmapped windows
   on another workspace. Normal floating windows retain stock behavior.

The extension enables this mode only when the optional API is present and only
while its own constraint is attached.

**Tradeoff:** a client that truly refuses to render smaller is clipped, not
magically reflowed. Right/bottom content can be inaccessible. This is a strict,
stable slot boundary, not proof of perfect Discord usability. No pixel scaling
or fake client maximization is used. Real Discord/OpenCode sessions still need
interactive validation, using a test profile rather than the user's live data.

## Reproduce without sudo or changing the live compositor

Build requirements include Meson/Ninja, Mutter's build dependencies,
GObject-Introspection scanner/compiler and Docutils' `rst2man`.

From the extension checkout, using a fresh temporary directory:

```sh
repo="$PWD"
root="$(mktemp -d /tmp/opencode/scrollwork-mutter.XXXXXX)"
git clone --depth=1 --branch=51.1 https://github.com/GNOME/mutter.git "$root/src"
git -C "$root/src" apply "$repo/patches/mutter-51.1-external-layout.patch"
meson setup "$root/build" "$root/src" --prefix="$root/install" \
  -Dudev_dir="$root/install/lib/udev" \
  -Dtests=disabled -Ddocs=false -Ddevkit=disabled -Dprofiler=false
meson compile -C "$root/build" -j 8
meson install -C "$root/build" --no-rebuild
SCROLLWORK_MUTTER_PREFIX="$root/install" npm run test:strict
```

The test launcher requires `bwrap` for a staged prefix. It overlays the staged
libraries/typelibs **inside a private mount namespace**, not the host `/usr`.
This is necessary because GI prepends hard-coded library paths; overriding only
`LD_LIBRARY_PATH` caused two copies of Cogl to load and abort. The namespace also
hides `/dev/dri`, exercising software-rendered headless GNOME. The staged upstream
51.1 build otherwise hit an unrelated render-device initialization failure on this
host. Physical GPU operation is not established by these tests.

All settings, D-Bus and client profiles remain isolated as in the normal suite.
The current development build is staged at
`/tmp/opencode/mutter-scrollwork-install`; nothing was installed system-wide.
