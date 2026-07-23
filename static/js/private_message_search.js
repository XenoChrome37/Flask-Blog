document.addEventListener('DOMContentLoaded', function() {
    const userSearchInput = document.getElementById('userSearchInput');
    const userList = document.getElementById('userList');
    const selectedReceiver = document.getElementById('selectedReceiver');
    const selectedUsername = document.getElementById('selectedUsername');
    const clearSearch = document.getElementById('clearSearch');
    let selectedUser = null;

    // Function to update the selected user display
    function updateSelectedUserDisplay() {
        if (selectedUser) {
            selectedUsername.textContent = "Selected: " + selectedUser;
        } else {
            selectedUsername.textContent = "";
        }
    }

    // Add click listeners to user items
    userList.addEventListener('click', function(event) {
        if (event.target.classList.contains('userItem')) {
            // Remove 'selected' class from previously selected item
            if (selectedUser) {
                const prevSelected = userList.querySelector('.userItem.selected');
                if (prevSelected) {
                    prevSelected.classList.remove('selected');
                }
            }

            // Set the selected user
            selectedUser = event.target.dataset.username;
            selectedReceiver.value = selectedUser;

            // Add 'selected' class to the clicked item
            event.target.classList.add('selected');

            // Update the display
            updateSelectedUserDisplay();
        }
    });

    // Add input listener to search input
    userSearchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const userItems = userList.querySelectorAll('.userItem');

        userItems.forEach(userItem => {
            const username = userItem.dataset.username.toLowerCase();
            if (username.includes(searchTerm)) {
                userItem.style.display = ''; // Use '' to reset display property
            } else {
                userItem.style.display = 'none';
            }
        });
    });

    // Ensure all users are visible on initial load
    const userItems = userList.querySelectorAll('.userItem');
    userItems.forEach(userItem => {
        userItem.style.display = ''; // Make sure all are visible initially
    });

    // Add click listener to clear search button
    clearSearch.addEventListener('click', function() {
        userSearchInput.value = ''; // Clear the search input
        const userItems = userList.querySelectorAll('.userItem');
        userItems.forEach(userItem => {
            userItem.style.display = ''; // Show all users
        });
    });
});