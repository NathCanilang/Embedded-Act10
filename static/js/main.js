/**
 * Main page JavaScript
 * Handles the face detection view
 */

document.addEventListener("DOMContentLoaded", function () {
  const videoFeed = document.getElementById("video-feed");
  const videoOverlay = document.getElementById("video-overlay");
  const statusIndicator = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");
  const refreshFacesBtn = document.getElementById("refresh-faces-btn");
  const reloadModelBtn = document.getElementById("reload-model-btn");
  const registeredFacesList = document.getElementById("registered-faces-list");
  const modelStatus = document.getElementById("model-status");

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
  }

  function setStatus(type, text) {
    statusText.textContent = text;
    statusIndicator.style.backgroundColor =
      type === "active" ? "#198754" : "#dc3545";
  }

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

  window.addEventListener("beforeunload", function (e) {
    this.fetch("/close_cam")
      .then((res) => res.json())
      .then((data) => {
        console.log("camera closed");
      });
    e.preventDefault();
  });
});
