# Blurzy

Blurzy is an early-stage desktop video application for detecting and tracking
subjects, reviewing and editing annotations, and exporting video with selected
subjects blurred. It brings those steps into one PySide6 workflow, with
background workers for long-running detection, tracking, and export tasks.

The project grew through hands-on prototyping: its layered design separates
video/ML integrations from application workflows and the desktop interface, so
experiments can be refined without putting all of that complexity in the UI.

## What it can do

- Open and review video, with playback and frame-level controls.
- Run detection with supported model providers and track detections.
- Review and edit bounding-box annotations.
- Import and export annotation data, and export blurred video.
- Keep long-running work off the UI thread and surface progress in the app.

Blurzy is actively evolving. Model availability depends on the installed
providers and their hardware/runtime support; the project does not currently
claim a stable release or a model-independent detection experience.

## Website and documentation

- [Project homepage](https://CodeRSTech.github.io/Blurzy/)
- [Documentation](https://CodeRSTech.github.io/Blurzy/docs/)

The documentation is generated with MkDocs and the Darkly theme. To preview it:

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

The Pages workflow checks documentation builds on pull requests and deploys
the homepage and documentation on `master`. Select **GitHub Actions** under
**Settings → Pages → Build and deployment** to enable publication. See the
[documentation development guide](docs/development.md) for the complete site
build and preview commands.

## Get started

Blurzy requires Python 3.12 or newer. Create a virtual environment, then
install the package and development tools:

```bash
python -m venv .venv
```

Activate the environment, then run:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
blurzy
```

The editable install provides the `blurzy` GUI command as well. On Linux, run
the app from a graphical desktop session. PyTorch and model-provider support
can have platform-specific requirements; consult the relevant provider's
installation guidance if its models are unavailable.

## Development

Run the automated test suite from the repository root:

```bash
python -m pytest -q
```

The default suite is intended for local development and CI; it does not require
downloading model weights. Some video/GUI integration tests require Qt and
appropriate test media. Run a focused subset while iterating, for example:

```bash
python -m pytest tests/domain tests/shared -q
```

`pyproject.toml` is the canonical source for package dependencies and the
`dev` extra. `requirements.txt` remains available for existing workflows and
installs the project from that metadata.

For a distributable build:

```bash
python -m pip install -e ".[dist]"
python -m build
```

## Architecture

The source follows four broad layers:

| Layer | Responsibility |
| --- | --- |
| `src/app/domain` | Core video, session, detection, tracking, and export types |
| `src/app/application` | Workflows and services coordinating domain operations |
| `src/app/infrastructure` | Video, model, tracking, and export integrations/workers |
| `src/app/ui` | PySide6 window, widgets, handlers, and UI controller |

A typical detection flow starts in a UI handler, delegates through the
application facade and detection service, then runs in an infrastructure
worker. Worker signals carry progress and results back to the UI. See
[`docs/architecture.md`](docs/architecture.md) for a guided code map and
[`tests/README.md`](tests/README.md) for the test layout.

## Future additions: beyond detection and tracking

This section is a brainstorm, not a list of implemented features or promised
releases. Blurzy already provides detection, tracking strategies, bounding-box
editing, annotation import/export, and configurable Gaussian blur. The ideas
below extend that foundation into a more reliable and convenient workflow:

**Detect -> track -> refine -> review -> redact -> export.**

In plain terms, detection asks "where is the subject in this frame?" and
tracking asks "which subject does this box belong to over time?" Neither step
proves that every sensitive region remains covered. A box can stay on screen
while drifting away from a face, and a detector can miss a person entirely.
The goal should therefore be better coverage and easier correction, not just
boxes that survive longer.

### 1. Adaptive detection and scene-cut handling

> Give the tracker a fresh look at the video when it needs
one, rather than relying on old boxes or doing equally expensive work on every
frame. Treat a camera cut as a new scene, not as sudden movement by the same
people.

**Example usage:** In an interview with little movement, a fast processing
preset could use periodic detection between tracking updates. When someone
turns away, a box jumps, or the camera cuts to the audience, Blurzy would detect
again sooner. Periodic whole-frame checks would still look for new arrivals.

**Possible implementation:** Schedule detection using a regular maximum
interval plus triggers such as unmatched tracks, abrupt motion, or scene
changes. Reset or end tracks at confirmed cuts. Retain suitable low-confidence
detections for tracker association instead of discarding every weak candidate
before tracking.

**Tradeoffs:** More frequent detection costs time; fewer checks can miss
subjects. Camera flashes and fast pans can resemble cuts. Detector confidence
is a model score, not a calibrated probability that redaction is safe, so it
should not be the only scheduling signal.

### 2. Smoother boxes, bounded gap filling, and coverage margins

> Reduce shaking, bridge brief missed detections, and leave
some extra space around the subject. Keeping a box alive is useful only if it
continues to cover the right area.

**Example usage:** A face detector misses two frames as a speaker turns their
head. Blurzy could interpolate between the reliable boxes before and after
the gap, then add a user-selected margin around the face. The user could
preview the result before accepting it.

**Possible implementation:** Smooth box position and size, use motion
prediction for short gaps, and offer time-based limits on how long predictions
remain usable. For offline video, later detections can help refine earlier
gaps. Add padding relative to box size and clip expanded regions to frame
boundaries. Mark predicted or interpolated boxes separately from detections.

**Tradeoffs:** Smoothing can lag behind rapid movement and expose an edge;
padding obscures more content. Interpolation must not connect unrelated
subjects across long absences or scene cuts. Long or uncertain gaps should
be flagged for review rather than silently filled.

### 3. Appearance-aware tracking and identity correction

> Recognize a subject using visual clues as well as where
their box is. This could help keep two people from exchanging track IDs when
they cross paths.

**Example usage:** A user wants to blur one pedestrian throughout a clip but
leave another visible. After they pass each other, the tracker should keep
the blur assigned to the intended person. If it gets confused, the user could
split the track and reconnect the correct segments.

**Possible implementation:** Supply frame crops or image-derived features to
an appearance-aware tracker, combined with motion and overlap matching.
Blurzy's current DeepSORT adapter supplies box-derived features rather than
visual appearance embeddings; adding frame access would be a substantive
extension, not merely selecting a different tracker name.

**Tradeoffs:** Similar clothing, lighting changes, and occlusion still cause
errors. Appearance features add computation and may contain sensitive
information, so their persistence should be optional and explicit. A track ID
is not a verified real-world identity. Ambiguous matches should remain
reviewable, especially when some subjects are excluded from redaction.

### 4. A review timeline and uncertainty queue

> Show the user where to look instead of asking them to
inspect every frame with equal attention.

**Example usage:** After processing a ten-minute video, the timeline highlights
a disappearing face, a sudden box jump, and a possible identity swap. Clicking
each marker plays a short surrounding segment with overlays. The user fixes
the problem and marks that interval as reviewed.

**Possible implementation:** Flag suspicious gaps, abrupt size or position
changes, track births/deaths, and unreviewed ranges. Provide next/previous
issue navigation and distinguish model confidence from review status.
Changes to annotations, processing settings, or affected tracks should
invalidate relevant prior review markers.

**Tradeoffs:** Too many warnings create fatigue, while too few create false
reassurance. Offer adjustable warning sensitivity, but make clear that
"no warnings" does not mean "no missed subjects": an entirely undetected
person may produce no track anomaly at all.

### 5. Track-level editing and keyframe propagation

> Correct a subject once across a stretch of video instead
of drawing the same box repeatedly. A keyframe is a frame where the user
explicitly sets the desired region; intermediate frames are estimated.

**Example usage:** A user corrects a face box at the start and end of a turn.
Blurzy previews the intervening boxes. The user adds another keyframe if the
motion is not smooth, or manually draws a region for an object no model found.
They could also apply "redact this track" only between two timestamps.

**Possible implementation:** Extend existing box editing with track-wide and
time-range actions, keyframe interpolation, bounded forward/backward
propagation, and split/merge operations. Preserve manual corrections when
rerunning automation, with an explicit choice about replacing them.
Provide undo/redo and a preview of the affected range.

**Tradeoffs:** One incorrect propagated edit can damage many frames. Scope
must be visible: current frame, selected range, or whole track. Excluding a
track from redaction should be deliberate and easy to audit.

### 6. More masking effects and shapes

> Let users choose how much to hide and how the covered
region looks, rather than always applying a blurred rectangle.

**Example usage:** Use an ellipse around a face, a solid rectangle over a
license plate, or a polygon over a document. A segmentation mask, which marks
the pixels belonging to a subject, could hide a moving person while retaining
more of the surrounding scene.

**Possible implementation:** Add pixelation and solid-fill effects alongside
Gaussian blur, per-track effect settings, editable polygons/ellipses, and
optional segmentation-assisted masks. Support mask expansion and temporal
stabilization. Use the same rendering rules for preview and final export.

**Tradeoffs:** Segmentation adds model and editing cost, and detailed masks can
flicker or leave holes. Soft edges can leak information at the boundary.
Blur and pixelation do not guarantee anonymity; solid fill is a stronger
option for obscuring covered pixels, but an incomplete mask still exposes
content. Clothing, context, or audio may identify a subject even with a
fully covered face.

### 7. Specialized detection for faces, plates, and text

> Look for the sensitive detail itself rather than relying
only on general object boxes. OCR, or optical character recognition, turns
visible text into machine-readable words.

**Example usage:** In dashcam footage, detect plates instead of hiding whole
cars. In a recorded presentation, locate and cover an email address or
account number while leaving the rest of the slide readable.

**Possible implementation:** Offer task-specific model presets, OCR-based
candidate regions, user-defined text patterns, and manual fallback regions.
Keep coordinates aligned with the original video when inference uses resized
frames. Associate regions over time and make recognized text reviewable
without retaining it unnecessarily.

**Tradeoffs:** Small, rotated, moving, or partially hidden text is difficult.
OCR may misread a sensitive value, so exact text matching alone can miss it;
a user may prefer covering an entire text field. Specialized models need
representative evaluation and checks of model licenses and distribution terms.

### 8. Audio redaction as a separate, optional workflow

> Video masking cannot hide a name spoken aloud. Users may
also need to mute or replace a selected audio interval.

**Example usage:** Blur a customer's face and mute the moment their phone
number is spoken. A transcript could help locate the phrase, but the user
would listen to and adjust the selection before exporting.

**Possible implementation:** Start with manual timestamp-based muting or
tones, then explore optional speech transcription and phrase search.
Maintain audio/video synchronization and preview the exact edited interval.
Transcription should follow the same explicit local/cloud privacy choices
as video processing.

**Tradeoffs:** Speech recognition can miss words, languages, and overlapping
speakers. Audio boundaries may need extra padding. This requires an audio
pipeline rather than just another bounding-box model, so it is a larger,
separate extension.

### 9. Presets, resumable jobs, and hardware-aware processing

> Make common tasks repeatable and keep long jobs from
starting over after an interruption.

**Example usage:** A user selects a saved "face review" preset for several
clips, checks the estimated workload, and queues processing. After closing
the app, they resume completed stages and review each clip before export.
A lower-resolution proxy could make editing a large video more responsive.

**Possible implementation:** Extend existing settings and background workers
with named presets, a persistent job queue, stage checkpoints, and incremental
reprocessing of affected ranges. Record source fingerprints, model versions,
and settings so stale results are not reused. Map proxy coordinates and
timestamps back to the original media, and expose available CPU/GPU options.

**Tradeoffs:** Checkpoints consume storage and can contain sensitive
annotations. Hardware support varies, and reduced-resolution inference can
miss small faces or text. Speed presets should explain the coverage tradeoff
rather than promise equivalent results.

### 10. Export controls and privacy-conscious defaults

> Give users control over the deliverable, not just the
on-screen boxes.

**Example usage:** Export a redacted copy with selected quality settings,
choose whether to preserve or remove audio, and remove supported metadata
that could reveal location or authorship. Preview representative output
segments before sharing the result.

**Possible implementation:** Add codec/container and quality choices,
explicit audio handling, metadata inspection/removal, and a pre-export
summary of effects, exclusions, and unresolved review items. Handle
variable-frame-rate input and timestamp synchronization explicitly.
Write outputs separately from originals and report export failures clearly.

**Tradeoffs:** Codec availability and metadata handling vary by format.
Previewing a few segments cannot establish whole-video safety. Keep processing
local by default; any future cloud service should require informed consent
and describe uploads, retention, and deletion. Review reports and project
files should not expose original images or recognized text by default.

### Suggested priorities and evaluation

The most useful first investment is likely **coverage and correction**:
padding, bounded gap handling, uncertainty navigation, and range-based edits.
These improve the existing workflow before introducing expensive new models.
Next, explore masking choices, presets, and export controls. Appearance-aware
tracking, segmentation, OCR, and audio processing are larger experiments whose
value should be demonstrated on representative footage.

Evaluate proposed changes against a manually reviewed reference set containing
small subjects, fast motion, crossings, occlusions, low light, camera cuts, and
different frame rates. Compare against the existing pipeline, not just a
successful demonstration clip.

| Measure | What it tells us |
| --- | --- |
| Missed-redaction frames and longest uncovered interval | How often, and for how long, a sensitive region is exposed |
| Sensitive-region coverage and excess masked area | Whether masks cover the target without unnecessarily hiding the scene |
| Identity switches and fragmented tracks | Whether track-based redaction remains attached to the intended subject |
| Mask jitter and drift | Whether masks stay stable and aligned during movement |
| Review time, correction count, and warning usefulness | Whether automation actually reduces the user's workload |
| Processing speed, peak memory, and output synchronization | Whether the workflow is practical on supported hardware |

Keep observed detections, automated predictions, manual corrections, and
review status distinguishable. No detector, tracker, or redaction setting
should be presented as a guarantee of anonymization.

## Contributing

Start with the development setup above, run the tests relevant to your change,
and include a concise description of user-visible behavior in your pull
request. The focused notes in [`docs/engineering`](docs/engineering/) describe
the existing documentation and exception-handling conventions.
