# Architecture

Blurzy is a PySide6 desktop application organized into five broad layers under
`src/app`: **UI**, **Application**, **Domain**, **Infrastructure**, and
**Shared**. The layers separate user interaction and workflow coordination
from video/model integrations and core data types. They describe the current
code organization; they are not yet enforced as strict package boundaries.

## Layer relationships

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "Segoe UI, Arial, sans-serif", "fontSize": "14px"}, "flowchart": {"htmlLabels": true, "rankSpacing": 8, "padding": 12}}}%%
flowchart TB
    UI["<div style='width:560px;text-align:left;white-space:nowrap'><span style='display:inline-block;width:145px;border-right:1px solid #cbd5e1;margin-right:16px'><b>UI</b></span><span style='font-size:13px;color:#475569'>Qt window · widgets · handlers</span></div>"]
    APP["<div style='width:560px;text-align:left;white-space:nowrap'><span style='display:inline-block;width:145px;border-right:1px solid #cbd5e1;margin-right:16px'><b>Application</b></span><span style='font-size:13px;color:#475569'>Facade · services · managers · interfaces</span></div>"]
    DOMAIN["<div style='width:560px;text-align:left;white-space:nowrap'><span style='display:inline-block;width:145px;border-right:1px solid #cbd5e1;margin-right:16px'><b>Domain</b></span><span style='font-size:13px;color:#475569'>Types · state · rules</span></div>"]
    INFRA["<div style='width:560px;text-align:left;white-space:nowrap'><span style='display:inline-block;width:145px;border-right:1px solid #cbd5e1;margin-right:16px'><b>Infrastructure</b></span><span style='font-size:13px;color:#475569'>Video · models · workers · storage</span></div>"]
    SHARED["<div style='width:560px;text-align:left;white-space:nowrap'><span style='display:inline-block;width:145px;border-right:1px solid #cbd5e1;margin-right:16px'><b>Shared</b></span><span style='font-size:13px;color:#475569'>Cross-cutting: logging · exceptions · utilities</span></div>"]

    UI ~~~ APP ~~~ DOMAIN ~~~ INFRA ~~~ SHARED

    classDef base color:#0f172a,stroke-width:1px,rx:5,ry:5;
    classDef ui fill:#eff6ff,stroke:#93c5fd;
    classDef app fill:#eef2ff,stroke:#a5b4fc;
    classDef domain fill:#ecfdf5,stroke:#6ee7b7;
    classDef infra fill:#fff7ed,stroke:#fdba74;
    classDef shared fill:#f8fafc,stroke:#94a3b8,stroke-dasharray:4 3;

    class UI,APP,DOMAIN,INFRA,SHARED base;
    class UI ui;
    class APP app;
    class DOMAIN domain;
    class INFRA infra;
    class SHARED shared;
```

The stack shows code organization, not a strict dependency hierarchy. UI delegates user actions to Application, which coordinates Domain data and Infrastructure implementations. Infrastructure reads and writes Domain data and implements interfaces declared in Application. Shared utilities are imported across layers. Domain owns concepts such as boxes, processing settings, sessions, and video metadata; it is not the location for Qt workflows or model-specific code.

## Layer responsibilities and component map

| Layer | Responsibility | Main packages |
| --- | --- | --- |
| [UI](architecture/ui/index.md) | Qt widgets and dialogs, user-action handlers, controller, and view state | `ui/handlers`, `ui/qt`, `ui/adapters` |
| [Application](architecture/application/index.md) | Workflow facade, services, session lifecycle, manager coordination, and worker interfaces | `application/services`, `application/managers`, `application/interfaces` |
| [Domain](architecture/domain/index.md) | Video/session/detection/tracking/export types and rules | `domain/video`, `domain/session`, `domain/detection`, `domain/tracking` |
| [Infrastructure](architecture/infrastructure/index.md) | Video I/O, inference and tracking algorithms, background workers, persistence | `infrastructure/video`, `infrastructure/detection`, `infrastructure/tracking`, `infrastructure/project` |
| [Shared](architecture/shared/index.md) | Cross-cutting logging, exceptions, image and annotation utilities | `shared/` |

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
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "Segoe UI, Arial, sans-serif", "fontSize": "14px"}, "flowchart": {"htmlLabels": true, "rankSpacing": 8, "padding": 12}}}%%
flowchart TB
    USER(["User"])
    UI["<div style='width:560px;text-align:left'><b>UI</b><br/><span style='font-size:13px;color:#475569'>Qt widget and handler · request detection</span></div>"]
    APP["<div style='width:560px;text-align:left'><b>Application</b><br/><span style='font-size:13px;color:#475569'>Facade and DetectionService · validate session · prepare engine</span></div>"]
    WORKER["<div style='width:560px;text-align:left'><b>DetectionWorker</b><br/><span style='font-size:13px;color:#475569'>Background frame processing · report batches and progress</span></div>"]
    ENGINE["<div style='width:560px;text-align:left'><b>DetectionEngine and model</b><br/><span style='font-size:13px;color:#475569'>Run inference on each frame</span></div>"]
    DATA["<div style='width:560px;text-align:left'><b>Session data layers</b><br/><span style='font-size:13px;color:#475569'>Process detection batches</span></div>"]
    VIEW["<div style='width:560px;text-align:left'><b>UI presentation</b><br/><span style='font-size:13px;color:#475569'>Show progress · render results</span></div>"]

    USER --> UI --> APP
    APP -->|Create and start| WORKER
    WORKER -->|Frame| ENGINE
    ENGINE -->|Detection results| WORKER
    WORKER -->|Result batches and progress| APP
    APP -->|Update layers| DATA
    APP -->|Progress| VIEW
    DATA -->|Render results| VIEW

    classDef base color:#0f172a,stroke-width:1px,rx:5,ry:5;
    classDef ui fill:#eff6ff,stroke:#93c5fd;
    classDef app fill:#eef2ff,stroke:#a5b4fc;
    classDef worker fill:#fff7ed,stroke:#fdba74;
    classDef engine fill:#ecfdf5,stroke:#6ee7b7;
    classDef data fill:#f8fafc,stroke:#94a3b8;

    class UI,APP,WORKER,ENGINE,DATA,VIEW base;
    class UI,VIEW ui;
    class APP app;
    class WORKER worker;
    class ENGINE engine;
    class DATA data;
```

Single-frame detection is also available. Background detection reads frames
and runs inference away from the GUI event loop; Qt signals carry result
batches, progress, completion, and errors back to application/UI code.
Detection engine factories and provider-specific model packages keep model
loading separate from UI widgets.

### Tracking, editing, and export

Tracking starts from available detection boxes in Layer A or B. The tracking
service validates the request, creates a `TrackingWorker` with a selected
strategy, and later synchronizes output to Layer C. Layer D is the
user-editable result layer, populated from tracking output when needed.
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
- Session annotation data is organized as Layer A (raw detections), Layer B
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

Blurzy is evolving. These pages describe the current implementation and
provide a structure for future detail; they do not imply that every boundary
is complete or every proposal is implemented.
