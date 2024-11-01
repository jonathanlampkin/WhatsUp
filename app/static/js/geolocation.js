let map, userMarker, directionsService, directionsRenderer;
const placesList = document.getElementById('places-list');

// Function to load Google Maps API dynamically with the fetched key
function loadGoogleMapsApi(apiKey) {
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places&callback=initMap`;
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
}

// Function to initialize the map and user location
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

// Display Ranked Places List and Place Markers
function displayNearbyPlaces(places) {
    placesList.innerHTML = '';  // Clear previous list
    places.forEach((place, index) => {
        const listItem = document.createElement('li');
        listItem.textContent = `${place.name} Rating: ${place.rating} Number of Ratings: ${place.user_ratings_total} Price Level: ${place.price_level} Open Now: ${place.open_now}`;
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


// Fetch the Google Maps API key, cache it in localStorage, and load the map
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

// Fetch the API key and initialize the map
fetchAndCacheGoogleMapsApiKey();