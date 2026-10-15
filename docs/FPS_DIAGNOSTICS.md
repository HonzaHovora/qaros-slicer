# Live Slicer FPS investigation, 2026-10-15

The user confirmed correct orientation with r13. Two current field reports use
the accepted r13 DLL (`821fdf85…`) and the same initial app placement.

`QAROS-VTK-diagnostics-20261015-165856-906.zip`, latest session
`20261015-165429-435776`, confirms the requested 50% render scale:

| Quantity | Value throughout this session |
|---|---|
| Actual eye render | 960 × 540 per eye |
| Stream color | 1920 × 1080 per eye, GPU upscaled |
| Stream depth | 960 × 540 per eye |
| Desktop view | 726 × 451 |
| Renders / extra depth / desktop restore renders | 2 / 0 / 0 |

After an initial SDK readiness wait of about 45–47 ms, readiness waiting falls
to about 12–13 ms and the stream reaches 19–19.5 completed stereo frames/s.
Both eye renders initially take about 30 ms in total. Over the next minutes
this rises to about 48 ms; the final full minute averages 13.39 stereo frames/s,
48.42 ms color rendering and 53.93 ms Python frame wall time. Copy calls remain
around 3–4 ms; SDK waiting at the end is about 14–17 ms. The session stops
normally after 3,742 stereo frames, without a reported bridge error.

The slowdown is real and occurs predominantly inside the host rendering calls.
Resolution and explicit render count do not increase. These wall-clock calls
include driver waits and GPU work, so they are not isolated GPU execution times.
The old five-second logs do not capture foreground changes, hardware clocks,
temperatures, within-window cadence or SDK eye poses. They cannot establish
whether focus, scene/view changes, shared GPU load, power/thermal limits or
another source of waiting causes the reported 11/15 FPS oscillation.

## r14 diagnostic experiment

Rendering, SDK transforms/layout and native DLL are unchanged. No performance
fix is claimed. The Python log now records one-second summaries and a bounded
sequence of frame samples; old timing/resolution keys remain available.
`SAMPLE_COLUMNS` describes each sample:

| Column | Meaning |
|---|---|
| serial | Stereo frame serial |
| start_monotonic_s | Start time on the process monotonic clock |
| start_interval_ms | Time since previous frame start, including across log windows |
| color_render_ms | Wall time inside both color Render calls |
| host_render_thread_cpu_ms | Render-thread CPU time for all host renders; includes driver CPU work/spinning, excludes sleeping waits; not GPU time |
| foreground_pid | Foreground process at frame start, null if unavailable |
| sdk_eye_changed | Whether SDK position/orientation/FOV changed since the previous frame (rounded to six decimals) |

One-second records also include last SDK eye poses/FOV and a read-only snapshot
of volume sampling, crop, input dimensions/spacing, property/input modification
times and object matrix. The snapshot is taken after restoring desktop state.
During the single-pass eye renders AutoAdjustSampleDistances is temporarily off
and ImageSampleDistance is 1, as in r12/r13; the snapshot shows restored values.
At most 512 per-frame samples are retained per window; `samples_omitted` reports
any overflow, while means/counts still cover every frame.

`host-system.log` samples optional NVIDIA NVML counters once per second on a
separate thread: clocks, temperature, power, performance state, clock-event
reason mask, utilization and device memory. It also records foreground PID and
executable basename (no window titles), cumulative process CPU seconds, a
monotonic timestamp and the sampler's own elapsed time. GPU figures describe
the entire device, not Slicer's share. Unsupported values are null, with NVML
error codes. Missing NVML does not prevent streaming or focus logging. The
monitor's start/stop never waits for a driver query on the render thread.

NVML reference: https://docs.nvidia.com/deploy/nvml-api/latest/index.html

`COLLECT-LOGS.cmd` includes the matching `host-system-N.log` files alongside
host Python/native logs. No screenshots, pixel readback, GPU timing queries,
new synchronization, driver-setting changes or external monitoring processes
are introduced. Diagnostic overhead is not assumed to be zero; CPU wall times
and the sampler's own duration are retained for assessment.

For the next run keep render scale at 50%, use one unchanged scene/view and
keep both windows visible if possible. Leave Visualizer active for 20–30 s,
Slicer active for 20–30 s, then repeat. Stop after 2–3 minutes, wait for Start
to become available and collect logs. Avoid rotating/zooming or changing the
preset during this specific run, so view cost and focus can be distinguished.

Tests cover optional/unavailable NVML, 64-bit handles/counters, balanced NVML
shutdown after partial initialization, nonblocking stop during a deliberately
stalled GPU query, frame cadence across log boundaries and the Windows focus
API. The official Slicer smoke test also checks the diagnostic snapshot against
its CT fixture and continues checking color/depth and state preservation.
Actual NVIDIA telemetry and its overhead still require the target-PC run.
