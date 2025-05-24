// Dark Mode Functionality for AyushHealthBot
document.addEventListener('DOMContentLoaded', function() {
    // Add dark mode toggle button
    addDarkModeToggle();
    
    // Load user preference for dark mode
    loadThemePreference();
});

// Add dark mode toggle button
function addDarkModeToggle() {
    const toggleBtn = document.createElement('button');
    toggleBtn.setAttribute('class', 'dark-mode-toggle');
    toggleBtn.setAttribute('id', 'darkModeToggle');
    toggleBtn.setAttribute('aria-label', 'Toggle dark mode');
    toggleBtn.innerHTML = '<i class="fas fa-moon"></i>';
    document.body.appendChild(toggleBtn);
    
    // Add event listener for dark mode toggle
    toggleBtn.addEventListener('click', function() {
        toggleDarkMode();
    });
}

// Toggle between dark and light mode
function toggleDarkMode() {
    if (isDarkMode()) {
        document.documentElement.setAttribute('data-theme', 'light');
        localStorage.setItem('theme', 'light');
        document.getElementById('darkModeToggle').innerHTML = '<i class="fas fa-moon"></i>';
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
        document.getElementById('darkModeToggle').innerHTML = '<i class="fas fa-sun"></i>';
    }
}

// Check if dark mode is currently active
function isDarkMode() {
    return document.documentElement.getAttribute('data-theme') === 'dark';
}

// Load theme preference from localStorage
function loadThemePreference() {
    const theme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
    
    // Wait for DOM to be fully loaded 
    setTimeout(() => {
        const darkModeToggle = document.getElementById('darkModeToggle');
        if (darkModeToggle) {
            if (theme === 'dark') {
                darkModeToggle.innerHTML = '<i class="fas fa-sun"></i>';
            } else {
                darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
            }
        }
    }, 100);
} 