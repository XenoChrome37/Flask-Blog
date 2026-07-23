document.addEventListener('DOMContentLoaded', function() {
    const hideFromSearch = document.getElementById('hideFromSearch');
    const hideFromSelect = document.getElementById('hiddenFrom');

    if (hideFromSearch && hideFromSelect) {
        hideFromSearch.addEventListener('input', function () {
            const searchTerm = this.value.toLowerCase().trim();
            const options = hideFromSelect.querySelectorAll('option');

            options.forEach(option => {
                const text = option.textContent.toLowerCase();
                if (text.includes(searchTerm) || option.value === "") {
                    option.style.display = "block";
                } else {
                    option.style.display = "none";
                }
            });
        });
    }
    const messageForm = document.getElementById('messageForm');
    const messageInput = messageForm.querySelector('textarea[name="message"]');
    const mentionList = document.getElementById('mentionList');

    // Allow Enter key to create a new line
    messageInput.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + "\n" + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 1;
        }
    });

    // Detect mentions
    messageInput.addEventListener('input', function() {
        const lastWord = this.value.split(" ").pop();
        if (lastWord.startsWith('@')) {
            mentionList.style.display = 'block';
            const searchTerm = lastWord.substring(1).toLowerCase();
            const mentionItems = document.querySelectorAll('.mentionItem');
            mentionItems.forEach(item => {
                const username = item.dataset.username.toLowerCase();
                if (username.includes(searchTerm)) {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
        } else {
            mentionList.style.display = 'none';
        }
    });

    // Handle mention selection
    mentionList.addEventListener('click', function(event) {
        if (event.target.classList.contains('mentionItem')) {
            const username = event.target.dataset.username;
            const lastWord = messageInput.value.split(" ").pop();
            messageInput.value = messageInput.value.replace(lastWord, "@" + username + " ");
            mentionList.style.display = 'none';
            messageInput.focus(); // Keep focus on the input
        }
    });

    // Optionally, submit the form with Ctrl + Enter
    messageForm.addEventListener('keypress', function(event) {
        if (event.key === 'Enter' && event.ctrlKey) {
            event.preventDefault();
            messageForm.submit();
        }
    });
});
