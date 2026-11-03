# Appearance embeddings

Implementation: `src/app/infrastructure/tracking/reid_extractor.py`

Two people who cross paths can swap IDs if the tracker only knows *where* they
are. **Re-identification (Re-ID)** adds *what they look like*. Blurzy turns the
image inside each box into a short list of numbers (an **embedding**); similar
looking crops give similar lists. Comparing two lists with cosine similarity
says "probably the same person" or "different".

!!! info "No neural network"

    `PartBasedAppearanceEmbedder` uses hand-built colour and edge histograms.
    It needs no model weights or downloads, runs on the worker thread, and is
    cheap, but it is weaker than a learned Re-ID model. It captures clothing
    colour and texture, so two people dressed alike can look identical.

## Where this sits

![The worker owns the embedder; vectors flow to DeepSORT and BoT-SORT and, as isolated vectors, to the post-processor](../../../assets/api/tracking_pipeline/stack-reid-light.svg#only-light)
![The worker owns the embedder; vectors flow to DeepSORT and BoT-SORT and, as isolated vectors, to the post-processor](../../../assets/api/tracking_pipeline/stack-reid-dark.svg#only-dark)

Solid arrows are calls or data flow. The settings dialog stores
`reid_embedding_dim`; the worker builds the embedder from it at the start of
`run()`. The thick box is this page.

## From box to vector

![Pipeline: detection box, clamp and crop rejecting sides under two pixels, resize to 64 by 128, colour and edge histograms, unit-normalise, vector or None](../../../assets/api/tracking_pipeline/reid-light.svg#only-light)
![Pipeline: detection box, clamp and crop rejecting sides under two pixels, resize to 64 by 128, colour and edge histograms, unit-normalise, vector or None](../../../assets/api/tracking_pipeline/reid-dark.svg#only-dark)

Arrows are processing steps for one box.

1. The box is clamped to the frame and cropped. A crop narrower or shorter than
   2 px yields `None`.
2. The crop is resized to a canonical 64 x 128 grid, so box size does not
   change the vector.
3. Histograms are computed per body region: hue-saturation-value and CIE-LAB
   colour, and Sobel edge orientation (texture).
4. The result is scaled to length 1, so a dot product is the cosine similarity.

| Dimension | Layout | Trade-off |
| --- | --- | --- |
| 128 | Three horizontal strips, HSV and edges | Fastest |
| 256 (default) | Three strips plus a narrower centre core that ignores edge clutter | Balanced |
| 512 | Six regions (2 columns x 3 rows) with fine and coarse edges | Most detail, slowest |

Other values raise `ValueError`.

!!! warning "When there is no vector"

    The result is `None` for a missing frame (no readable local video), a tiny
    crop, or—for strategies—an all-zero descriptor. Frames must be 8-bit RGB;
    any other array shape or dtype raises `ValueError`, which the worker reports
    through `error_occurred`. Strategies and the linker treat `None` as "no
    appearance evidence", never as a mismatch.

## Who uses the vectors

![Sequence: the worker sends frame and boxes to the embedder, gets one vector per box, passes them to the strategy, keeps vectors of observed isolated boxes, and sends them to the post-processor](../../../assets/api/tracking_pipeline/reid-example-light.svg#only-light)
![Sequence: the worker sends frame and boxes to the embedder, gets one vector per box, passes them to the strategy, keeps vectors of observed isolated boxes, and sends them to the post-processor](../../../assets/api/tracking_pipeline/reid-example-dark.svg#only-dark)

Time flows downward. Vectors are computed for **every** strategy, even those
that ignore them, because the post-processor uses them too.

* **During matching.** [DeepSORT and BoT-SORT](strategies.md) compare each
  detection with per-track appearance memory.
* **After matching.** The worker keeps one vector per observed, *isolated* box
  (IoU below 0.25 with every other box in the frame). The
  [post-processor](post-processing.md) averages the first and last three
  vectors of each fragment and uses them to accept or reject a link.

!!! tip "Why isolation matters"

    A crop of two overlapping people contains both. Learning appearance from it
    would blend their identities, so overlapping boxes contribute no memory.

## Limitations

* Cost: one crop, resize and several histograms per box per frame, even when the
  strategy will ignore the result.
* Lighting changes and similar clothing reduce reliability; the linker therefore
  also requires geometric plausibility.
* Without a local, readable video file the whole feature silently degrades to
  motion and overlap.
