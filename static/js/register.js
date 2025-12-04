/**
 * Register page JavaScript
 * Handles multi-image face capture and registration
 */

document.addEventListener("DOMContentLoaded", function () {
  // DOM Elements
  const videoFeed = document.getElementById("video-feed");
  const videoOverlay = document.getElementById("video-overlay");
  const startCaptureBtn = document.getElementById("start-capture-btn");
  const stopCaptureBtn = document.getElementById("stop-capture-btn");
  const capturedGrid = document.getElementById("captured-grid");
  const personNameInput = document.getElementById("person-name");
  const registerForm = document.getElementById("register-form");
  const registerBtn = document.getElementById("register-btn");
  const cancelBtn = document.getElementById("cancel-btn");
  const messageArea = document.getElementById("message-area");
  const progressContainer = document.getElementById(
    "capture-progress-container"
  );
  const progressBar = document.getElementById("capture-progress");
  const progressText = document.getElementById("progress-text");
  const captureFlash = document.getElementById("capture-flash");

  // Configuration
  const IMAGES_TO_CAPTURE = parseInt(
    document.getElementById("images-to-capture")?.value || 30
  );
  const CAPTURE_INTERVAL = 500; // ms between captures

  // State
  let capturedImages = [];
  let captureInterval = null;
  let isCapturing = false;

  // Initialize
  init();

  function init() {
    // Handle video feed loading
    videoFeed.onload = function () {
      videoOverlay.classList.add("hidden");
    };

    videoFeed.onerror = function () {
      videoOverlay.innerHTML = `
        <span style="font-size: 2rem;">❌</span>
        <p class="mt-2">Camera Error - Please check your camera</p>
      `;
    };

    // Start capture button
    startCaptureBtn.addEventListener("click", startCapture);

    // Stop capture button
    stopCaptureBtn.addEventListener("click", stopCapture);

    // Register form
    registerForm.addEventListener("submit", handleRegister);

    // Cancel button
    cancelBtn.addEventListener("click", resetForm);
  }

  function startCapture() {
    const name = personNameInput.value.trim();

    if (!name) {
      showMessage("Please enter a name first", "danger");
      personNameInput.focus();
      return;
    }

    // Reset state
    capturedImages = [];
    updateGrid();

    // Update UI
    isCapturing = true;
    startCaptureBtn.classList.add("d-none");
    stopCaptureBtn.classList.remove("d-none");
    progressContainer.classList.remove("d-none");
    personNameInput.disabled = true;
    cancelBtn.classList.remove("d-none");
    updateProgress(0);

    showMessage("Capturing... Move your head slowly for variety", "info");

    // Start capturing at intervals
    captureInterval = setInterval(captureFrame, CAPTURE_INTERVAL);
  }

  function stopCapture() {
    isCapturing = false;

    if (captureInterval) {
      clearInterval(captureInterval);
      captureInterval = null;
    }

    startCaptureBtn.classList.remove("d-none");
    stopCaptureBtn.classList.add("d-none");

    if (capturedImages.length >= IMAGES_TO_CAPTURE) {
      registerBtn.disabled = false;
      showMessage(
        `✅ Captured ${capturedImages.length} images! Click "Complete Registration" to finish.`,
        "success"
      );
    } else if (capturedImages.length > 0) {
      showMessage(
        `Captured ${capturedImages.length}/${IMAGES_TO_CAPTURE} images. You can continue or register with current images.`,
        "warning"
      );
      registerBtn.disabled = false;
    } else {
      showMessage("No images captured", "warning");
    }
  }

  async function captureFrame() {
    if (!isCapturing || capturedImages.length >= IMAGES_TO_CAPTURE) {
      stopCapture();
      return;
    }

    const name = personNameInput.value.trim();

    try {
      const response = await fetch("/register/capture_multiple", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          index: capturedImages.length,
        }),
      });

      const data = await response.json();

      if (data.success) {
        capturedImages.push(data.image);
        updateProgress(capturedImages.length);
        updateGrid();
        flashEffect();

        // Check if we've captured enough
        if (capturedImages.length >= IMAGES_TO_CAPTURE) {
          stopCapture();
        }
      } else if (data.retry) {
        // Face not detected, continue trying
        console.log("Retry:", data.error);
      } else {
        console.error("Capture error:", data.error);
      }
    } catch (error) {
      console.error("Capture error:", error);
    }
  }

  function updateProgress(count) {
    const percentage = (count / IMAGES_TO_CAPTURE) * 100;
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `${count} / ${IMAGES_TO_CAPTURE}`;
  }

  function updateGrid() {
    if (capturedImages.length === 0) {
      capturedGrid.innerHTML = `
        <div class="placeholder-box text-center p-4">
          <span class="placeholder-icon d-block" style="font-size: 3rem;">👤</span>
          <p class="text-muted mb-0">Captured faces will appear here</p>
        </div>
      `;
      return;
    }

    // Show last 6 captured images in a grid
    const imagesToShow = capturedImages.slice(-6);
    capturedGrid.innerHTML = `
      <div class="row g-2">
        ${imagesToShow
          .map(
            (img, idx) => `
          <div class="col-4">
            <img src="data:image/jpeg;base64,${img}" 
                 class="img-fluid rounded captured-thumb" 
                 alt="Capture ${
                   capturedImages.length - imagesToShow.length + idx + 1
                 }">
          </div>
        `
          )
          .join("")}
      </div>
      <p class="text-center text-muted mt-2 mb-0">
        <small>Showing last ${imagesToShow.length} of ${
      capturedImages.length
    } captures</small>
      </p>
    `;
  }

  function flashEffect() {
    if (captureFlash) {
      captureFlash.classList.remove("d-none");
      setTimeout(() => {
        captureFlash.classList.add("d-none");
      }, 100);
    }
  }

  async function handleRegister(e) {
    e.preventDefault();

    const name = personNameInput.value.trim();

    if (!name) {
      showMessage("Please enter a name", "danger");
      return;
    }

    if (capturedImages.length === 0) {
      showMessage("Please capture some images first", "danger");
      return;
    }

    try {
      registerBtn.disabled = true;
      registerBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Training model...';

      const response = await fetch("/register/complete_registration", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
        }),
      });

      const data = await response.json();

      if (data.success) {
        showMessage(`✅ ${data.message}`, "success");

        // Reset after success
        setTimeout(() => {
          window.location.href = "/";
        }, 2000);
      } else {
        showMessage(data.error || "Registration failed", "danger");
        registerBtn.disabled = false;
      }
    } catch (error) {
      console.error("Registration error:", error);
      showMessage("Failed to register face", "danger");
      registerBtn.disabled = false;
    } finally {
      registerBtn.innerHTML =
        '<span class="me-2">✅</span> Complete Registration';
    }
  }

  function resetForm() {
    // Stop any ongoing capture
    if (captureInterval) {
      clearInterval(captureInterval);
      captureInterval = null;
    }
    isCapturing = false;

    // Reset state
    capturedImages = [];

    // Reset UI
    startCaptureBtn.classList.remove("d-none");
    stopCaptureBtn.classList.add("d-none");
    progressContainer.classList.add("d-none");
    updateProgress(0);
    updateGrid();

    personNameInput.value = "";
    personNameInput.disabled = false;
    registerBtn.disabled = true;
    cancelBtn.classList.add("d-none");

    messageArea.innerHTML = "";
  }

  function showMessage(message, type) {
    messageArea.innerHTML = `
      <div class="alert alert-${type} alert-dismissible fade show" role="alert">
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
    `;

    // Auto-dismiss after 5 seconds for non-error messages
    if (type !== "danger") {
      setTimeout(() => {
        const alert = messageArea.querySelector(".alert");
        if (alert) {
          alert.classList.remove("show");
          setTimeout(() => (messageArea.innerHTML = ""), 150);
        }
      }, 5000);
    }
  }
});

function showMessage(message, type) {
  messageArea.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    const alert = messageArea.querySelector(".alert");
    if (alert) {
      alert.classList.remove("show");
      setTimeout(() => (messageArea.innerHTML = ""), 150);
    }
  }, 5000);
}
