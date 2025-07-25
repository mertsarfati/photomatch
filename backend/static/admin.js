document.addEventListener("DOMContentLoaded", () => {
  fetchEvents(); // Etkinlikleri yükle

  const createForm = document.getElementById("create-form");
  if (createForm) {
    createForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const name = document.getElementById("event-name").value.trim();
      const location = document.getElementById("event-location").value.trim();
      if (!name) return;

      fetch("/create-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, location })
      })
      .then(res => res.json())
      .then(data => {
        document.getElementById("event-name").value = "";
        document.getElementById("event-location").value = "";
        fetchEvents(); // listeyi güncelle
        openEvent(data.id); // yeni etkinliğe geç
      });
    });
  }

  const uploadForm = document.getElementById("upload-form");
  if (uploadForm) {
    uploadForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const files = document.getElementById("file-input").files;
      const eventId = uploadForm.dataset.event;
      if (!eventId || files.length === 0) return;

      for (let file of files) {
        const formData = new FormData();
        formData.append("file", file);
        fetch(`/upload/${eventId}`, {
          method: "POST",
          body: formData
        }).then(() => fetchGallery(eventId));
      }
    });
  }
});

function fetchEvents() {
  fetch("/list-events")
    .then(res => res.json())
    .then(data => {
      const list = document.getElementById("event-list");
      list.innerHTML = "";

      for (let event of data.events) {
        const li = document.createElement("li");
        li.innerHTML = `
          <strong>${event.name}</strong> (${event.id})
          ${event.location ? `📍 ${event.location}` : ""}
          ${event.cover ? `<img src="${event.cover}" alt="cover" style="height:40px;margin-left:8px;">` : ""}
          <br>
          <button onclick="openEvent('${event.id}')">Yönet</button>
          <a href="/qrcode/${event.id}" target="_blank">📱 QR</a>
          <a href="/event-info/${event.id}" target="_blank">ℹ Bilgi</a>
          <button onclick="deleteEvent('${event.id}')">🗑 Sil</button>
        `;
        list.appendChild(li);
      }
    });
}

function openEvent(eventId) {
  document.getElementById("selected-event").textContent = eventId;
  document.getElementById("upload-section").style.display = "block";
  document.getElementById("stats-section").style.display = "block";
  document.getElementById("upload-form").dataset.event = eventId;

  fetchStats(eventId);
  fetchGallery(eventId);
}

function fetchStats(eventId) {
  fetch(`/stats/${eventId}`)
    .then(res => res.json())
    .then(data => {
      document.getElementById("total").textContent = data.total_faces;
      document.getElementById("tagged").textContent = data.tagged_photos;
      document.getElementById("gender").textContent = `${data.male}♂ / ${data.female}♀`;
    });
}

function fetchGallery(eventId) {
  fetch(`/photos/${eventId}`)
    .then(res => res.json())
    .then(data => {
      const grid = document.getElementById("gallery-grid");
      grid.innerHTML = "";
      for (let photo of data.photos) {
        const item = document.createElement("div");
        item.className = "gallery-item";
        item.innerHTML = `
          <img src="/uploads/${eventId}/${photo}" alt="${photo}" />
          <div>${photo}</div>
        `;
        grid.appendChild(item);
      }
    });
}

function deleteEvent(eventId) {
  if (!confirm("Bu etkinliği silmek istediğine emin misin?")) return;
  fetch(`/delete-event/${eventId}`, { method: "DELETE" })
    .then(() => {
      document.getElementById("upload-section").style.display = "none";
      document.getElementById("stats-section").style.display = "none";
      fetchEvents();
    });
}