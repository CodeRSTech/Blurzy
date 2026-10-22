# Application service helpers

Source: `src/app/application/services/helpers/`

Shared service helpers keep repeated layer operations consistent. Coercion
functions normalize layer and import-mode values crossing the Qt boundary;
`ImportMode` defines how incoming data combines with an existing layer; and
the JSON/CSV helpers serialize, deserialize, and apply imported box data.
Detection and tracking services use these helpers for their respective layer
pairs.

These helpers handle annotation data, not project documents or rendered video.
See [Detection services](detection.md), [Tracking services](tracking.md), and
[Project persistence](../../infrastructure/project.md).
