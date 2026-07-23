// Advanced settings toggle
document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('toggleAdvancedSettings');
    const advancedSettings = document.getElementById('advancedSettings');
    
    if (toggleBtn && advancedSettings) {
        toggleBtn.addEventListener('click', function() {
            if (advancedSettings.style.display === 'none' || advancedSettings.style.display === '') {
                advancedSettings.style.display = 'block';
            } else {
                advancedSettings.style.display = 'none';
            }
        });
    }
});