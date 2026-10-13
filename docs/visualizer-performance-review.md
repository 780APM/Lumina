# Visualizer performance review — 14 October 2026

The player was profiled locally on Windows using Python 3.12.10, miniaudio 1.71,
and Matplotlib 3.11.2. Measurements use the existing 1200 × 800 player window,
with an approximately 828 × 506 visualizer canvas. These are local samples,
not guarantees for other display sizes or hardware.

## Measured cost per frame

| Mode | FFT and band aggregation | Update graphics | Render | Total mean | Total p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2D | 0.31 ms | 0.74 ms | 7.98 ms | 9.02 ms | 9.83 ms |
| Circular | 0.38 ms | 1.14 ms | 29.21 ms | 30.74 ms | 32.55 ms |
| 3D | 0.20 ms | 18.61 ms | 10.38 ms | 29.18 ms | 30.62 ms |

The benchmark feeds a synthetic signal through the real FFT and graphics update
functions, then calls the real TkAgg canvas draw. Five warm-up frames were
discarded. It measures rendering cost separately from audio decoding and OS
timer scheduling.

A separate brief real-playback test, with a generated WAV muted at the output,
measured approximately 29 visualizer redraws per second in 2D mode. A callback
scheduled every 10 ms ran 9.7 ms late on average and 14.3 ms late at p95. Its
largest delay was 206 ms; this short test includes startup, so that maximum
should not be interpreted as a steady-state frame cost.

## Cause

- `_tick_viz()` runs on Tk's UI thread and requests `draw_idle()` every 16 ms
  for 2D and circular modes. `draw_idle()` defers/coalesces a redraw; the actual
  rendering still executes on the UI thread. Rendering competes directly with
  pointer input, resizing, controls, scrolling, and marquee updates.
- 2D animates 144 individual Matplotlib patches (bars, reflections, peaks).
  Circular mode animates 144 polar patches and incurs the extra coordinate
  transformation cost. Circular rendering already exceeds the 16 ms request
  interval on this machine.
- `_draw_3d()` clears the axes, resets the camera and limits, and creates 40
  `bar3d()` collections every frame. Geometry recreation accounts for most of
  that mode's frame cost. A 50 ms timer limits frequency but does not shorten
  the individual UI stalls.
- The FFT is less than 0.4 ms in these measurements. Moving it to a worker will
  not address the dominant rendering cost. Tk widgets and their canvas must
  still be updated on the UI thread.

## Evaluated alternatives

An in-memory Matplotlib blitting prototype took approximately 9.08 ms per 2D
frame and 30.12 ms per circular frame. It did not materially improve the result:
almost everything in the plot is changing, and those artists still need drawing.
Blitting alone should not be presented as a complete fix.

A separate in-memory Tk Canvas prototype updated and painted 48 bars with their
reflections and peaks in a mean 2.22 ms (p95 2.58 ms). This was a renderer-only
prototype, not a completed replacement: it used a fixed color, omitted FFT and
interaction logic, and was not integrated into playback. Nevertheless, it
supports benchmarking a lighter renderer before investing in FFT optimizations.

## Recommended implementation

1. Render 2D and circular modes with persistent Tk Canvas rectangles/polygons.
   Create them once and update their coordinates and colors. Preserve the
   existing spectrum, reflections, peaks, and accent controls.
2. Use a 30 FPS starting budget, skip frames rather than queueing stale work,
   and suspend visualization while minimized or hidden. Throttle repaint during
   resizing and recompute layout when the size settles. Convert smoothing and
   decay to elapsed-time calculations so behavior stays consistent at different
   frame rates.
3. For 3D, create reusable collections once and update their vertex coordinates.
   Preserve camera rotation and avoid clearing the axes or allocating new
   collections on every frame. Benchmark this before selecting a frame budget.
4. Re-measure input latency during sustained real playback, dragging, resize,
   seeking, and mode changes; include a large/high-DPI window. Retain bounded
   PCM storage and avoid moving Tk rendering into a background thread.

The renderer implementation was not changed during this review.

References: [Tkinter event-loop threading model](https://docs.python.org/3/library/tkinter.html#threading-model)
and [Matplotlib blitting](https://matplotlib.org/stable/users/explain/animations/blitting.html).

## Windows icon requirements

For this desktop player, a browser favicon does not set the Windows taskbar icon.
The chosen concept should be exported to a multi-resolution ICO (16, 24, 32, 48,
64, 128, 256 pixels) and a PNG for Tk. Apply the icon to the running window, add
the ICO to PyInstaller's `EXE(icon=...)`, bundle the runtime assets, and set a
Windows application identity so taskbar grouping is consistent. Verify the
running app, Explorer icon, pinned shortcut, and high-DPI display independently.

Keep the mark bold and recognizable at 16/32 pixels. The current spec has no
custom icon, and MainWindow does not assign one. Final integration should follow
selection of a concept.
