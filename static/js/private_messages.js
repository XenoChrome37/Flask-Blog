// Private Messages - Real-time polling and form submission
document.addEventListener('DOMContentLoaded', function() {
    // ============================================
    // PART 1: Real-time Message Polling
    // ============================================
    (function(){
        // Polling client for private messages
        const container = document.querySelector('.pm-container');
        if (!container) return;

        // Get current username from data attribute (set by template)
        const currentUsername = container.getAttribute('data-username') || '';

        // Compute current last_id from existing DOM nodes
        function getCurrentLastId() {
            const boxes = container.querySelectorAll('.pm-box');
            let max = -1;
            boxes.forEach(b => {
                const idAttr = b.getAttribute('data-id');
                if (!idAttr) return;
                const v = parseInt(idAttr, 10);
                if (!isNaN(v) && v > max) max = v;
            });
            return max;
        }

        let lastId = getCurrentLastId();
        const POLL_MS = 5000;

        function escapeHtml(s) {
            return String(s).replace(/[&<>"']/g, function(c) {
                return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"})[c];
            });
        }

        function buildPmNode(pm) {
            const box = document.createElement('div');
            box.className = 'pm-box ' + (pm.sender === currentUsername ? 'pm-sent' : 'pm-received');
            box.setAttribute('data-id', String(pm.id));

            const meta = document.createElement('div');
            meta.className = 'pm-meta';
            if (pm.sender === currentUsername) {
                meta.innerHTML = '<span class="pm-label">To:</span> <span class="pm-user">' + escapeHtml(pm.receiver || '') + '</span>';
            } else {
                meta.innerHTML = '<span class="pm-label">From:</span> <span class="pm-user">' + escapeHtml(pm.sender || '') + '</span>';
            }
            const body = document.createElement('div');
            body.className = 'pm-body';
            body.innerHTML = escapeHtml(pm.message || '').replace(/\n/g, '<br>');

            box.appendChild(meta);
            box.appendChild(body);

            if (pm.images && pm.images.length) {
                const imgsDiv = document.createElement('div');
                imgsDiv.className = 'pm-images';
                pm.images.forEach(img => {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'message-image';
                    const im = document.createElement('img');
                    im.src = '/uploads/' + encodeURIComponent(img);
                    im.alt = 'pm image';
                    wrapper.appendChild(im);
                    imgsDiv.appendChild(wrapper);
                });
                box.appendChild(imgsDiv);
            }

            return box;
        }

        async function fetchNew() {
            try {
                const url = '/api/private_messages' + (lastId >= 0 ? ('?since_id=' + encodeURIComponent(lastId)) : '');
                const res = await fetch(url, {credentials: 'same-origin'});
                if (!res.ok) return;
                const data = await res.json();
                if (!Array.isArray(data) || data.length === 0) return;
                // data is newest-first from API; reverse it so we can insert oldest first, 
                // which will result in newest-first order in the DOM
                data.reverse().forEach(pm => {
                    const node = buildPmNode(pm);
                    container.insertBefore(node, container.firstChild);
                });
                const ids = data.map(d => parseInt(d.id, 10)).filter(n => !isNaN(n));
                if (ids.length) {
                    const max = Math.max.apply(null, ids);
                    if (max > lastId) lastId = max;
                }
            } catch (e) {
                console.error('PM poll failed', e);
            }
        }

        // initial poll to pick up any messages that arrived after the server render
        setTimeout(fetchNew, 1000);
        setInterval(fetchNew, POLL_MS);
    })();

    // ============================================
    // PART 2: Form Submission Handler
    // ============================================
    // Form submission: support both traditional form POST and JSON API no-reload send
    const pmForm = document.getElementById('pmForm');
    const submitBtn = document.getElementById('submitBtn');
    const statusSpan = document.getElementById('submitStatus');

    if (!pmForm) return; // Exit if form doesn't exist

    pmForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Check if there are images - if yes, use form POST, otherwise use JSON API (always no-reload)
        const pmImages = document.getElementById('pm_images');

        if (!pmImages || pmImages.files.length === 0) {
            // Use JSON API for no-reload send (no images)
            const receiver = document.getElementById('selectedReceiver').value;
            const message = document.getElementById('pmMessage').value;

            try {
                if (statusSpan) statusSpan.textContent = 'Sending...';
                const res = await fetch('/api/private_messages', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        receiver: receiver,
                        message: message,
                        hide_from: []
                    })
                });

                if (res.status === 201) {
                    if (statusSpan) {
                        statusSpan.textContent = 'Sent! ✓';
                        statusSpan.style.color = 'green';
                    }
                    document.getElementById('pmMessage').value = '';
                    document.getElementById('selectedReceiver').value = '';
                    const selectedUsername = document.getElementById('selectedUsername');
                    if (selectedUsername) selectedUsername.textContent = '';
                    if (statusSpan) {
                        setTimeout(() => { 
                            statusSpan.textContent = ''; 
                            statusSpan.style.color = ''; 
                        }, 3000);
                    }
                } else {
                    const data = await res.json();
                    if (statusSpan) {
                        statusSpan.textContent = 'Error: ' + (data.error || 'Failed to send');
                        statusSpan.style.color = 'red';
                    }
                }
            } catch (err) {
                console.error('Send failed', err);
                if (statusSpan) {
                    statusSpan.textContent = 'Error: ' + err.message;
                    statusSpan.style.color = 'red';
                }
            }
        } else {
            // Use traditional form POST (for image uploads)
            pmForm.submit();
        }
    });
});

