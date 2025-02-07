document.addEventListener("DOMContentLoaded", function() {
    document.getElementById("uploadForm").addEventListener("submit", async function(event) {
        event.preventDefault();
        await uploadFile();
    });

    document.getElementById("interactiveBtn").addEventListener("click", async function() {
        await fetchInteractiveChart();
    });

    document.getElementById("recommendForm").addEventListener("submit", async function(event) {
        event.preventDefault();
        await fetchRecommendations();
    });

    document.getElementById("visualizeHistoryBtn").addEventListener("click", async function() {
        await fetchListeningHistoryVisualization();
    });
});

// 📤 Upload CSV File
async function uploadFile() {
    let fileInput = document.getElementById("fileInput");
    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        let response = await fetch("/upload", { method: "POST", body: formData });
        let result = await response.json();

        if (result.error) {
            alert(`❌ Error: ${result.error}`);
            return;
        }

        alert("✅ File uploaded successfully!");

        // Fetch summary stats & visualization
        await fetchSummary();
        await fetchVisualization();
    } catch (error) {
        console.error("Upload Error:", error);
        alert("⚠️ Upload failed. Please try again.");
    }
}

// 📊 Fetch Summary Stats
async function fetchSummary() {
    try {
        let response = await fetch("/summary");
        let data = await response.json();

        let summaryOutput = document.getElementById("summaryOutput");

        if (data.error) {
            summaryOutput.innerHTML = `<p style="color: red;">⚠️ ${data.error}</p>`;
            return;
        }

        summaryOutput.innerHTML = `
            <p><strong>Total Songs:</strong> ${data["Total Songs"]}</p>
            <p><strong>Unique Artists:</strong> ${data["Unique Artists"]}</p>
            <p><strong>Avg Duration (min):</strong> ${data["Avg Duration (min)"]}</p>
        `;
    } catch (error) {
        console.error("Summary Fetch Error:", error);
        document.getElementById("summaryOutput").innerHTML = "<p>⚠️ Failed to fetch summary.</p>";
    }
}

// 📈 Fetch Static Visualization
async function fetchVisualization() {
    try {
        let response = await fetch("/visualize");
        let data = await response.json();

        if (data.image_url) {
            let chartImage = document.getElementById("chartImage");
            chartImage.src = data.image_url;
            chartImage.style.display = "block";
        }
    } catch (error) {
        console.error("Visualization Fetch Error:", error);
    }
}

// 🎨 Fetch Listening History Visualization
async function fetchListeningHistoryVisualization() {
    try {
        let response = await fetch("/visualize-history");
        let data = await response.json();

        if (data.image_url) {
            let historyChart = document.getElementById("historyChart");
            historyChart.src = data.image_url;
            historyChart.style.display = "block";
        } else {
            alert(`⚠️ ${data.error}`);
        }
    } catch (error) {
        console.error("Listening History Visualization Fetch Error:", error);
    }
}

// 🎵 Fetch User's Top Spotify Artists
async function fetchSpotifyTopArtists() {
    try {
        let response = await fetch("/spotify-top-artists", { method: "GET" });
        let data = await response.json();

        let output = document.getElementById("spotifyArtistsOutput");
        output.innerHTML = "<h3>Your Top Artists:</h3>";

        if (data.error) {
            output.innerHTML += `<p>${data.error}</p>`;
        } else {
            data.forEach(artist => {
                output.innerHTML += `<p><strong>${artist.name}</strong></p>`;
            });
        }
    } catch (error) {
        console.error("Error fetching Spotify top artists:", error);
    }
}

// 🎵 Fetch Spotify Recommendations
async function fetchSpotifyRecommendations() {
    try {
        let response = await fetch("/spotify-recommendations", { method: "GET" });
        let data = await response.json();

        let output = document.getElementById("spotifyRecommendationsOutput");
        output.innerHTML = "<h3>Recommended Songs:</h3>";

        if (data.error) {
            output.innerHTML += `<p>${data.error}</p>`;
        } else {
            data.forEach(song => {
                output.innerHTML += `<p><strong>${song.name}</strong> by ${song.artist}</p>`;
            });
        }
    } catch (error) {
        console.error("Error fetching Spotify recommendations:", error);
    }
}
