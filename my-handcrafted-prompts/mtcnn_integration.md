# Integrating MTCNN for Face Detection

## Current models

Currently, Torch and Ultralytics YOLOv8 models are used, with mostly same structure.

For example: Torch model is structured as follows:

`src/app/infrastructure/detection/model/torch/loader_factory.py`
`src/app/infrastructure/detection/model/torch/mapper.py`
`src/app/infrastructure/detection/model/torch/model.py`

An MTCNN implementation was added (`/src/app/infrastructure/detection/model/mtcnn_tf/`) but tensorflow isn't available for the current python version.
Another MTCNN implementation (`/src/app/infrastructure/detection/model/mtcnn_torch/`) was added but it is not compatible with the current Torch version.

The latter's implementation is pending and, a quick search lists the following MTCNN implementations:

```python
import cv2
import torch
from PIL import Image
from facenet_pytorch import MTCNN

# 1. Automatically select GPU if available, otherwise fallback to CPU
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

# 2. Initialize MTCNN (keep_all=True detects multiple faces)
mtcnn = MTCNN(keep_all=True, device=device)

# 3. Load image via PIL (Required format for facenet-pytorch)
image_path = "your_image.jpg"
img = Image.open(image_path)

# 4. Detect faces, probabilities, and facial landmarks
boxes, probs, landmarks = mtcnn.detect(img, landmarks=True)

# 5. Draw the results using OpenCV for visualization
# Convert the PIL image back to a standard NumPy/OpenCV BGR array
img_cv = cv2.imread(image_path)

if boxes is not None:
    for box, prob, landmark in zip(boxes, probs, landmarks):
        # Only draw if detection confidence is reasonably high
        if prob > 0.90:
            # Draw bounding box (convert coordinates to integers)
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(img_cv, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw 5 facial landmarks (eyes, nose, mouth corners)
            for point in landmark:
                px, py = map(int, point)
                cv2.circle(img_cv, (px, py), 3, (0, 0, 255), -1)

# 6. Display the image
cv2.imshow('PyTorch MTCNN Detection', img_cv)
cv2.waitKey(0)
cv2.destroyAllWindows()
```

While the PyTorch MTCNN implementation works to the point of loading model,
It generates this when trying to detect faces. The error is rather obvious

```bash
17:46:06.833 | INFO     | Detecting objects in frame for session 'minmal_people_detection.mp4' | app.application.services.detection.execution_service:execute_for_current_frame:33
17:46:06.833 | WARNING  | MTCNN Torch inference failed | app.infrastructure.detection.model.mtcnn_torch.model:detect:57
Traceback (most recent call last):
  File "D:\Codes and Projects\Blurzy\src\app\infrastructure\detection\model\mtcnn_torch\model.py", line 55, in detect
    results = MTCNN.detect_faces(image=frame, threshold=DEFAULT_MTCNN_TORCH_CONFIDENCE_THRESHOLD)
AttributeError: type object 'MTCNN' has no attribute 'detect_faces'
```
