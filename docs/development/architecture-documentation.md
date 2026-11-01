# Writing architecture guides

## Architecture explains; API reference specifies

The root **Architecture** section is the beginner-friendly explanation of
Blurzy, not a second API reference. Its overview introduces the layers; its
component pages explain what each part does, why it exists, how it collaborates
with other parts, and how data moves through it. Introduce unfamiliar terms
before using them. Teach a concrete workflow with diagrams and images rather
than presenting only class inventories.

The generated **API reference** is the technical counterpart: signatures,
fields, method contracts, and detailed behavior belong in Python docstrings.
Link to those pages instead of copying their inventories. Add a component page
only when it teaches a meaningful workflow or design concept; do not create
source-only package inventories, since the API reference already covers modules.
See [Reference documentation](reference-documentation.md) for generation details.

Explain the implementation, not just the intended design. Label proposed
behavior and known limitations explicitly. Check ownership, data conversions,
failure paths, and lifecycle claims against source; a common interface does not
guarantee identical provider capabilities or crash-proof execution.

## Material reading aids

Use the enabled Material features to make the workflow easier to learn, not to
hide essential facts:

| Feature | Use it for | Keep visible |
| --- | --- | --- |
| Admonitions (`!!! note`, `!!! warning`, `!!! example`) | Ownership boundaries, limitations, or a small worked example | Safety and failure-path warnings |
| Collapsible details (`??? example`) | Optional calculations or implementation detail | The main explanation and its conclusions |
| Content tabs (`=== "Label"`) | Parallel alternatives, such as tracking strategies | A short comparison table before the tabs |
| Tables | Comparing roles, settings, payloads, or outcomes | Short cells rather than paragraphs squeezed into columns |
| SVG diagrams (D2) | Structure, data flow, state transitions, or signal sequences | Arrow semantics and an equivalent prose explanation |

Content tabs use `pymdownx.tabbed` with Material's alternate style. Label synthetic examples as illustrative rather than
presenting them as recorded inference output.

## Assets and formats

Use the configured [Material authoring features](documentation-style.md#material-authoring-features)
and the official [Material reference](https://squidfunk.github.io/mkdocs-material/reference/).
The current configuration supports image attributes and `figure`/`figcaption`
captions via `attr_list` and `md_in_html`. Do not assume caption extensions,
lightboxes, or other optional features are installed.

Keep component assets in `docs/assets/api/<component_name>/`, using a stable
snake_case name. Despite its historical `api` name, this directory also holds
architecture illustrations. Detection-engine assets, for example, belong in
`docs/assets/api/detection_engine/`.

| Asset | Convention |
| --- | --- |
| Architecture diagram | Editable source beside equivalent `*-light.svg` and `*-dark.svg` renders |
| Real input/output image | PNG; preserve dimensions when explaining pixel coordinates |
| Inference results | Downloadable structured data, such as JSON, alongside the images |
| Generation instructions | Tool requirements and exact commands in the relevant guide |

Architecture diagrams are **SVG pairs rendered from D2 sources**; do not add
Mermaid fences to architecture pages. (The Mermaid fence remains configured in
`mkdocs.yml` only for backwards compatibility.) Keep the editable `.d2` source
beside its renders; never commit only a screenshot of a diagram.

Explain a component with several focused diagrams rather than one dense one,
for example: structure and ownership, runtime flow, a signal sequence
(`shape: sequence_diagram`), a lifecycle or state machine, and failure paths.
Aim for about a dozen nodes or fewer per diagram so text stays readable at page
width, and say in one or two sentences what the arrows mean.

Cover infrastructure components, application services and managers, and UI
handlers with this approach. Small helpers do not need their own article: give
them a clear section and diagram on the page of the component they serve (the
video decode worker, for example, is explained on the video page). Adapter and
interface classes are explained only where they clarify a workflow.

Reference theme variants using Material's image fragments. From
`docs/architecture/infrastructure/detection/engine.md`, for example:

```markdown
![One image passes through the selected model wrapper to common results](../../../assets/api/detection_engine/flow-light.svg#only-light)
![One image passes through the selected model wrapper to common results](../../../assets/api/detection_engine/flow-dark.svg#only-dark)
```

Use descriptive alt text, readable text at page width, adequate contrast in both
themes, and arrows whose meaning is clear. Define whether arrows represent data,
calls, or dependencies; use a legend when necessary. Do not rely on color alone.
Both theme variants must carry the same information.

Install the D2 CLI separately (`d2` must be on PATH) and render every source
below `docs/assets/api`, or one directory, from the repository root:

```console
python scripts/render_diagrams.py
python scripts/render_diagrams.py docs/assets/api/detection_engine
```

The script runs `d2 --theme 0 --pad 24` for `*-light.svg` and
`d2 --theme 200 --pad 24` for `*-dark.svg`. Check the result in a real browser
(for example headless Chromium); generic SVG converters such as CairoSVG do not
render D2 styling faithfully.

## Worked examples are evidence

Where useful, accompany the abstract flow with a real input, actual results,
and an annotated output. Run the application's actual entry point rather than
bypassing it with a provider-only demonstration. Derive the annotations, result
table, counts, and downloadable records from the same returned data.

Record the input and weights provenance (including hashes where practical),
model name, relevant package versions, image dimensions/channel order, inference
settings, and reproduction command. Explain coordinates, confidence, and local
IDs rather than assuming readers understand them. Do not imply that detections
are ground truth or that per-image IDs identify people across frames.

Keep original pixels separate from annotations. Disclose limitations such as
missed objects, overlapping labels, provider-specific input conventions, and
failure results that cannot be distinguished from "nothing detected." Never
invent predictions or hide errors to obtain a plausible example.

Record media attribution and verify redistribution permissions before
publishing third-party examples. A supplied filename is not proof of origin or
license. If provenance is incomplete, state that uncertainty and resolve the
publication permission separately.

Rendering diagrams and running inference are **opt-in authoring steps**.
The static documentation build must not run models, download weights, import
the application, or require the desktop/ML stack. Commit the rendered assets
needed by readers and keep regeneration separate.

## Author and reviewer checklist

- Can a newcomer follow the workflow without reading the implementation first?
- Do diagrams, prose, and examples agree on responsibilities and actual behavior?
- Are intended behavior and current limitations clearly distinguished?
- Are editable sources, asset locations, commands, and provenance recorded?
- Is every diagram a D2-sourced SVG pair, and do both themes have equivalent readable diagrams and useful alt text?
- Do admonitions carry ownership boundaries, limitations, and failure paths?
- Do annotations, tables, and downloadable results describe the same real run?
- Are media permissions established and attribution accurate?
- Do navigation, relative links, images, and downloads work in the built site?

Run `python -m mkdocs build --strict` for page/asset/navigation changes. For
documentation-tooling changes, also run
`python -m unittest discover -s tests -p "test_docs_reference.py"`.
Inspect the rendered page in both themes; a successful build cannot establish
visual clarity or factual correctness.
