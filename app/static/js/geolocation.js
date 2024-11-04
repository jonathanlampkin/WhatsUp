let map, userMarker;
const placesList = document.getElementById('places-list');

function loadGoogleMapsApi(apiKey) {
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&callback=initMap`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
}

function initMap() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(position => {
            const userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };

            map = new google.maps.Map(document.getElementById("map"), {
                center: userLocation,
                zoom: 15,
            });

            userMarker = new google.maps.Marker({
                position: userLocation,
                map,
                title: "Your Location",
            });

            fetchNearbyPlaces(userLocation.lat, userLocation.lng);
        }, error => {
            console.error('Geolocation error:', error);
            alert('Geolocation is required to use this feature.');
        });
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}

function fetchNearbyPlaces(latitude, longitude) {
    fetch('/process-coordinates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: latitude, longitude: longitude })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "processing") {
            console.log("Processing request. Updates will be received via WebSocket.");
        } else if (data.error) {
            console.error("Error fetching nearby places:", data.error);
        }
    })
    .catch(error => console.error("Error fetching nearby places:", error));
}

document.addEventListener('DOMContentLoaded', () => {
    const socket = new WebSocket(`wss://${window.location.host}/ws`);

    socket.onopen = () => {
        console.log("WebSocket connection established.");
    };

    socket.onerror = (error) => {
        console.error("WebSocket connection error:", error);
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log("Received data from WebSocket:", data);

            const { latitude, longitude, places } = data;
            if (places && places.length > 0) {
                displayNearbyPlaces(places);
            } else {
                console.warn("No places received or places array is empty.");
            }
        } catch (error) {
            console.error("Error parsing WebSocket message:", error);
        }
    };

    socket.onclose = () => {
        console.log("WebSocket connection closed.");
    };
});

function displayNearbyPlaces(places) {
    placesList.innerHTML = '';
    places.forEach((place) => {
        const listItem = document.createElement('div');
        listItem.className = 'place-item';

        listItem.innerHTML = `
            <h3>${place.name}</h3>
            <p><strong>Rating:</strong> ${place.rating} ⭐ (${place.user_ratings_total} reviews)</p>
            <p><strong>Price Level:</strong> ${place.price_level || "N/A"}</p>
            <p><strong>Open Now:</strong> ${place.open_now ? "Yes" : "No"}</p>
        `;
        listItem.onclick = () => highlightPlace(place);
        placesList.appendChild(listItem);

        const marker = new google.maps.Marker({
            position: { lat: place.latitude, lng: place.longitude },
            map,
            title: place.name,
        });

        marker.addListener('click', () => highlightPlace(place));
    });
}

function highlightPlace(place) {
    map.panTo({ lat: place.latitude, lng: place.longitude });
    map.setZoom(16);
}

function fetchAndCacheGoogleMapsApiKey() {
    const cachedApiKey = localStorage.getItem("google_maps_api_key");

    if (cachedApiKey) {
        loadGoogleMapsApi(cachedApiKey);
    } else {
        fetch('/get-google-maps-key')
            .then(response => response.json())
            .then(data => {
                if (data.key) {
                    localStorage.setItem("google_maps_api_key", data.key);
                    loadGoogleMapsApi(data.key);
                }
            })
            .catch(error => console.error("Error fetching Google Maps API key:", error));
    }
}

fetchAndCacheGoogleMapsApiKey();
