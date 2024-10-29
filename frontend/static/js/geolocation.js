// frontend/static/js/geolocation.js

let map, userMarker, directionsService, directionsRenderer;
const placesList = document.getElementById('places-list');

// Initialize Map and User Location
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

            directionsService = new google.maps.DirectionsService();
            directionsRenderer = new google.maps.DirectionsRenderer();
            directionsRenderer.setMap(map);

            // Fetch nearby places and display them
            fetchNearbyPlaces(userLocation.lat, userLocation.lng);
        }, error => {
            console.error('Geolocation error:', error);
            alert('Geolocation is required to use this feature.');
        });
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}

// Fetch Nearby Places from Backend
function fetchNearbyPlaces(latitude, longitude) {
    fetch('/get-nearby-places', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ latitude: latitude, longitude: longitude })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            console.error("Error fetching nearby places:", data.error);
        } else {
            displayNearbyPlaces(data.places);
        }
    })
    .catch(error => console.error("Error fetching nearby places:", error));
}

// Display Ranked Places List and Place Markers
function displayNearbyPlaces(places) {
    placesList.innerHTML = '';  // Clear previous list
    places.forEach((place, index) => {
        const listItem = document.createElement('li');
        listItem.textContent = `${place.name} - ${place.vicinity} (Rating: ${place.rating})`;
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

// Highlight Place and Show Directions
function highlightPlace(place) {
    directionsService.route({
        origin: userMarker.getPosition(),
        destination: { lat: place.latitude, lng: place.longitude },
        travelMode: google.maps.TravelMode.DRIVING,
    }, (response, status) => {
        if (status === google.maps.DirectionsStatus.OK) {
            directionsRenderer.setDirections(response);
        } else {
            alert("Directions request failed due to " + status);
        }
    });
}

// Load Google Maps API directly with your proxy setup (assuming the server-side proxy is ready)
initMap();
