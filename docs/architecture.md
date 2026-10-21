# Architecture

**Blurzy** is a Qt desktop application organized into five broad layers under
`src/app`: 
  - **UI**, 
  - **Application**, 
  - **Domain**, 
  - **Infrastructure**, *and*
  - **Shared**. 

The layers separate user interaction and workflow coordination
from video/model integrations and core data types. They describe the current
code organization; they are not yet enforced as strict package boundaries.

## Layer relationships

```mermaid
%%{init: {"theme": "base", "layout": "elk", "themeVariables": {"fontFamily": "Roboto, Segoe UI, Arial, sans-serif", "fontSize": "15px", "lineColor": "#ffffff", "edgeLabelBackground": "#f8fafc", "textColor": "#0f172a"}, "elk": {"nodePlacementStrategy": "SIMPLE"}, "flowchart": {"htmlLabels": true, "useMaxWidth": true, "rankSpacing": 48, "nodeSpacing": 32, "padding": 10, "curve": "linear"}}}%%
flowchart TB
    UI["<div style='width:360px;text-align:center;line-height:1.6;color:#0f172a'><b style='font-size:19px'>UI</b><br/>User interaction and presentation<br/><span style='color:#334155'>Qt windows · widgets · handlers</span></div>"]
    APP["<div style='width:360px;text-align:center;line-height:1.6;color:#0f172a'><b style='font-size:19px'>Application</b><br/>Workflow coordination and contracts<br/><span style='color:#334155'>Facade · services · interfaces</span></div>"]
    DOMAIN["<div style='width:360px;text-align:center;line-height:1.6;color:#0f172a'><b style='font-size:19px'>Domain</b><br/>Core types, state, and rules<br/><span style='color:#334155'>Boxes · settings · video metadata</span></div>"]
    INFRA["<div style='width:360px;text-align:center;line-height:1.6;color:#0f172a'><b style='font-size:19px'>Infrastructure</b><br/>Technical implementations and adapters<br/><span style='color:#334155'>Video I/O · models · workers · storage</span></div>"]
    SHARED["<div style='width:360px;text-align:center;line-height:1.6;color:#0f172a'><b style='font-size:19px'>Shared</b><br/>Cross-cutting support for all layers<br/><span style='color:#334155'>Logging · exceptions · utilities</span></div>"]

    UI -->|Delegates via UI adapter| APP
    APP -->|Uses types and rules| DOMAIN
    %% Invisible links establish visual order, not dependencies.
    DOMAIN ~~~ INFRA
    INFRA -->|Conforms to contracts| APP
    INFRA -->|Uses types and rules| DOMAIN
    INFRA ~~~ SHARED

    classDef base color:#0f172a,stroke-width:1.5px,rx:8,ry:8;
    classDef ui fill:#dfe6ef,stroke:#60a5fa;
    classDef app fill:#dee2ef,stroke:#818cf8;
    classDef domain fill:#dcede5,stroke:#34d399;
    classDef infra fill:#dfe7dd,stroke:#fb923c;
    classDef shared fill:#e8eaec,stroke:#94a3b8,stroke-dasharray:5 4;

    class UI,APP,DOMAIN,INFRA,SHARED base;
    class UI ui;
    class APP app;
    class DOMAIN domain;
    class INFRA infra;
    class SHARED shared;
```

| Principal dependency         | Boundary                                      |
|------------------------------|-----------------------------------------------|
| UI → Application             | Delegates user actions through the UI adapter |
| Application → Domain         | Uses core types, state, and rules             |
| Infrastructure → Application | Conforms to Application-owned contracts       |
| Infrastructure → Domain      | Uses core types, state, and rules             |

The stack shows code organization; vertical order does not imply a dependency
chain. **Arrows in the key point toward the types or contracts a layer depends
on**, not the direction of runtime data or Qt signals. Shared supports multiple
layers and is not another step in the dependency chain.

???+ warning "Important"

    This is a map of the principal boundaries, not an exhaustive import graph or
    strict Clean Architecture. Application still imports concrete Infrastructure
    implementations for factories, session initialization, and persistence.
    `src/main.py` bootstraps Qt and wires Application, Window, and UIController.
    Domain owns core types and rules, not Qt workflows or model-specific code.

## Layer responsibilities and component map

| Layer                                               | Responsibility                                                                            | Main packages                                                                                           |
|-----------------------------------------------------|-------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| [UI](reference/ui/index.md)                         | Qt widgets and dialogs, user-action handlers, controller, and view state                  | `ui/handlers`, `ui/qt`, `ui/adapters`                                                                   |
| [Application](reference/application/index.md)       | Workflow facade, services, session lifecycle, manager coordination, and worker interfaces | `application/services`, `application/managers`, `application/interfaces`                                |
| [Domain](reference/domain/index.md)                 | Video/session/detection/tracking/export types and rules                                   | `domain/video`, `domain/session`, `domain/detection`, `domain/tracking`                                 |
| [Infrastructure](reference/infrastructure/index.md) | Video I/O, inference and tracking algorithms, background workers, persistence             | `infrastructure/video`, `infrastructure/detection`, `infrastructure/tracking`, `infrastructure/project` |
| [Shared](reference/shared/index.md)                 | Cross-cutting logging, exceptions, image and annotation utilities                         | `shared/`                                                                                               |

??? info
    
    Package-level component stubs follow the meaningful source-package structure.
    They provide a place to add detailed design notes without creating a page for
    every Python module. See the component links in the navigation.

### Important components

- `Application` (`src/app/application/application.py`) is the facade used by
  the UI. It owns the session manager and constructs application services.
