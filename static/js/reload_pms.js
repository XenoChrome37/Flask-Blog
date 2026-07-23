(function(){
    // Polling client for private messages
    const container = document.querySelector('.pm-container');
    if (!container) return;

    // Compute current last_id from existing DOM nodes
    function getCurrentLastId() {
        const boxes = container.querySelectorAll('.pm-box');
        let max = -1;
        boxes.forEach(b => {
            const idAttr = b.getAttribute('data-id');
            if (!idAttr) return;
            // data-id may contain extra tokens if template rendered classes in same attr,
            // so extract the first number-like token
            const match = idAttr.match(/(\d+)/);
            if (match) {
                const v = parseInt(match[1], 10);
                if (!isNaN(v) && v > max) max = v;
            }
        });
        return max;
    }

    let lastId = getCurrentLastId();
    const POLL_MS = 5000;

    function escapeHtml(s) {
        return s.replace(/[&<>"']/g, function(c) {
            return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":"&#39;"})[c];
        });
    }

    function buildPmNode(pm) {
        const box = document.createElement('div');
        box.className = 'pm-box ' + (pm.sender === '{{ session.get("username") }}' ? 'pm-sent' : 'pm-received');
        box.setAttribute('data-id', String(pm.id));

        const meta = document.createElement('div');
        meta.className = 'pm-meta';
        if (pm.sender === '{{ session.get("username") }}') {
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
            // data is newest-first; insert each at top preserving newest-first
            data.forEach(pm => {
                // create node and prepend
                const node = buildPmNode(pm);
                container.insertBefore(node, container.firstChild);
            });
            // update lastId to the maximum id we received
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