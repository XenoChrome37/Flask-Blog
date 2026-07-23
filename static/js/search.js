console.log("search.js loaded");
document.addEventListener('DOMContentLoaded', function() {
    const searchBtn = document.getElementById('searchBtn');
    const searchBox = document.getElementById('searchBox');
    const searchInput = document.getElementById('searchInput');
    let searchActive = false; // Track if search is active

    console.log("Search script loaded");

    // Toggle search box and filtering when clicking the search button
    searchBtn.addEventListener('click', function() {
        console.log("Search button clicked");
        searchActive = !searchActive; // Toggle the search state

        if (searchActive) {
            searchBox.style.display = 'block';
            searchInput.focus();
            applyFilter(); // Apply the filter if search is active
        } else {
            searchBox.style.display = 'none';
            searchInput.value = ''; // Clear the search input
            removeFilter(); // Remove the filter if search is not active
        }
    });

    // Function to apply the filter
    function applyFilter() {
        const searchTerm = searchInput.value.toLowerCase();
        const messages = document.querySelectorAll('.message');

        console.log("Applying filter with term:", searchTerm);

        messages.forEach(message => {
            const messageText = message.textContent.toLowerCase();
            console.log("Message text:", messageText);
            if (messageText.includes(searchTerm)) {
                message.classList.remove('hidden');
            } else {
                message.classList.add('hidden');
            }
        });
    }

    // Function to remove the filter
    function removeFilter() {
        const messages = document.querySelectorAll('.message');
        messages.forEach(message => {
            message.classList.remove('hidden'); // Show all messages
        });
        console.log("Filter removed");
    }

    // Search functionality (live filtering)
    searchInput.addEventListener('input', function() {
        if (searchActive) {
            applyFilter(); // Apply the filter as the user types
        }
    });

    // Close search box when clicking outside
    document.addEventListener('click', function(event) {
        if (!searchBtn.contains(event.target) && !searchBox.contains(event.target)) {
            searchBox.style.display = 'none';
            searchActive = false; // Deactivate search
            removeFilter(); // Show all messages
        }
    });
}); 