- `UIController` (`src/app/ui/uicontroller.py`) owns the UI handlers and
  connects the Qt window to the facade.
- `SessionManager` and `SessionInitializer` coordinate per-video runtime
  objects. A `Session` holds the video runtime references and the four
  annotation/tracking data layers.
- Services such as `DetectionService`, `TrackingService`, and `ProjectService`
  coordinate use cases; managers own selected worker/session lifecycles.
- Infrastructure contains `VideoReader`, detection engines and provider
  models, tracking strategies, background workers, `SessionDataStore`, and
  `ProjectStore`.
- Application interfaces define worker/factory contracts consumed by
  application adapters and infrastructure implementations.

## Runtime workflows

### Startup and opening a video

`src/main.py` loads runtime configuration, initializes Qt, creates the
Application, Window, and UIController, then enters the Qt event loop. When a
video is opened, the UI handler calls the Application facade; session
management creates a session and `SessionInitializer` attaches the
`VideoReader`, domain `SessionState`, and `VideoDecodeWorker`. The decode
worker fills a bounded frame buffer, while playback controls request frames
through the Application and render them in the preview.

### Detection

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Roboto, Segoe UI, Arial, sans-serif",
    "fontSize": "18px",
    "primaryColor": "#dfe6ef",
    "primaryBorderColor": "#60a5fa",
    "primaryTextColor": "#0f172a",
    "actorBkg": "#eff6ff",
    "actorBorder": "#60a5fa",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#94a3b8",
    "signalColor": "#334155",
    "signalTextColor": "#0f172a",
    "labelBoxBkgColor": "#f8fafc",
    "labelBoxBorderColor": "#cbd5e1",
    "loopTextColor": "#0f172a"
  }
}}%%
sequenceDiagram
    autonumber
    actor User
    participant UI as UI (Qt Widget)
    participant App as Application (Facade)
    participant Worker as DetectionWorker (QThread)
    participant Engine as DetectionEngine (Model)
    participant Data as Session Data Layers

    User->>UI: Click "Detect"
    UI->>App: request_detection(session_id)
    App->>App: Validate session & prepare engine
    App->>Worker: start() [Background thread]
    
    activate Worker
    loop For each frame / batch
        Worker->>Engine: run_inference(frame)
        Engine-->>Worker: detection_results
        Worker-->>Data: append_results(batch)
        Worker-->>UI: signal: progress_updated(percent)
    end
    deactivate Worker

    Data-->>UI: signal: layers_changed()
    UI->>User: Render bounding boxes & overlays
```

Single-frame detection is also available. Background detection reads frames
and runs inference away from the GUI event loop; Qt signals carry result
batches, progress, completion, and errors back to application/UI code.
Detection engine factories and provider-specific model packages keep model
loading separate from UI widgets.

### Tracking, editing, and export

Tracking process detection boxes in Layer A/B into layer C after user presses the "Start Tracking" button. 

The tracking service then:
- validates the request,
- creates a `TrackingWorker` with a selected strategy, and
- later synchronizes output to Layer C. 

Layer D is the user-editable result layer. 
Every run refreshes Layer D boxes across all frames while preserving manual annotations. 
Trackers suppress nested same-class detector boxes before association and tag coasted estimates separately from detection-backed observations. 

#### Optional

Offline stitching uses bidirectional tracklet matching and Gaussian-smoothed
gap interpolation; rejected tails decay quickly. Preview-only box, mask, and
live-blur settings are separate from Render controls, which govern exported
video blur.
Annotation handlers update the selected layer and request the preview/table
to render again.

For blurred-video export, the export service reads the selected session and
uses Layer D when it contains boxes, otherwise Layer C. The export worker runs
the operation off the UI thread, reports progress, and supports cancellation.
The current video-rendering implementation is in the Application export
service and uses OpenCV; it is not a separate infrastructure renderer.
Annotation import/export services handle annotation data separately from
video rendering.

### Projects and persistence

The project service captures session paths, frame positions, settings, layer
data, and project directories in domain project documents. The infrastructure
`ProjectStore` serializes and validates the JSON project file. Loading
reopens the referenced videos and restores session settings and annotation
layers; unavailable or invalid sessions are reported as skipped.

## Data and background-work boundaries

- Domain data includes `SessionId`, `SessionState`, `ProcessingSettings`,
  `DetectionResult`, bounding boxes, project documents, and video metadata.
- Session annotation data is organized as Layer A (label/confidence-selected detections), Layer B
  (filtered/editable detections), Layer C (raw tracking output), and Layer D
  (editable tracking results).
- Infrastructure workers do not update Qt widgets directly. They emit Qt
  signals; application services/adapters and UI handlers consume those
  signals and update data or presentation.
- Session data store, project store, and video reader are distinct: project
  files persist project/session data, the session store holds live annotation
  layers, and the reader decodes source media.
- Exact threading and storage responsibilities vary by workflow. Consult the
  component page and implementation before changing a worker lifecycle.

## Finding your way around

- Application entry point and Qt bootstrap: `src/main.py`
- Workflow facade and composition: `src/app/application/application.py`
- Session lifecycle: `src/app/application/managers/`
- User-action handlers and controller: `src/app/ui/handlers/`,
  `src/app/ui/uicontroller.py`
- Qt window and widgets: `src/app/ui/qt/`
- Core types and rules: `src/app/domain/`
- Video, model, tracking, persistence, and worker implementations:
  `src/app/infrastructure/`
- Shared utilities: `src/app/shared/`
  - Tests organized by source layer: `tests/`

!!! info

    Blurzy is evolving. These pages describe the current implementation and
    provide a structure for future detail; they do not imply that every boundary
    is complete or every proposal is implemented.
