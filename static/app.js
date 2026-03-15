const form = document.getElementById("swapForm");
const durationInput = document.getElementById("duration");
const durationValue = document.getElementById("durationValue");
const progressSection = document.getElementById("progressSection");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const resultSection = document.getElementById("result");
const resultVideo = document.getElementById("resultVideo");
const downloadBtn = document.getElementById("downloadBtn");
const message = document.getElementById("message");
const generateBtn = document.getElementById("generateBtn");

let pollTimer = null;

function setMessage(text, isError = true) {
  if (!text) {
    message.classList.add("hidden");
    return;
  }
  message.textContent = text;
  message.classList.remove("hidden");
  if (isError) {
    message.style.background = "rgba(220, 80, 80, 0.15)";
    message.style.color = "#ffdddd";
  } else {
    message.style.background = "rgba(80, 220, 110, 0.18)";
    message.style.color = "#ddffdd";
  }
}

function updateProgress(percent) {
  progressFill.style.width = `${percent}%`;
  progressText.textContent = `${percent}%`;
}

function reset() {
  clearInterval(pollTimer);
  pollTimer = null;
  progressSection.classList.add("hidden");
  resultSection.classList.add("hidden");
  updateProgress(0);
  setMessage("");
  generateBtn.disabled = false;
}

function pollStatus(taskId) {
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/status/${taskId}`);
      if (!res.ok) {
        throw new Error("Unable to check progress");
      }
      const json = await res.json();
      const progress = Math.min(100, Math.max(0, json.progress ?? 0));
      updateProgress(progress);

      if (json.status === "done") {
        clearInterval(pollTimer);
        pollTimer = null;
        setMessage("Done! Your video is ready.", false);
        resultSection.classList.remove("hidden");
        resultVideo.src = json.videoUrl;
        downloadBtn.href = json.downloadUrl;
        generateBtn.disabled = false;
      }

      if (json.status === "error") {
        clearInterval(pollTimer);
        pollTimer = null;
        setMessage(json.message || "An error occurred during processing.");
        generateBtn.disabled = false;
      }
    } catch (err) {
      clearInterval(pollTimer);
      pollTimer = null;
      setMessage(err.message || "Failed to poll status.");
      generateBtn.disabled = false;
    }
  }, 1200);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  reset();

  const formData = new FormData(form);
  generateBtn.disabled = true;
  progressSection.classList.remove("hidden");
  updateProgress(5);

  try {
    const res = await fetch("/generate", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      throw new Error("Upload failed");
    }

    const json = await res.json();
    const taskId = json.taskId;
    if (!taskId) {
      throw new Error("Invalid response from server");
    }

    setMessage("Processing... This may take a while.", false);
    pollStatus(taskId);
  } catch (err) {
    setMessage(err.message || "Unexpected error");
    generateBtn.disabled = false;
  }
});

durationInput.addEventListener("input", () => {
  durationValue.textContent = durationInput.value;
});
