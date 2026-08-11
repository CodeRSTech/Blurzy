Certain behaviours are desired when dealing with data within the 'data table' and 'canvas' contexts, described below:

## Ctrl key is down

When the Ctrl key is held down, the following behaviours are expected:

1. **Multi-Selection**: Users should be able to select multiple rows or items in the data table or canvas by clicking with *mouse left* on them while holding down the Ctrl key. Each click should toggle the selection state of the item.
2. **Deselecting Items**: If an item is already selected, clicking on it again while holding the Ctrl key should deselect it without affecting other selected items.
3. **Drag and select** (data table only): Users should be able to click and drag to create a selection box that allows them to select multiple items at once while holding down the Ctrl key. Items within the selection box should be added to the current selection without deselecting previously selected items. Canvas selection however doesn't require Ctrl key to be held down. User can simply drag a rectangle on screen whist tool mode is edit to select boxes.

## Multiple items are selected

When multiple items are selected, the following behaviours are expected:

1. **Group Actions**: Users should be able to perform actions on all selected items simultaneously, such as deleting, moving, or applying changes. The actions should apply to all selected items without requiring individual confirmation for each item.
2. **Deselection**: Users should be able to deselect all items by clicking on an empty area of the data table or canvas, or by pressing a specific key (e.g., Esc) or key combination to clear the selection.
3. **Visual Feedback**: The interface should provide clear visual feedback indicating which items are currently selected. This could include highlighting the selected items, changing their border color, or displaying a selection count.
4. **Contextual Menus**: When multiple items are selected, right-clicking on any of the selected items should bring up a contextual menu (WITHOUT discarding selection) that provides options relevant to the group of selected items. The menu should include actions that can be performed on all selected items, such as "Delete", "Move", or "Export".
5. **Accidental Deselection Prevention**: The system should prevent accidental deselection of multiple items. For example, if a user right-clicks on a selected item, the selection should remain intact, and when user clicks outside the selection area, a confirmation prompt should appear before clearing the selection.
6. **Drag and Drop**: Users should be able to drag and drop multiple selected items to a new location within the data table or canvas. The system should provide visual cues during the drag operation to indicate that multiple items are being moved.

## Context menu actions

Most of the actions are easy, the ones requiring extra care are as follows:

### Select All

When the user selects the "Select All" option from the context menu, the following behaviours are expected:

1. **Select All Items**: All items in the data table or canvas should be selected, regardless of their current selection state.

### Deselect All

When the user selects the "Deselect All" option from the context menu, the following behaviours are expected:

1. **Deselect All Items**: All currently selected items in the data table or canvas should be deselected, regardless of their current selection state.

### Select inverse

When the user selects the "Select Inverse" option from the context menu, the following behaviours are expected:

1. **Inverse Selection**: All currently selected items should be deselected, and all currently unselected items should be selected. This allows users to quickly invert their selection without manually selecting or deselecting each item.

## Additional Considerations

Certain actions are required as of now, given as:

### Undo/Redo

This is a core requirement. The system should support undo and redo functionality for selection actions, allowing users to revert or reapply their selection changes. This includes actions such as selecting, deselecting, and performing group actions on selected items.

All box operations should be undoable and redoable, including:
- Selection and deselection of boxes
- Deletion of boxes
- Relabeling of boxes
- Moving boxes
- Duplicating boxes
- Any other actions that modify the state of boxes in the data table or canvas

For this, a new 'state management' system should be implemented to track changes and enable undo/redo functionality.

### Copy/Paste

This is a core requirement. The system should support copy and paste functionality for selected items, allowing users to duplicate their selection easily. This includes copying selected items from the data table or canvas and pasting them into the same or different context.

For this, the state management system should also handle copy and paste operations, ensuring that these actions can be undone and redone as needed.

### Documentation

The system should provide clear and comprehensive documentation for all selection-related actions, including undo/redo and copy/paste functionality. This documentation should be easily accessible to users and include examples and best practices for using these features effectively.

Readability counts and, beautiful is better than ugly.

Block comments are preferred over docstrings.

Any code that you modify or add should be well-documented with clear explanations of its purpose and functionality.

Simple is better than complex: Technical explanations with lots of jargon should be avoided. The documentation should be written in a way that is easy to understand for users of all technical backgrounds.