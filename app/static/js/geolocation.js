let map, userMarker, directionsService, directionsRenderer;
const placesList = document.getElementById('places-list');

// Load Google Maps API dynamically with the fetched key
function loadGoogleMapsApi(apiKey) {
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&callback=initMap`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
}

// Initialize the map and user location
function initMap() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(position => {
            const userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude
            };

            // Initialize the map centered at user location
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

            // Fetch and display nearby places
            fetchNearbyPlaces(userLocation.lat, userLocation.lng);
        }, error => {
            console.error('Geolocation error:', error);
            alert('Geolocation is required to use this feature.');
        });
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}

// Fetch nearby places from the backend
function fetchNearbyPlaces(latitude, longitude) {
    fetch('/process-coordinates', {
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

// Display ranked places list and add place markers
function displayNearbyPlaces(places) {
    placesList.innerHTML = '';  // Clear previous list
    places.forEach(place => {
        // Create a card for each place with structured content
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

// Highlight selected place on map and show directions
function highlightPlace(place) {
    directionsService.route(
        {
            origin: userMarker.getPosition(),
            destination: { lat: place.latitude, lng: place.longitude },
            travelMode: 'WALKING'
        },
        (result, status) => {
            if (status === 'OK') {
                directionsRenderer.setDirections(result);
            } else {
                console.error('Directions request failed due to ' + status);
            }
        }
    );
}

// Fetch Google Maps API key and load the map
function fetchAndCacheGoogleMapsApiKey() {
    const cachedApiKey = localStorage.getItem("google_maps_api_key");

    if (cachedApiKey) {
        console.log("Using cached Google Maps API key.");
        loadGoogleMapsApi(cachedApiKey);
    } else {
        console.log("Fetching Google Maps API key from server.");
        fetch('/get-google-maps-key')
            .then(response => response.json())
            .then(data => {
                if (data.key) {
                    localStorage.setItem("google_maps_api_key", data.key);
                    loadGoogleMapsApi(data.key);
                } else {
                    console.error("API key not found in response.");
                }
            })
            .catch(error => console.error("Error fetching Google Maps API key:", error));
    }
}

// Start by fetching the API key and initializing the map
fetchAndCacheGoogleMapsApiKey();
