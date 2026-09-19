(function () {
    // 1. Theme Persistence
    const savedTheme = localStorage.getItem('jamia_lms_theme');
    if (savedTheme === 'dark') {
        document.documentElement.classList.add('dark-mode');
    }

    window.addEventListener('DOMContentLoaded', () => {
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
        }

        // 2. Build the Top-Right Slide Toggle Switch
        const toggleWrapper = document.createElement('div');
        toggleWrapper.id = 'theme-slide-wrapper';
        
        const toggleIconLight = document.createElement('i');
        toggleIconLight.className = 'fa-solid fa-sun toggle-icon-light';
        
        const toggleTrack = document.createElement('div');
        toggleTrack.id = 'theme-slide-track';
        const toggleThumb = document.createElement('div');
        toggleThumb.id = 'theme-slide-thumb';
        toggleTrack.appendChild(toggleThumb);
        
        const toggleIconDark = document.createElement('i');
        toggleIconDark.className = 'fa-solid fa-moon toggle-icon-dark';

        toggleWrapper.appendChild(toggleIconLight);
        toggleWrapper.appendChild(toggleTrack);
        toggleWrapper.appendChild(toggleIconDark);
        
        document.body.appendChild(toggleWrapper);

        toggleWrapper.addEventListener('click', () => {
            const isDark = document.body.classList.toggle('dark-mode');
            document.documentElement.classList.toggle('dark-mode', isDark);
            localStorage.setItem('jamia_lms_theme', isDark ? 'dark' : 'light');
        });

        // 3. Smart Reset Popup & Outside-Click Engine
        document.addEventListener('click', (event) => {
            // Check if user clicked a "RESET PW" trigger button
            const clickedBtn = event.target.closest('button, a, .btn');
            const isResetTrigger = clickedBtn && (
                (clickedBtn.textContent || '').toUpperCase().includes('RESET') ||
                (clickedBtn.textContent || '').toUpperCase().includes('PW')
            );

            // Find all reset popups and modal boxes on the page
            const allPopups = document.querySelectorAll(
                'div[id*="reset"], div[id*="password"], div[id*="pw"], form[id*="reset"], form[id*="password"], [class*="popup"], [class*="modal"]'
            );

            // A. If clicking a RESET PW button:
            if (isResetTrigger) {
                const clickedRow = clickedBtn.closest('tr');
                // Close any OTHER user's reset box so they don't overlap
                allPopups.forEach(box => {
                    if (box.tagName !== 'BUTTON' && box.tagName !== 'A') {
                        if (clickedRow && !clickedRow.contains(box)) {
                            box.style.display = 'none';
                            box.classList.remove('show', 'active', 'open');
                        }
                    }
                });
                // Allow this button to open its own box without closing it
                return;
            }

            // B. If clicking INSIDE an open popup (typing password, clicking input): do nothing
            const insidePopup = event.target.closest(
                'div[id*="reset"], div[id*="password"], div[id*="pw"], form[id*="reset"], form[id*="password"], [class*="popup"], [class*="modal"]'
            );
            if (insidePopup && insidePopup.tagName !== 'BUTTON' && insidePopup.tagName !== 'A') {
                return;
            }

            // C. If clicking OUTSIDE on the background: close all open popups
            allPopups.forEach(box => {
                if (box.tagName !== 'BUTTON' && box.tagName !== 'A') {
                    if (box.style.display && box.style.display !== 'none') {
                        box.style.display = 'none';
                    }
                    box.classList.remove('show', 'active', 'open');
                }
            });
        });
    });
})();