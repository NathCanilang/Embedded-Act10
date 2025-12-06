/**
 * Main page JavaScript
 * Handles the face detection view, notifications, and detection events
 */

document.addEventListener("DOMContentLoaded", function () {
  const videoFeed = document.getElementById("video-feed");
  const videoOverlay = document.getElementById("video-overlay");
  const statusIndicator = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");
  const buzzerStatus = document.getElementById("buzzer-status");
  const refreshFacesBtn = document.getElementById("refresh-faces-btn");
  const reloadModelBtn = document.getElementById("reload-model-btn");
  const registeredFacesList = document.getElementById("registered-faces-list");
  const modelStatus = document.getElementById("model-status");
  const detectionLog = document.getElementById("detection-log");
  const clearLogBtn = document.getElementById("clear-log-btn");
  const toastContainer = document.getElementById("toast-container");

  // Track last event timestamp
  let lastEventTimestamp = Date.now() / 1000;
  let eventPollingInterval = null;

  // Initialize
  init();

  function init() {
    // Handle video feed loading - MJPEG streams don't fire onload reliably
    let streamStarted = false;

    function hideOverlay() {
      if (!streamStarted) {
        streamStarted = true;
        // Use both class and direct style to ensure it hides
        videoOverlay.classList.add("hidden");
        videoOverlay.style.display = "none";
        setStatus("active", "Camera Active");
        console.log("Camera stream started - overlay hidden");
      }
    }

    // Method 1: Check if video feed has natural dimensions (stream started)
    function checkStreamReady() {
      if (videoFeed.naturalWidth > 0 && videoFeed.naturalHeight > 0) {
        hideOverlay();
        return;
      }
      if (!streamStarted) {
        setTimeout(checkStreamReady, 200);
      }
    }

    // Method 2: Hide after reasonable timeout (fallback)
    setTimeout(() => {
      hideOverlay();
    }, 3000);

    // Start checking immediately
    checkStreamReady();

    videoFeed.onerror = function () {
      if (!streamStarted) {
        videoOverlay.innerHTML = `
                <span style="font-size: 2rem;">❌</span>
                <p class="mt-2">Camera Error - Please check your camera</p>
            `;
        setStatus("error", "Camera Error");
      }
    };

    // Load registered faces and model status
    loadRegisteredFaces();
    loadModelStatus();
    loadBuzzerStatus();

    // Start polling for detection events
    startEventPolling();

    // Refresh button
    if (refreshFacesBtn) {
      refreshFacesBtn.addEventListener("click", () => {
        loadRegisteredFaces();
        loadModelStatus();
      });
    }

    // Reload model button
    if (reloadModelBtn) {
      reloadModelBtn.addEventListener("click", reloadModel);
    }

    // Clear log button
    if (clearLogBtn) {
      clearLogBtn.addEventListener("click", clearDetectionLog);
    }
  }

  function setStatus(type, text) {
    statusText.textContent = text;
    statusIndicator.style.backgroundColor =
      type === "active" ? "#198754" : "#dc3545";
  }

  // === DETECTION EVENT POLLING ===
  function startEventPolling() {
    // Poll every 1 second for new events
    eventPollingInterval = setInterval(pollDetectionEvents, 1000);
  }

  async function pollDetectionEvents() {
    try {
      const response = await fetch(
        `/detection_events?since=${lastEventTimestamp}`
      );
      const data = await response.json();

      if (data.events && data.events.length > 0) {
        data.events.forEach((event) => {
          // Update last timestamp
          if (event.timestamp > lastEventTimestamp) {
            lastEventTimestamp = event.timestamp;
          }

          // Show notification toast
          showNotificationToast(event);

          // Add to detection log
          addToDetectionLog(event);
        });
      }
    } catch (error) {
      console.error("Error polling detection events:", error);
    }
  }

  function showNotificationToast(event) {
    const isRecognized = event.type === "recognized";
    const toastId = `toast-${Date.now()}`;
    const time = new Date(event.timestamp * 1000).toLocaleTimeString();

    const toastHtml = `
      <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="5000">
        <div class="toast-header ${
          isRecognized ? "bg-success" : "bg-danger"
        } text-white">
          <strong class="me-auto">${
            isRecognized ? "✅ Face Recognized" : "🔔 Unknown Face!"
          }</strong>
          <small>${time}</small>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body ${
          isRecognized ? "bg-success-subtle" : "bg-danger-subtle"
        }">
          ${
            isRecognized
              ? `<strong>${event.name}</strong> detected (${Math.round(
                  event.confidence * 100
                )}% confidence)`
              : "<strong>Unregistered person detected!</strong> Buzzer activated."
          }
        </div>
      </div>
    `;

    toastContainer.insertAdjacentHTML("beforeend", toastHtml);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement);
    toast.show();

    // Remove toast element after it's hidden
    toastElement.addEventListener("hidden.bs.toast", () => {
      toastElement.remove();
    });
  }

  function addToDetectionLog(event) {
    const isRecognized = event.type === "recognized";
    const time = new Date(event.timestamp * 1000).toLocaleTimeString();

    // Clear the "no detections" message if present
    if (detectionLog.querySelector(".text-muted")) {
      detectionLog.innerHTML = "";
    }

    const logEntry = document.createElement("div");
    logEntry.className = `detection-entry small p-1 mb-1 rounded ${
      isRecognized ? "bg-success-subtle" : "bg-danger-subtle"
    }`;
    logEntry.innerHTML = `
      <span class="badge ${
        isRecognized ? "bg-success" : "bg-danger"
      } me-1">${time}</span>
      ${
        isRecognized
          ? `<span class="text-success">${event.name}</span>`
          : '<span class="text-danger">Unknown</span>'
      }
    `;

    // Add to top of log
    detectionLog.insertBefore(logEntry, detectionLog.firstChild);

    // Keep only last 20 entries in the UI
    const entries = detectionLog.querySelectorAll(".detection-entry");
    if (entries.length > 20) {
      entries[entries.length - 1].remove();
    }
  }

  async function clearDetectionLog() {
    try {
      await fetch("/clear_events", { method: "POST" });
      detectionLog.innerHTML =
        '<p class="text-muted text-center small mb-0">No detections yet...</p>';
      lastEventTimestamp = Date.now() / 1000;
    } catch (error) {
      console.error("Error clearing events:", error);
    }
  }

  // === BUZZER STATUS ===
  async function loadBuzzerStatus() {
    try {
      const response = await fetch("/buzzer_status");
      const data = await response.json();

      if (buzzerStatus) {
        if (data.gpio_available) {
          buzzerStatus.textContent = "🔔 Buzzer Active";
          buzzerStatus.className = "ms-2 badge bg-success";
        } else if (data.simulation_mode) {
          buzzerStatus.textContent = "🔔 Simulated";
          buzzerStatus.className = "ms-2 badge bg-warning text-dark";
        } else {
          buzzerStatus.textContent = "🔕 Buzzer Off";
          buzzerStatus.className = "ms-2 badge bg-secondary";
        }
      }
    } catch (error) {
      console.error("Error loading buzzer status:", error);
    }
  }

  // === MODEL AND FACE MANAGEMENT ===
  async function reloadModel() {
    try {
      reloadModelBtn.disabled = true;
      reloadModelBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm"></span>';

      const response = await fetch("/reload_model", { method: "POST" });
      const data = await response.json();

      if (data.success) {
        alert("✅ " + data.message);
        loadModelStatus();
      } else {
        alert("❌ " + (data.error || "Failed to reload model"));
      }
    } catch (error) {
      console.error("Error reloading model:", error);
      alert("❌ Error reloading model");
    } finally {
      reloadModelBtn.disabled = false;
      reloadModelBtn.innerHTML = "🧠";
    }
  }

  async function loadModelStatus() {
    try {
      const response = await fetch("/model_status");
      const data = await response.json();

      if (modelStatus) {
        const statusIcon = data.model_loaded ? "✅" : "❌";
        modelStatus.innerHTML = `
          ${statusIcon} Model: ${data.model_loaded ? "Loaded" : "Not loaded"} | 
          ${data.num_encodings} encodings
        `;
      }
    } catch (error) {
      console.error("Error loading model status:", error);
    }
  }

  function loadRegisteredFaces() {
    fetch("/register/list")
      .then((response) => response.json())
      .then((data) => {
        if (data.success && data.faces.length > 0) {
          registeredFacesList.innerHTML = data.faces
            .map(
              (name) => `
                        <div class="face-item">
                            <div class="face-avatar">${name
                              .charAt(0)
                              .toUpperCase()}</div>
                            <span class="face-name">${name}</span>
                            <button class="btn btn-sm btn-outline-danger delete-face-btn" data-name="${name}" title="Delete">🗑️</button>
                        </div>
                    `
            )
            .join("");

          // Add delete event listeners
          document.querySelectorAll(".delete-face-btn").forEach((btn) => {
            btn.addEventListener("click", () => deleteFace(btn.dataset.name));
          });
        } else {
          registeredFacesList.innerHTML = `
                        <div class="no-faces-message">
                            <span class="icon">👤</span>
                            <p>No faces registered yet</p>
                            <a href="/register" class="btn btn-sm btn-outline-primary">Register Now</a>
                        </div>
                    `;
        }
      })
      .catch((error) => {
        console.error("Error loading faces:", error);
        registeredFacesList.innerHTML = `
                    <div class="no-faces-message">
                        <span class="icon">⚠️</span>
                        <p>Error loading faces</p>
                    </div>
                `;
      });
  }

  async function deleteFace(name) {
    if (!confirm(`Are you sure you want to delete "${name}"?`)) {
      return;
    }

    try {
      const response = await fetch(
        `/register/delete/${encodeURIComponent(name)}`,
        {
          method: "DELETE",
        }
      );
      const data = await response.json();

      if (data.success) {
        alert("✅ " + data.message);
        loadRegisteredFaces();
        loadModelStatus();
      } else {
        alert("❌ " + (data.error || "Failed to delete"));
      }
    } catch (error) {
      console.error("Error deleting face:", error);
      alert("❌ Error deleting face");
    }
  }

  // === CLEANUP ===
  window.addEventListener("beforeunload", function (e) {
    // Stop polling
    if (eventPollingInterval) {
      clearInterval(eventPollingInterval);
    }

    this.fetch("/close_cam")
      .then((res) => res.json())
      .then((data) => {
        console.log("camera closed");
      });
    e.preventDefault();
  });
});
