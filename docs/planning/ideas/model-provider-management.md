# Model and Provider Management

!!! info "Current status"

    The application already exposes provider selection and model choices for
    supported YOLO, TorchVision, and MTCNN integrations. This proposal remains
    relevant to discoverability and provider-specific guidance; it is not a
    statement that provider selection is absent. See the
    [detection package notes](../../architecture/infrastructure/detection/index.md)
    and [architecture guide](../../architecture/overview.md).

## What this is

A cleaner way to choose *what kind* of model the user wants before choosing the exact model.

That usually means separating:

- provider or family
- concrete model
- model-specific options

For Blurzy, that could mean flows such as:

- Torch models
- YOLO models
- MTCNN models

## Original motivation

As model support grows, a flat picker can become harder to understand. Users
need a mental map of the available options.

Provider selection exists today. This proposal remains useful for improving
provider-specific defaults, validation, and help as integrations grow.

## Simple example

A beginner may know they want a YOLO-based workflow, but not know the exact model name. A provider-first picker narrows the decision before they choose the final model.

## Why it matters for Blurzy

The application supports multiple model ecosystems and exposes provider
selection. Continued work should focus on discoverability and provider-specific
guidance rather than adding the already-present selection control.
