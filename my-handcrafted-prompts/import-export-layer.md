## Import / Export Detections

Currently, the only way to populate Layer A and thus Layer B 
is to run detections (usually by the `DetectionWorker`)

In 'src/app/infrastructure/session/session_data_store.py' (lines 62-68):

```python
        # O(1) Memory Layout: Layer -> Frame Index -> List of Boxes
        self._data: dict[VideoDataLayer, dict[int, ListOfBoxes]] = {
            VideoDataLayer.A: defaultdict(list),
            VideoDataLayer.B: defaultdict(list),
            VideoDataLayer.C: defaultdict(list),
            VideoDataLayer.D: defaultdict(list),
        }
```
where: 
 - `VideoDataLayer` is an enum with values A, B, C, D (each representing respective layers of video data).
 - `ListOfBoxes` is a list of `BBoxViewModel` objects (from `app.domain.views.bounding_box_view_model`)

## New functionality: Import / Export Detections/Trackers

The plan is simple: user can export from any layer and import into any layer. 
This will allow users to save their work and load it back later, 
or share detections between different sessions or projects.

This will be the FEW known instances where we will allow users to directly manipulate the data in Layer A and Layer B.

Two new buttons are already added in the UI (in `../src/app/ui/qt/sections/right_panel.py`):

line 95-116:
```python
        self.detect_all_btn = QPushButton("Start Background Detection")
        #
        #   [====================================================]
        #   [                   Import / Export                  ]
        #   [====================================================]
        #
        #   [NEW] Import / Export detections button
        #   Intended functionality:
        #   First, a dialog asks whether to import or export detections.
        #   There are options for choosing whether to import or export and,
        #   Which layer to target (A/B)
        #       Case 1.:
        #           - User chooses import
        #           - a open file dialog opens to select a .json / .csv file to import
        #           - The imported detections are then added to the selected layer (A/B)
        #           [NOTE] A warning dialog must tell the users that any existing data will be overwritten
        #       Case 2.:
        #           - User chooses export
        #           - a save file dialog opens to select a .json / .csv file to export
        #           - The detections from the selected layer (A/B) are then exported to the selected file

        self.imp_exp_detections_button = QPushButton("Import / Export")
```

lines 180-200:
```python
        self.track_btn = QPushButton("Start Tracking")        #
        #   [====================================================]
        #   [                   Import / Export                  ]
        #   [====================================================]
        #
        #   [NEW] Import / Export trackers button
        #   Intended functionality:
        #   First, a dialog asks whether to import or export trackers.
        #   There are options for choosing whether to import or export and,
        #   Which layer to target (C/D)
        #       Case 1.:
        #           - User chooses import
        #           - a open file dialog opens to select a .json / .csv file to import
        #           - The imported trackers are then added to the selected layer (C/D)
        #           [NOTE] A warning dialog must tell the users that any existing data will be overwritten
        #       Case 2.:
        #           - User chooses export
        #           - a save file dialog opens to select a .json / .csv file to export
        #           - The trackers from the selected layer (C/D) are then exported to the selected file

        self.imp_exp_tracks_button = QPushButton("Import / Export")
```

## You'll need to implement the following to get the ball rolling:
1. A dialog box under 'src/app/ui/qt/dialogue_boxes'
2. Import, Export services in 'src/app/application/services/detection' and also,
3. Import, Export services in 'src/app/application/services/tracking' (note that the two import/export services under each module will be based on a common interface)
4. DataImport interface in new module under 'src/app/application/interfaces' 
5. DataExport interface in new module under 'src/app/application/interfaces' 