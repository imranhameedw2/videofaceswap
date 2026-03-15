# VideoFaceSwap

This repository contains a simple web application that lets you:

- Upload a **user image** and a **source video**
- Select a **gender mode** (Male / Female / All Faces)
- Choose a **duration** (5–60 seconds)
- Generate a **face-swap video** (placeholder implementation)
- View the resulting video and download it

## 🚀 Getting Started (Local)

### 1) Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2) Run the app

```bash
python app.py
```

Then open `http://localhost:5000` in your browser.

## 🧠 Notes

- This implementation uses a simple OpenCV-based face swap that attempts to replace detected faces in each frame with the face from the uploaded image.
- Results are best on videos where the face is relatively frontal and stable. The algorithm is **not** a production-quality face-swap model.
- You can improve quality by replacing `app.py`'s `_swap_face_on_frame` logic with a more advanced face-swap model (e.g., DeepFaceLab, FaceSwap, or a neural network-based approach).
