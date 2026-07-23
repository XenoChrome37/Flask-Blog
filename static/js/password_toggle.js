document.addEventListener('DOMContentLoaded', function() {
    var togglePasswordButtons = document.querySelectorAll('.toggle-password');

    togglePasswordButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var inputId = this.previousElementSibling.id; // Get the input ID from the previous sibling
            togglePassword(inputId, this);
        });
    });

    function togglePassword(inputId, button) {
        console.log("togglePassword called for inputId: " + inputId);
        var passwordInput = document.getElementById(inputId);
        var icon = document.getElementById('togglePassword');

        if (passwordInput.type === "password") {
            passwordInput.type = "text";
            icon.classList.remove("fa-eye");
            icon.classList.add("fa-eye-slash");
        } else {
            passwordInput.type = "password";
            icon.classList.remove("fa-eye-slash");
            icon.classList.add("fa-eye");
        }
    }
});