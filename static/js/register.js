// Registration JavaScript with Gesture Control
document.addEventListener("DOMContentLoaded", function () {
  // Get elements matching the HTML template
  const videoFeed = document.getElementById("video-feed");
  const videoOverlay = document.getElementById("video-overlay");
  const nameInput = document.getElementById("person-name");
  const startCaptureBtn = document.getElementById("start-capture-btn");
  const stopCaptureBtn = document.getElementById("stop-capture-btn");
  const registerBtn = document.getElementById("register-btn");
  const cancelBtn = document.getElementById("cancel-btn");
  const captureStatus = document.getElementById("capture-status");
  const statusText = document.getElementById("status-text");
  const progressContainer = document.getElementById(
    "capture-progress-container"
  );
  const progressBar = document.getElementById("capture-progress");
  const progressText = document.getElementById("progress-text");
  const capturedGrid = document.getElementById("captured-grid");
  const messageArea = document.getElementById("message-area");
  const captureFlash = document.getElementById("capture-flash");
  const registerForm = document.getElementById("register-form");

  // Get total images from hidden input
  const TOTAL_IMAGES = parseInt(
    document.getElementById("images-to-capture")?.value || "40"
  );

  let userName = "";
  let capturedCount = 0;
  let isCapturing = false;
  let captureInterval = null;
  let capturedImages = [];
  let gesturePollingInterval = null;
  let sessionStarted = false;

  // === HIDE SPINNER WHEN CAMERA IS READY ===
  let streamStarted = false;

  function hideOverlay() {
    if (!streamStarted && videoOverlay) {
      streamStarted = true;
      videoOverlay.classList.add("hidden");
      videoOverlay.style.display = "none";
      console.log("Register: Camera stream started - overlay hidden");
    }
  }

  // Check if video feed has natural dimensions (stream started)
  function checkStreamReady() {
    if (
      videoFeed &&
      videoFeed.naturalWidth > 0 &&
      videoFeed.naturalHeight > 0
    ) {
      hideOverlay();
      // Start gesture polling after camera is ready
      startGesturePolling();
      return;
    }
    if (!streamStarted) {
      setTimeout(checkStreamReady, 200);
    }
  }

  // Fallback: Hide after 3 seconds regardless
  setTimeout(() => {
    hideOverlay();
    startGesturePolling();
  }, 3000);

  // Start checking immediately
  checkStreamReady();

  // === GESTURE POLLING ===
  function startGesturePolling() {
    if (gesturePollingInterval) return;

    gesturePollingInterval = setInterval(pollGestureStatus, 300);
    console.log("Gesture polling started");
  }

  function stopGesturePolling() {
    if (gesturePollingInterval) {
      clearInterval(gesturePollingInterval);
      gesturePollingInterval = null;
    }
  }

  function pollGestureStatus() {
    fetch("/register/gesture_status")
      .then((response) => response.json())
      .then((data) => {
        if (data.gesture) {
          handleGesture(data.gesture);
        }
      })
      .catch((error) => {
        console.error("Gesture poll error:", error);
      });
  }

  function handleGesture(gesture) {
    console.log("Gesture detected:", gesture);

    switch (gesture) {
      case "thumbs_up":
        handleThumbsUp();
        break;
      case "thumbs_down":
        handleThumbsDown();
        break;
      case "one":
        handleOneGesture();
        break;
    }
  }

  // 👍 Thumbs Up: Start capture or capture image
  function handleThumbsUp() {
    if (!sessionStarted) {
      // If name is entered and session not started, start it
      userName = nameInput.value.trim();
      if (userName) {
        startCaptureBtn.click();
      } else {
        showMessage(
          "Please enter a name first, then show 👍 Thumbs Up",
          "warning"
        );
        nameInput.focus();
      }
    } else if (isCapturing) {
      // Capture is already running - show feedback
      setStatus("👍 Capturing... Keep showing thumbs up!", "success");
    }
  }

  // 👎 Thumbs Down: Cancel registration
  function handleThumbsDown() {
    if (sessionStarted) {
      showMessage(
        "👎 Thumbs Down detected - Cancelling registration...",
        "warning"
      );
      setTimeout(() => {
        stopCapturing();
        fetch("/register/cancel", { method: "POST" });
        resetCapture();
        showMessage("Registration cancelled via gesture", "info");
      }, 500);
    }
  }

  // ☝️ One: Register new user (reset form)
  function handleOneGesture() {
    if (!isCapturing) {
      showMessage(
        "☝️ One gesture detected - Ready for new registration",
        "info"
      );
      resetCapture();
      nameInput.focus();
    }
  }

  // === START CAPTURE BUTTON ===
  startCaptureBtn.addEventListener("click", function () {
    userName = nameInput.value.trim();
    if (!userName) {
      showMessage("Please enter a name first", "warning");
      nameInput.focus();
      return;
    }

    // Disable name input and show stop button
    nameInput.disabled = true;
    startCaptureBtn.classList.add("d-none");
    stopCaptureBtn.classList.remove("d-none");
    cancelBtn.classList.remove("d-none");

    // Show progress
    captureStatus.classList.remove("d-none");
    progressContainer.classList.remove("d-none");

    // Clear previous captures
    capturedImages = [];
    capturedGrid.innerHTML =
      '<p class="text-muted text-center">Capturing...</p>';

    // Start registration on server
    fetch("/register/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: userName }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "started") {
          sessionStarted = true;
          setStatus(
            "👍 Show Thumbs Up to capture, or wait for auto-capture",
            "info"
          );
          setTimeout(startCapturing, 1000);
        } else {
          showMessage(
            "Failed to start: " + (data.message || "Unknown error"),
            "danger"
          );
          resetCapture();
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        showMessage("Error starting registration", "danger");
        resetCapture();
      });
  });

  // === STOP CAPTURE BUTTON ===
  stopCaptureBtn.addEventListener("click", function () {
    stopCapturing();
    setStatus("Capture stopped", "warning");
  });

  // === CANCEL BUTTON ===
  cancelBtn.addEventListener("click", function () {
    if (confirm("Cancel registration and clear all captured images?")) {
      stopCapturing();
      fetch("/register/cancel", { method: "POST" });
      resetCapture();
      showMessage("Registration cancelled", "info");
    }
  });

  // === REGISTER FORM SUBMIT ===
  registerForm.addEventListener("submit", function (e) {
    e.preventDefault();
    completeRegistration();
  });

  // === START CAPTURING ===
  function startCapturing() {
    isCapturing = true;
    capturedCount = 0;
    updateProgress(0);

    setStatus("Capturing... Move your head slightly", "primary");

    // Capture images at intervals
    captureInterval = setInterval(captureImage, 400);
  }

  // === CAPTURE SINGLE IMAGE ===
  function captureImage() {
    if (!isCapturing) return;

    fetch("/register/capture_multiple", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ count: 1 }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "capturing" || data.status === "completed") {
          capturedCount = data.captured;
          updateProgress(capturedCount);

          // Flash effect on successful capture
          flashCapture();

          // Update status with validation info
          if (data.validation && data.validation.valid) {
            setStatus(
              `Captured ${capturedCount}/${TOTAL_IMAGES} - Good!`,
              "success"
            );
          }

          if (data.status === "completed" || capturedCount >= TOTAL_IMAGES) {
            stopCapturing();
            setStatus(
              "Capture complete! Click 'Complete Registration'",
              "success"
            );
            registerBtn.disabled = false;
          }
        } else if (data.status === "skipped") {
          // Show why it was skipped
          showValidationFeedback(data.validation);
        } else if (data.status === "error") {
          setStatus(data.message || "Capture error", "danger");
        }
      })
      .catch((error) => {
        console.error("Capture error:", error);
      });
  }

  // === SHOW VALIDATION FEEDBACK ===
  function showValidationFeedback(validation) {
    if (!validation) return;

    let message = "";
    if (validation.no_face) {
      message = "No face detected - look at camera";
    } else if (validation.blur) {
      message = "Too blurry - hold still";
    } else if (validation.brightness === "dark") {
      message = "Too dark - improve lighting";
    } else if (validation.brightness === "bright") {
      message = "Too bright - reduce lighting";
    } else if (validation.face_size === "small") {
      message = "Face too small - move closer";
    } else if (validation.face_size === "large") {
      message = "Face too close - move back";
    } else if (validation.error) {
      message = validation.error;
    }

    if (message) {
      setStatus(message, "warning");
    }
  }

  // === FLASH EFFECT ===
  function flashCapture() {
    if (captureFlash) {
      captureFlash.classList.remove("d-none");
      captureFlash.style.opacity = "0.5";
      setTimeout(() => {
        captureFlash.style.opacity = "0";
        setTimeout(() => captureFlash.classList.add("d-none"), 200);
      }, 100);
    }
  }

  // === UPDATE PROGRESS ===
  function updateProgress(count) {
    const percent = (count / TOTAL_IMAGES) * 100;
    progressBar.style.width = percent + "%";
    progressText.textContent = `${count} / ${TOTAL_IMAGES}`;
  }

  // === STOP CAPTURING ===
  function stopCapturing() {
    isCapturing = false;
    if (captureInterval) {
      clearInterval(captureInterval);
      captureInterval = null;
    }
    stopCaptureBtn.classList.add("d-none");
    startCaptureBtn.classList.remove("d-none");
  }

  // === COMPLETE REGISTRATION ===
  function completeRegistration() {
    setStatus("Training model...", "warning");
    registerBtn.disabled = true;
    registerBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';

    fetch("/register/complete", { method: "POST" })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          setStatus("Registration Complete!", "success");
          showMessage(
            `<strong>Success!</strong> ${userName} registered with ${data.images_saved} images.
             <br><a href="/" class="btn btn-primary btn-sm mt-2 me-2">Go to Detection</a>
             <button class="btn btn-secondary btn-sm mt-2" onclick="location.reload()">Register Another</button>`,
            "success"
          );
          cancelBtn.classList.add("d-none");
        } else {
          setStatus("Registration Failed", "danger");
          showMessage(data.message || "Unknown error", "danger");
          registerBtn.disabled = false;
          registerBtn.innerHTML =
            '<span class="me-2">✅</span> Complete Registration';
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        setStatus("Error completing registration", "danger");
        registerBtn.disabled = false;
        registerBtn.innerHTML =
          '<span class="me-2">✅</span> Complete Registration';
      });
  }

  // === RESET CAPTURE STATE ===
  function resetCapture() {
    stopCapturing();
    sessionStarted = false;
    nameInput.disabled = false;
    nameInput.value = "";
    startCaptureBtn.classList.remove("d-none");
    stopCaptureBtn.classList.add("d-none");
    cancelBtn.classList.add("d-none");
    registerBtn.disabled = true;
    registerBtn.innerHTML =
      '<span class="me-2">✅</span> Complete Registration';
    captureStatus.classList.add("d-none");
    progressContainer.classList.add("d-none");
    updateProgress(0);
    capturedGrid.innerHTML = `
      <div class="placeholder-box text-center p-4">
        <span class="placeholder-icon d-block" style="font-size: 3rem">👤</span>
        <p class="text-muted mb-0">Captured faces will appear here</p>
      </div>
    `;
  }

  // === SET STATUS MESSAGE ===
  function setStatus(message, type) {
    statusText.textContent = message;
    captureStatus.className = `capture-status alert alert-${type} mb-3`;
    captureStatus.classList.remove("d-none");
  }

  // === SHOW MESSAGE IN MESSAGE AREA ===
  function showMessage(message, type) {
    messageArea.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
  }

  // === ENTER KEY TO START ===
  nameInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      startCaptureBtn.click();
    }
  });
});
