/* -------------------------------------------------------------------------
   Case details page logic.
     * Sidebar case-list selection re-renders the main + chat panel
       in place (or navigates to /cases/<id> on a fresh request).
     * Tabs (Overview / Documents / Notes).
     * Chat with the per-case AI endpoint.
   ------------------------------------------------------------------------- */
(function(){
  'use strict';
  const { $, $$, escapeHTML, initialsOf, fmtDate, api, toast, user } = App;

  const caseDataEl = $('#case-data');
  const data = caseDataEl ? JSON.parse(caseDataEl.textContent) : { cases: [], active: null, chat_history: [], quick_queries: [] };
  const userInitials = (user && user.avatar_initials) || 'L';
  const chatBody = $('#chat-body');
  const docList = $('#doc-list');

  // ---------- Sidebar selection ---------- //
  const caseList = $('#case-list');
  if(caseList){
    caseList.addEventListener('click', e => {
      const item = e.target.closest('.case-item');
      if(!item) return;
      $$('.case-item', caseList).forEach(el => el.classList.remove('active'));
      item.classList.add('active');
      renderCase(item);
    });
  }

  function renderCase(el){
    const parseJson = (str) => {
      try { return JSON.parse(str || '[]'); }
      catch(e) { return []; }
    };

    const d = {
      id:           parseInt(el.dataset.id),
      idDisplay:    el.dataset.idDisplay,
      name:         el.dataset.name,
      type:      el.dataset.type,
      client:    el.dataset.client,
      status:    el.dataset.status,
      court:     el.dataset.court,
      hearing:   el.dataset.hearing,
      sections:     parseJson(el.dataset.sections),
      facts:        el.dataset.facts,
      lawyer:       el.dataset.lawyer,
      documents:    parseJson(el.dataset.documents),
      notes:        parseJson(el.dataset.notes)
    };
    data.active = d; // Update global state
    
    // Clear chat if dialog is open or hidden
    const msgs = chatBody.querySelectorAll('.msg');
    msgs.forEach(m => m.remove());
    setStatus(null);
    
    // If dialog is active, reload history immediately
    if($('#ai-dialog-overlay').classList.contains('active')){
      loadChatHistory(d.id);
    } else {
      // Just reset the button states
      if(analyzeWrap) analyzeWrap.style.display = 'flex';
      if(chatForm) chatForm.style.display = 'none';
    }

    $('#bc-case').textContent = d.name;
    $('#case-id').textContent     = `${d.idDisplay} · ${(d.type || '').toUpperCase()}`;
    $('#case-title').textContent  = d.name;
    $('#case-court').textContent  = d.court || '—';
    $('#case-hearing').textContent= fmtDate(d.hearing);
    $('#case-sections-head').innerHTML = `Sections: <b>${(d.sections || []).join(', ') || '—'}</b>`;

    $('#case-facts').textContent = d.facts || '';
    $('#lawyer-name').textContent     = d.lawyer || '—';
    $('#lawyer-chamber').textContent  = (d.lawyer && user && d.lawyer === user.name)
      ? (user.chamber || 'Senior Counsel')
      : 'Senior Counsel';
    $('#lawyer-initials').textContent = initialsOf(d.lawyer);

    // Section chips
    $('#case-sections').innerHTML = (d.sections || [])
      .map(s => `<span class="chip">${escapeHTML(s)}</span>`).join('');

    // Documents
    if(docList){
      $('#doc-count').textContent = `${d.documents.length} file${d.documents.length===1?'':'s'}`;
      docList.innerHTML = (d.documents || []).map(doc => `
      <div class="doc-item">
        <div class="doc-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6"/></svg>
        </div>
        <div class="doc-meta">
          <div class="n">${escapeHTML(doc.name || doc.original_name)}</div>
          <div class="d">Uploaded ${fmtDate(doc.date || doc.uploaded_at)} · ${escapeHTML((doc.type || doc.file_type || '').toUpperCase())}</div>
        </div>
        <button class="doc-del" title="Delete" data-id="${doc.id}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>
        </button>
      </div>`).join('') || '<p style="color:var(--muted);font-size:12.5px;">No documents yet.</p>';
    }

    // Notes
    const noteGrid = $('#note-grid');
    noteGrid.innerHTML = (d.notes || []).map(n => {
      if(n.type === 'voice' || n.note_type === 'voice'){
        const bars = Array.from({length:56}, (_,i)=>{
          const h = 6 + Math.abs(Math.sin(i*0.6 + (n.title||'').length)) * 16;
          return `<span style="height:${h.toFixed(1)}px"></span>`;
        }).join('');
        return `
          <div class="voice-note">
            <button class="play" title="Play">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 5l12 7-12 7V5z"/></svg>
            </button>
            <div class="vinfo">
              <div class="ttl">${escapeHTML(n.title)}</div>
              <div class="waveform">${bars}</div>
            </div>
            <div class="vdur">${escapeHTML(n.duration || '00:00')}</div>
          </div>`;
      }
      return `
        <div class="note">
          <div class="nt">
            <span class="ttl">${escapeHTML(n.title || 'Note')}</span>
            <span class="tag">Note</span>
          </div>
          <p>${escapeHTML(n.content)}</p>
        </div>`;
    }).join('') || '<p style="color:var(--muted);font-size:12.5px;">No notes for this case.</p>';
  }

  // ---------- Tabs ---------- //
  $$('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      $$('.tab').forEach(b => b.classList.toggle('active', b === btn));
      $$('.tab-pane').forEach(p => p.classList.toggle('active', p.dataset.pane === target));
    });
  });

  // ---------- Upload ---------- //
  const uploadZone = $('#upload-zone');
  const fileInput = $('#file-input');
  if(uploadZone && fileInput){
    uploadZone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', () => {
      const files = fileInput.files;
      if(!files.length) return;
      
      const caseId = data.active ? data.active.id : null;
      if(!caseId) return;

      const formData = new FormData();
      for(let f of files) formData.append('file', f);

      uploadZone.classList.add('uploading');
      const textEl = uploadZone.querySelector('.t');
      const originalText = textEl.innerHTML;
      textEl.innerHTML = 'Uploading...';

      fetch(`/cases/${caseId}/documents`, {
        method: 'POST',
        body: formData
      })
      .then(res => res.json())
      .then(res => {
        uploadZone.classList.remove('uploading');
        textEl.innerHTML = originalText;
        if(res.ok){
          // Refresh the case data to show new documents
          const activeItem = $('.case-item.active');
          if(activeItem){
            // Update the data-documents attribute with the new list
            activeItem.dataset.documents = JSON.stringify(res.documents);
            renderCase(activeItem);
          }
        } else {
          alert(res.error || 'Upload failed');
        }
      })
      .catch(err => {
        console.error('Upload error:', err);
        uploadZone.classList.remove('uploading');
        textEl.innerHTML = originalText;
        alert('Upload failed');
      });
      
      fileInput.value = ''; // Reset
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', e => {
      e.preventDefault();
      uploadZone.classList.add('drag');
    });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag'));
    uploadZone.addEventListener('drop', e => {
      e.preventDefault();
      uploadZone.classList.remove('drag');
      fileInput.files = e.dataTransfer.files;
      fileInput.dispatchEvent(new Event('change'));
    });
  }

  // ---------- Delete Document ---------- //
  if(docList){
    docList.addEventListener('click', e => {
      const btn = e.target.closest('.doc-del');
      if(!btn) return;
      
      const docId = btn.dataset.id;
      if(!docId || docId === 'undefined') {
        console.error('No document ID found on button');
        return;
      }
      
      if(!confirm('Are you sure you want to delete this document?')) return;

      btn.disabled = true;
      fetch(`/documents/${docId}`, { method: 'DELETE' })
        .then(res => {
          if (!res.ok) {
            return res.json().then(data => { throw new Error(data.error || 'Delete failed'); });
          }
          return res.json();
        })
        .then(res => {
          if(res.ok){
            const activeItem = $('.case-item.active');
            if(activeItem){
              activeItem.dataset.documents = JSON.stringify(res.documents || []);
              renderCase(activeItem);
            }
          }
        })
        .catch(err => {
          console.error('Delete error:', err);
          alert(err.message || 'Delete failed');
          btn.disabled = false;
        });
    });
  }

  // ---------- Chat ---------- //
  function appendMessage({role, content, judgments}){
    const wrap = document.createElement('div');
    wrap.className = `msg ${role}`;
    const av = document.createElement('div');
    av.className = 'av';
    av.textContent = role === 'lawyer' ? userInitials : 'AI';
    const bub = document.createElement('div');
    bub.className = 'bubble';

    if(role === 'lawyer'){
      bub.textContent = content;
    } else if(judgments && judgments.length){
      bub.innerHTML = `
        <div style="margin-bottom:6px;">${marked.parse(content || 'Related judgments found:')}</div>
        <div class="judgments-list">
          ${judgments.map(j => `
            <div class="judgment-card" data-docid="${j.doc_id}" data-title="${escapeHTML(j.title)}">
              <div class="jt">${escapeHTML(j.title)}</div>
              <div class="jm">
                <span>${escapeHTML(j.court || 'Indian Kanoon')}</span>
                <span>${escapeHTML(j.date || '')}</span>
              </div>
              ${j.snippet ? `<div class="js">${j.snippet}</div>` : ''}
            </div>`).join('')}
        </div>
      `;
    } else {
      bub.innerHTML = marked.parse(content || '');
    }

    wrap.appendChild(av);
    wrap.appendChild(bub);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function appendLoading(){
    const wrap = document.createElement('div');
    wrap.className = 'msg ai';
    wrap.id = 'loading-msg';
    wrap.innerHTML = `
      <div class="av">AI</div>
      <div class="bubble loading-bubble">
        <span class="ltxt">Searching database</span>
        <span class="dots"><span></span><span></span><span></span></span>
      </div>`;
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  const chatForm = $('#chat-form');
  const chatInput = $('#chat-input');
  const analyzeBtn = $('#analyze-btn');
  const analyzeWrap = $('#analyze-wrap');
  const chatStatusCenter = $('#chat-status-center');
  const aiTrigger = $('#ai-trigger');

  function loadChatHistory(caseId){
    if(!caseId) return;
    
    // Clear existing messages (except status center)
    const msgs = chatBody.querySelectorAll('.msg');
    msgs.forEach(m => m.remove());

    fetch(`/cases/${caseId}/chat`)
      .then(res => res.json())
      .then(data => {
        if(data.ok && data.messages){
          data.messages.forEach(m => {
            appendMessage({ role: m.role, content: m.content });
          });
          
          // If we have messages, hide Analyze button and show chat input
          if(data.messages.length > 0){
            if(analyzeWrap) analyzeWrap.style.display = 'none';
            if(chatForm) chatForm.style.display = 'flex';
          } else {
            // No messages — show Analyze button
            if(analyzeWrap) analyzeWrap.style.display = 'flex';
            if(chatForm) chatForm.style.display = 'none';
          }
        }
      })
      .catch(err => console.error('History load error:', err));
  }

  function setStatus(text, showDots = false) {
    if(!chatStatusCenter) return;
    if(!text) {
      chatStatusCenter.innerHTML = '';
      return;
    }
    chatStatusCenter.innerHTML = `
      <div class="status-msg">
        <div>${text}</div>
        ${showDots ? '<div class="dots"><span></span><span></span><span></span></div>' : ''}
      </div>
    `;
  }

  // ---------- Analyze Button Logic ---------- //
  if(analyzeBtn){
    analyzeBtn.addEventListener('click', () => {
      const caseId = data.active ? data.active.id : null;
      if(!caseId) return;

      analyzeBtn.disabled = true;
      analyzeBtn.style.opacity = '0.5';
      
      setStatus('Analyzing Case Facts...', true);

      fetch('/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ case_id: caseId })
      })
      .then(response => response.json())
      .then(data => {
          setStatus('Analysis Completed');

          // Switch UI
          if(analyzeWrap) analyzeWrap.style.display = 'none';
          if(chatForm) chatForm.style.display = 'flex';
          if(chatInput) chatInput.focus();
      })
      .catch(error => {
          console.error('Extract API error:', error);
          setStatus('Error analyzing case facts.');
          analyzeBtn.disabled = false;
          analyzeBtn.style.opacity = '1';
          setTimeout(() => setStatus(null), 3000);
      });
    });
  }

  function sendToAI(userText){
    setStatus(null); // Remove status once chat starts
    
    // Create AI message wrapper for streaming
    const wrap = document.createElement('div');
    wrap.className = 'msg ai';
    const av = document.createElement('div');
    av.className = 'av';
    av.textContent = 'AI';
    const bub = document.createElement('div');
    bub.className = 'bubble';
    bub.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';
    wrap.appendChild(av);
    wrap.appendChild(bub);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;

    const caseId = data.active ? data.active.id : null;
    
    fetch('/chat-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: caseId, message: userText })
    })
    .then(response => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        bub.innerHTML = ''; // Clear loading dots

        function read() {
            return reader.read().then(({ done, value }) => {
                if (done) {
                    bub.innerHTML = marked.parse(fullContent);
                    chatBody.scrollTop = chatBody.scrollHeight;
                    return;
                }
                const chunk = decoder.decode(value, { stream: true });
                fullContent += chunk;
                // Parse markdown during stream for real-time formatting
                bub.innerHTML = marked.parse(fullContent); 
                chatBody.scrollTop = chatBody.scrollHeight;
                return read();
            });
        }
        return read();
    })
    .catch(error => {
        console.error('Chat error:', error);
        bub.textContent = 'Error sending message.';
    });
  }
  const aiDialogOverlay = $('#ai-dialog-overlay');
  const closeAiDialog = $('#close-ai-dialog');
  const docPreviewOverlay = $('#doc-preview-overlay');
  const closePreview = $('#close-preview');
  const previewTitle = $('#preview-title');
  const previewContent = $('#preview-content');

  // ---------- Judgment Preview Logic ---------- //
  if(chatBody){
    chatBody.addEventListener('click', (e) => {
      const card = e.target.closest('.judgment-card');
      if(!card) return;

      const docId = card.dataset.docid;
      const title = card.dataset.title;
      
      previewTitle.textContent = title;
      previewContent.innerHTML = '<div style="display:flex;justify-content:center;padding:40px;"><span class="ltxt" style="color:#666">Loading judgment...</span></div>';
      docPreviewOverlay.classList.add('active');

      fetch('/get-doc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId })
      })
        .then(res => res.json())
        .then(data => {
          if(data.content){
            previewContent.innerHTML = data.content.doc || '';
          } else {
            previewContent.textContent = 'Error: Document content not found.';
          }
        })
        .catch(err => {
          console.error('Preview error:', err);
          previewContent.textContent = 'Failed to load document.';
        });
    });
  }

  if(closePreview){
    closePreview.addEventListener('click', () => {
      docPreviewOverlay.classList.remove('active');
    });
    docPreviewOverlay.addEventListener('click', (e) => {
      if(e.target === docPreviewOverlay) docPreviewOverlay.classList.remove('active');
    });
  }

  // ---------- AI Dialog Logic ---------- //
  if(aiTrigger && aiDialogOverlay){
    aiTrigger.addEventListener('click', (e) => {
      // Don't open if we were just dragging
      if(aiTrigger.dataset.dragging === 'true') return;
      
      const caseId = data.active ? data.active.id : null;
      loadChatHistory(caseId);

      aiDialogOverlay.classList.add('active');
      chatBody.scrollTop = chatBody.scrollHeight;
    });

    closeAiDialog && closeAiDialog.addEventListener('click', () => {
      aiDialogOverlay.classList.remove('active');
    });

    aiDialogOverlay.addEventListener('click', (e) => {
      if(e.target === aiDialogOverlay) {
        aiDialogOverlay.classList.remove('active');
      }
    });

    // Draggable logic
    let isDragging = false;
    let startX, startY, initialX, initialY;

    aiTrigger.addEventListener('mousedown', (e) => {
      isDragging = false;
      aiTrigger.dataset.dragging = 'false';
      startX = e.clientX;
      startY = e.clientY;
      const rect = aiTrigger.getBoundingClientRect();
      initialX = rect.left;
      initialY = rect.top;

      const onMouseMove = (e) => {
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        if(Math.abs(dx) > 5 || Math.abs(dy) > 5) {
          isDragging = true;
          aiTrigger.dataset.dragging = 'true';
        }
        if(isDragging) {
          aiTrigger.style.left = (initialX + dx) + 'px';
          aiTrigger.style.top = (initialY + dy) + 'px';
          aiTrigger.style.bottom = 'auto';
          aiTrigger.style.right = 'auto';
        }
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });
  }

  if(chatForm){
    chatForm.addEventListener('submit', e => {
      e.preventDefault();
      const txt = chatInput.value.trim();
      if(!txt) return;
      appendMessage({ role:'lawyer', content: txt });
      chatInput.value = '';
      sendToAI(txt);
    });
  }
  $$('.qq').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.q;
      chatInput.value = q;
      chatForm && chatForm.requestSubmit();
    });
  });

  document.addEventListener('DOMContentLoaded', () => {
    const active = (caseList && $('.case-item.active')) || (caseList && $('.case-item'));
    if(active){
      active.classList.add('active');
      renderCase(active);
    }

    // Auto-scroll chat to the bottom on load.
    if(chatBody) chatBody.scrollTop = chatBody.scrollHeight;
  });
})();
