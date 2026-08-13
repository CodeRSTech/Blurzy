# Model and Provider Management

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

## Why this is a must

As model support grows, a single flat picker gets harder to understand. Users need a mental map of the available options.

Good model/provider management also makes future integrations easier because each family can bring its own defaults, validation, and help text.

## Simple example

A beginner may know they want a YOLO-based workflow, but not know the exact model name. A provider-first picker narrows the decision before they choose the final model.

## Why it matters for Blurzy

Your README already calls out a provider dropdown as a wishlist item, and the dependency set shows multiple model ecosystems. This is a strong candidate for structured product improvement.
