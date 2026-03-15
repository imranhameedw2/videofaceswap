import os
import threading
import uuid
from pathlib import Path

import cv2
import face_recognition
import numpy as np
from flask import (Flask, Response, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from moviepy.editor import VideoFileClip

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

for d in (UPLOAD_DIR, OUTPUT_DIR):
    d.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1GB
app.secret_key = "replace-with-a-secure-key"

# Simple in-memory task tracker
TASKS = {}


def _safe_filename(filename: str) -> str:
    return os.path.basename(filename)


def _face_landmarks(image_rgb):
    """Return the first face landmarks found in an RGB image."""
    faces = face_recognition.face_landmarks(image_rgb)
    return faces[0] if faces else None


def _landmarks_to_points(landmarks):
    pts = []
    for key in (
        "chin",
        "left_eyebrow",
        "right_eyebrow",
        "nose_bridge",
        "nose_tip",
        "left_eye",
        "right_eye",
        "top_lip",
        "bottom_lip",
    ):
        pts.extend(landmarks.get(key, []))
    return np.array(pts, dtype=np.int32)


def _create_face_mask(image_shape, landmarks):
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    points = _landmarks_to_points(landmarks)
    if points.size == 0:
        return mask

    hull = cv2.convexHull(points)
    cv2.fillConvexPoly(mask, hull, 255)
    return mask


def _compute_similarity_transform(src_landmarks, dst_landmarks):
    def _mean_point(p):
        return np.mean(p, axis=0).astype(np.float32)

    src_pts = np.array(
        [_mean_point(src_landmarks[k]) for k in ("left_eye", "right_eye", "nose_tip")],
        dtype=np.float32,
    )
    dst_pts = np.array(
        [_mean_point(dst_landmarks[k]) for k in ("left_eye", "right_eye", "nose_tip")],
        dtype=np.float32,
    )

    M, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
    return M


def _swap_face_on_frame(frame_rgb, src_bgr, src_mask, src_landmarks, gender="all"):
    """Swap the face from `src_bgr` into the given frame (RGB)."""
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    h, w = frame_bgr.shape[:2]

    faces = face_recognition.face_landmarks(frame_rgb)
    if not faces:
        return frame_rgb

    if gender != "all":
        # If gender filtering is enabled, only swap the first detected face.
        faces = faces[:1]

    out = frame_bgr.copy()

    for landmarks in faces:
        M = _compute_similarity_transform(src_landmarks, landmarks)
        if M is None:
            continue

        warped_src = cv2.warpAffine(src_bgr, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        warped_mask = cv2.warpAffine(src_mask, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        _, warped_mask = cv2.threshold(warped_mask, 20, 255, cv2.THRESH_BINARY)

        center = np.mean(
            [
                np.mean(landmarks["left_eye"], axis=0),
                np.mean(landmarks["right_eye"], axis=0),
                np.mean(landmarks["nose_tip"], axis=0),
            ],
            axis=0,
        ).astype(np.int32)
        center = tuple(int(x) for x in center)

        try:
            out = cv2.seamlessClone(warped_src, out, warped_mask, center, cv2.NORMAL_CLONE)
        except cv2.error:
            # If seamlessClone fails, skip this face
            continue

    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


def _process_task(task_id: str, image_path: Path, video_path: Path, duration: int, gender: str):
    """Run the face swap process for a single task."""
    TASKS[task_id]["status"] = "processing"
    try:
        TASKS[task_id]["progress"] = 10

        # Load the user image and prepare the face source for swapping
        src_rgb = face_recognition.load_image_file(str(image_path))
        src_landmarks = _face_landmarks(src_rgb)
        if src_landmarks is None:
            raise RuntimeError("No face detected in the provided image.")

        src_bgr = cv2.cvtColor(src_rgb, cv2.COLOR_RGB2BGR)
        src_mask = _create_face_mask(src_bgr.shape, src_landmarks)
        TASKS[task_id]["progress"] = 25

        # Load video
        clip = VideoFileClip(str(video_path))
        TASKS[task_id]["progress"] = 35

        # Apply duration
        duration = min(duration, int(clip.duration))
        clip = clip.subclip(0, duration)
        TASKS[task_id]["progress"] = 45

        # Run face swapping over each frame (this is a simple approach and may be slow on long videos)
        total_frames = int(clip.fps * clip.duration)
        frame_counter = {"count": 0}

        def _process_frame(frame):
            frame_counter["count"] += 1
            if total_frames > 0 and frame_counter["count"] % 10 == 0:
                # Update progress in a rough way during frame processing.
                percent = 45 + min(24, int(25 * frame_counter["count"] / total_frames))
                TASKS[task_id]["progress"] = percent
            return _swap_face_on_frame(frame, src_bgr, src_mask, src_landmarks, gender)

        swapped = clip.fl_image(_process_frame)
        TASKS[task_id]["progress"] = 70

        # Write output
        output_path = OUTPUT_DIR / f"{task_id}.mp4"
        swapped.write_videofile(str(output_path), audio_codec="aac", verbose=False, logger=None)
        TASKS[task_id]["progress"] = 90

        TASKS[task_id]["status"] = "done"
        TASKS[task_id]["progress"] = 100
        TASKS[task_id]["output"] = str(output_path.name)
    except Exception as e:
        TASKS[task_id]["status"] = "error"
        TASKS[task_id]["message"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    image = request.files.get("image")
    video = request.files.get("video")
    duration = int(request.form.get("duration", 10))
    gender = request.form.get("gender", "all")

    if not image or not video:
        flash("Please select both an image and a source video.")
        return redirect(url_for("index"))

    task_id = uuid.uuid4().hex
    image_filename = f"{task_id}_{_safe_filename(image.filename)}"
    video_filename = f"{task_id}_{_safe_filename(video.filename)}"

    image_path = UPLOAD_DIR / image_filename
    video_path = UPLOAD_DIR / video_filename

    image.save(image_path)
    video.save(video_path)

    TASKS[task_id] = {"status": "queued", "progress": 0}

    thread = threading.Thread(
        target=_process_task,
        args=(task_id, image_path, video_path, duration, gender),
        daemon=True,
    )
    thread.start()

    return jsonify({"taskId": task_id})


@app.route("/status/<task_id>")
def status(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify({"status": "unknown"}), 404

    response = {
        "status": task.get("status", "unknown"),
        "progress": task.get("progress", 0),
        "message": task.get("message", ""),
    }
    if task.get("status") == "done":
        response["videoUrl"] = url_for("video", task_id=task_id)
        response["downloadUrl"] = url_for("download", task_id=task_id)
    return jsonify(response)


@app.route("/video/<task_id>")
def video(task_id):
    task = TASKS.get(task_id)
    if not task or task.get("status") != "done":
        return "Not ready", 404
    out_name = task.get("output")
    return send_file(OUTPUT_DIR / out_name, mimetype="video/mp4")


@app.route("/download/<task_id>")
def download(task_id):
    task = TASKS.get(task_id)
    if not task or task.get("status") != "done":
        return "Not ready", 404
    out_name = task.get("output")
    return send_file(OUTPUT_DIR / out_name, as_attachment=True)


if __name__ == "__main__":
    # Run on port 3000 for GitHub Codespaces compatibility (port 80 requires root and may not be forwarded)
    app.run(host="0.0.0.0", port=3000, debug=True)
