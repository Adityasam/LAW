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
  const noteGrid = $('#note-grid');

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
      facts:        el.getAttribute('data-facts'),
      ai_summary:   el.getAttribute('data-ai_summary'),
      analysis_status: el.getAttribute('data-analysis_status') || 'pending',
      documents:    parseJson(el.dataset.documents),
      notes:        parseJson(el.dataset.notes),
      hearings:     parseJson(el.dataset.hearings || '[]')
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
      updateChatUI();
    }

    if($('#bc-case')) $('#bc-case').textContent = d.name;
    if($('#case-id')) $('#case-id').textContent     = `${d.idDisplay} · ${(d.type || '').toUpperCase()}`;
    if($('#case-title')) $('#case-title').textContent  = d.name;
    if($('#case-court')) $('#case-court').textContent  = d.court || '—';
    if($('#case-hearing')) $('#case-hearing').textContent= fmtDate(d.hearing);
    if($('#case-sections-head')) $('#case-sections-head').innerHTML = `Sections: <b>${(d.sections || []).join(', ') || '—'}</b>`;

    if($('#case-ai-summary')){
      if(d.ai_summary){
        $('#case-ai-summary').innerHTML = marked.parse(d.ai_summary);
        $('#ai-summary-card').style.display = 'block';
      } else {
        $('#ai-summary-card').style.display = 'none';
      }
    }

    if($('#case-facts')) $('#case-facts').textContent = d.facts || '';

    // Section chips
    if($('#case-sections')) $('#case-sections').innerHTML = (d.sections || [])
      .map(s => `<span class="chip">${escapeHTML(s)}</span>`).join('');

    // Documents
    if(docList){
      if($('#doc-count')) $('#doc-count').textContent = `${d.documents.length} file${d.documents.length===1?'':'s'}`;
      docList.innerHTML = (d.documents || []).map(doc => `
      <div class="doc-item">
        <div class="doc-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6"/></svg>
        </div>
        <div class="doc-meta">
          <div class="n">${escapeHTML(doc.name || doc.original_name)}</div>
          <div class="d">
            ${doc.status === 'processing' 
              ? '<span style="color:var(--gold)">AI Extracting...</span>' 
              : `Uploaded ${fmtDate(doc.date || doc.uploaded_at)} · ${escapeHTML((doc.type || doc.file_type || '').toUpperCase())}`}
          </div>
        </div>
        <div class="doc-actions">
          ${doc.summary ? `
          <button class="btn-icon view-doc-summary" title="View Summary" data-summary="${escapeHTML(doc.summary)}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 014 4v14a4 4 0 00-4-4H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a4 4 0 014-4h6z"/></svg>
          </button>` : ''}
          <a href="/uploads/${doc.filename}" target="_blank" class="btn-icon" title="Download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
          </a>
          <button class="doc-del" title="Delete" data-id="${doc.id}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>
          </button>
        </div>
      </div>`).join('') || '<p style="color:var(--muted);font-size:12.5px;">No documents yet.</p>';
    }

    // Notes
    if(noteGrid){
      noteGrid.innerHTML = (d.notes || []).map(n => {
        if(n.type === 'voice' || n.note_type === 'voice'){
          const bars = Array.from({length:56}, (_,i)=>{
            const h = 6 + Math.abs(Math.sin(i*0.6 + (n.title||'').length)) * 16;
            return `<span style="height:${h.toFixed(1)}px"></span>`;
          }).join('');
          return `
            <div class="voice-note" data-id="${n.id}">
              <button class="play" title="Play">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 5l12 7-12 7V5z"/></svg>
              </button>
              <div class="vinfo">
                <div class="ttl">${escapeHTML(n.title)}</div>
                <div class="waveform">${bars}</div>
              </div>
              <div class="vdur">${escapeHTML(n.duration || '00:00')}</div>
              <button class="note-del" title="Delete Note">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>
              </button>
            </div>`;
        }
        return `
          <div class="note" data-id="${n.id}">
            <div class="nt">
              <span class="ttl">${escapeHTML(n.title || 'Note')}</span>
              <div style="display: flex; align-items: center;">
                <span class="tag">Note</span>
                <button class="note-del" title="Delete Note">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>
                </button>
              </div>
            </div>
            <p>${escapeHTML(n.content)}</p>
          </div>`;
      }).join('') || '<p style="color:var(--muted);font-size:12.5px;">No notes for this case.</p>';
    }

    // Hearings
    const hearingListEl = $('#hearing-list');
    if(hearingListEl){
      hearingListEl.innerHTML = (d.hearings || []).map(h => `
        <div class="card hearing-item" data-id="${h.id}">
          <div class="ch" style="margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div style="padding: 8px; background: var(--gold-soft); color: var(--gold); border-radius: 6px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              </div>
              <h3 style="margin:0;" class="h-date-text">${fmtDate(h.date)}</h3>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="sub">Hearing Record</span>
              <button class="btn-icon edit-hearing" title="Edit Hearing">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 14px; height: 14px;"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              </button>
            </div>
          </div>
          <div class="hearing-content" style="font-size: 13.5px; color: var(--muted-2); line-height: 1.6; white-space: pre-wrap;">${escapeHTML(h.notes || '')}</div>
          
          <div class="edit-hearing-form" style="display: none; flex-direction: column; gap: 12px; margin-top: 10px; padding-top: 15px; border-top: 1px solid var(--border-2);">
            <div class="form-group">
              <label style="display:block; margin-bottom:6px; font-size:12px; color:var(--muted);">Hearing Date</label>
              <input type="date" class="edit-h-date" value="${h.date}" required style="width:100%; background: var(--bg); border: 1px solid var(--border-2); padding: 8px; border-radius: 6px; color: var(--text);">
            </div>
            <div class="form-group">
              <label style="display:block; margin-bottom:6px; font-size:12px; color:var(--muted);">Notes & Orders</label>
              <textarea class="edit-h-notes" placeholder="Update notes..." style="width:100%; background: var(--bg); border: 1px solid var(--border-2); padding: 8px; border-radius: 6px; color: var(--text); min-height: 80px; resize: vertical;">${escapeHTML(h.notes || '')}</textarea>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 8px;">
              <button class="btn btn-secondary cancel-edit-hearing" style="padding: 6px 15px; font-size: 12px;">Cancel</button>
              <button class="btn btn-primary save-edit-hearing" style="padding: 6px 15px; font-size: 12px;">Update Record</button>
            </div>
          </div>
        </div>
      `).join('') || '<p style="color:var(--muted);font-size:12.5px;">No hearings recorded yet.</p>';
    }

    // Start polling if there are processing documents or AI summary is missing
    if(d.documents.some(doc => doc.status === 'processing') || (d.facts && !d.ai_summary)){
      startPolling(d.id);
    }
  }

  let pollInterval = null;
  function startPolling(caseId){
    if(pollInterval) return;
    pollInterval = setInterval(() => {
      fetch(`/cases/${caseId}`)
        .then(res => res.json())
        .then(res => {
          if(res.ok && res.case){
            const activeItem = $('.case-item.active');
            if(activeItem && parseInt(activeItem.dataset.id) === caseId){
              activeItem.setAttribute('data-documents', JSON.stringify(res.case.documents || []));
              // Update other fields as well for the UI to refresh summary
              activeItem.setAttribute('data-ai_summary', res.case.ai_summary || '');
              activeItem.setAttribute('data-analysis_status', res.case.analysis_status || 'pending');
              activeItem.setAttribute('data-sections', JSON.stringify(res.case.sections || []));
              
              renderCase(activeItem);
              
              // Stop polling if all done
              const docsDone = !res.case.documents.some(doc => doc.status === 'processing');
              const summaryDone = !!res.case.ai_summary;
              
              if(docsDone && summaryDone){
                clearInterval(pollInterval);
                pollInterval = null;
              }
            }
          }
        })
        .catch(() => {
          clearInterval(pollInterval);
          pollInterval = null;
        });
    }, 10000);
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

  // ---------- Add Note ---------- //
  const addNoteForm = $('#add-note-form');
  if(addNoteForm){
    addNoteForm.addEventListener('submit', async e => {
      e.preventDefault();
      const title = $('#note-title').value;
      const content = $('#note-content').value;
      if(!content) return;

      const btn = addNoteForm.querySelector('button[type="submit"]');
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = 'Saving...';

      try {
        console.log('Adding note to case:', data.active.id);
        const res = await api.post(`/cases/${data.active.id}/notes`, { title, content });
        
        if(res.ok){
          // Update sidebar data so it persists in memory
          const activeItem = $('.case-item.active');
          if(activeItem){
            const notes = JSON.parse(activeItem.dataset.notes || '[]');
            notes.push(res.note);
            activeItem.dataset.notes = JSON.stringify(notes);
            renderCase(activeItem);
          }
          $('#note-title').value = '';
          $('#note-content').value = '';
          toast('Note added successfully', 'success');
        } else {
          throw new Error(res.error || 'Failed to save note');
        }
      } catch (err) {
        console.error('Note add error:', err);
        alert(err.message || 'Failed to add note');
      } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });
  }

  // ---------- Add Hearing ---------- //
  const addHearingForm = $('#add-hearing-form');
  const hearingListContainer = $('#hearing-list');

  if(hearingListContainer){
    hearingListContainer.addEventListener('click', async e => {
      // Toggle Edit Mode
      if(e.target.closest('.edit-hearing')){
        const card = e.target.closest('.hearing-item');
        card.querySelector('.hearing-content').style.display = 'none';
        card.querySelector('.edit-hearing-form').style.display = 'flex';
        card.querySelector('.edit-hearing').style.display = 'none';
        return;
      }

      // Cancel Edit
      if(e.target.closest('.cancel-edit-hearing')){
        const card = e.target.closest('.hearing-item');
        card.querySelector('.hearing-content').style.display = 'block';
        card.querySelector('.edit-hearing-form').style.display = 'none';
        card.querySelector('.edit-hearing').style.display = 'flex';
        return;
      }

      // Save Edit
      if(e.target.closest('.save-edit-hearing')){
        const card = e.target.closest('.hearing-item');
        const hId = card.dataset.id;
        const date = card.querySelector('.edit-h-date').value;
        const notes = card.querySelector('.edit-h-notes').value;
        
        const btn = e.target.closest('.save-edit-hearing');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = 'Updating...';

        try {
          const res = await api.put(`/hearings/${hId}`, { date, notes });
          if(res.ok){
            const activeItem = $('.case-item.active');
            if(activeItem){
              let hearings = JSON.parse(activeItem.dataset.hearings || '[]');
              hearings = hearings.map(h => h.id == hId ? res.hearing : h);
              activeItem.dataset.hearings = JSON.stringify(hearings);
              renderCase(activeItem);
            }
            toast('Hearing updated', 'success');
          } else {
            throw new Error(res.error || 'Update failed');
          }
        } catch (err) {
          console.error('Hearing update error:', err);
          alert(err.message || 'Failed to update hearing');
        } finally {
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      }
    });
  }

  if(addHearingForm){
    addHearingForm.addEventListener('submit', async e => {
      e.preventDefault();
      const date = $('#h-date').value;
      const notes = $('#h-notes').value;
      if(!date) return;

      const btn = addHearingForm.querySelector('button[type="submit"]');
      const originalText = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = 'Saving...';

      try {
        const res = await api.post(`/cases/${data.active.id}/hearings`, { date, notes });
        if(res.ok){
          const activeItem = $('.case-item.active');
          if(activeItem){
            const hearings = JSON.parse(activeItem.dataset.hearings || '[]');
            hearings.unshift(res.hearing); // Add to top
            activeItem.dataset.hearings = JSON.stringify(hearings);
            
            // Also update the header hearing date if it's the latest/relevant
            activeItem.dataset.hearing = res.hearing.date;
            
            renderCase(activeItem);
          }
          $('#h-date').value = '';
          $('#h-notes').value = '';
          toast('Hearing saved successfully', 'success');
        } else {
          throw new Error(res.error || 'Failed to save hearing');
        }
      } catch (err) {
        console.error('Hearing add error:', err);
        alert(err.message || 'Failed to add hearing');
      } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
      }
    });
  }

  // ---------- Delete Note ---------- //
  if(noteGrid){
    noteGrid.addEventListener('click', async e => {
      const btn = e.target.closest('.note-del');
      if(!btn) return;

      const noteEl = btn.closest('.note, .voice-note');
      const noteId = noteEl.dataset.id;
      if(!noteId) return;

      if(!confirm('Are you sure you want to delete this note?')) return;

      btn.disabled = true;
      try {
        const res = await api.del(`/notes/${noteId}`);
        if(res.ok){
          // Update memory data
          const activeItem = $('.case-item.active');
          if(activeItem){
            let notes = JSON.parse(activeItem.dataset.notes || '[]');
            notes = notes.filter(n => n.id != noteId);
            activeItem.dataset.notes = JSON.stringify(notes);
            renderCase(activeItem);
          }
          toast('Note deleted', 'info');
        } else {
          throw new Error(res.error || 'Failed to delete note');
        }
      } catch (err) {
        console.error('Note delete error:', err);
        alert(err.message);
        btn.disabled = false;
      }
    });
  }

  // ---------- Delete Document ---------- //
  if(docList){
    docList.addEventListener('click', e => {
      const btn = e.target.closest('.doc-del');
      if(btn){
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
        return;
      }

      // Summary button
      const summaryBtn = e.target.closest('.view-doc-summary');
      if(summaryBtn){
        const summary = summaryBtn.dataset.summary;
        const row = summaryBtn.closest('.doc-item');
        const docName = row.querySelector('.doc-meta .n').textContent;
        
        const summaryModal = $('#summary-modal');
        const summaryText = $('#summary-text');
        const summaryDocName = $('#summary-doc-name');
        
        if(summaryModal && summaryText && summaryDocName){
          summaryText.innerHTML = marked.parse(summary);
          summaryDocName.textContent = docName;
          summaryModal.classList.add('active');
        }
      }
    });
  }

  const closeSummary = $('#close-summary');
  if(closeSummary){
    closeSummary.addEventListener('click', () => {
      $('#summary-modal').classList.remove('active');
    });
  }

  // ---------- Chat ---------- //
  function appendMessage({role, content, judgments}){
    const wrap = document.createElement('div');
    wrap.className = `msg ${role}`;
    const av = document.createElement('div');
    av.className = 'av';
    av.textContent = (role === 'user' || role === 'lawyer') ? userInitials : 'AI';
    const bub = document.createElement('div');
    bub.className = 'bubble';

    if(role === 'user' || role === 'lawyer'){
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
              ${j.snippet ? `<div class="js">${marked.parse(j.snippet)}</div>` : ''}
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

  function updateChatUI() {
    const status = (data.active.analysis_status || 'pending').toLowerCase();
    
    if (status === 'completed') {
      if (analyzeWrap) analyzeWrap.style.display = 'none';
      if (chatForm) chatForm.style.display = 'flex';
      setStatus(null);
    } else if (status === 'processing') {
      if (analyzeWrap) analyzeWrap.style.display = 'none';
      if (chatForm) chatForm.style.display = 'none';
      setStatus('LegalMind is analyzing your case...', true);
    } else {
      // pending or failed
      if (analyzeWrap) analyzeWrap.style.display = 'flex';
      if (chatForm) chatForm.style.display = 'none';
      setStatus(null);
    }
  }

  function loadChatHistory(caseId){
     if(!caseId) return;
     
     // Clear existing messages (except status center)
     const msgs = chatBody.querySelectorAll('.msg');
     msgs.forEach(m => m.remove());

     fetch(`/cases/${caseId}/chat`)
       .then(res => res.json())
       .then(data => {
         if(data.ok){
           if(data.messages){
             data.messages.forEach(m => {
               appendMessage({ role: m.role, content: m.content });
             });
           }
           
           // Use the status from the server to update UI
           updateChatUI();
           
           if(data.analysis_status === 'processing'){
             // Poll for status update if still processing
             setTimeout(() => loadChatHistory(caseId), 5000);
           }
         }
       })
       .catch(err => console.error('History load error:', err));
   }

  // ---------- Hearing Date Inline Edit ---------- //
  const hearingDateText = $('#case-hearing');
  const hearingDateInput = $('#case-hearing-input');

  if(hearingDateText && hearingDateInput){
    hearingDateText.addEventListener('click', () => {
      hearingDateText.style.display = 'none';
      hearingDateInput.style.display = 'inline-block';
      
      // Values are often in DD MMM YYYY or YYYY-MM-DD
      // Try to set current date correctly for the input
      const current = hearingDateText.textContent.trim();
      if(current && current !== '—'){
        // If it looks like ISO, use it, else default empty
        if(/^\d{4}-\d{2}-\d{2}$/.test(current)) hearingDateInput.value = current;
      }
      hearingDateInput.focus();
    });

    hearingDateInput.addEventListener('blur', saveHearingDate);
    hearingDateInput.addEventListener('keydown', (e) => {
      if(e.key === 'Enter') saveHearingDate();
      if(e.key === 'Escape') {
        hearingDateInput.style.display = 'none';
        hearingDateText.style.display = 'inline-block';
      }
    });

    async function saveHearingDate(){
      const newDate = hearingDateInput.value;
      if(!newDate) {
        hearingDateInput.style.display = 'none';
        hearingDateText.style.display = 'inline-block';
        return;
      }

      const originalText = hearingDateText.textContent;
      hearingDateText.textContent = 'Updating...';
      hearingDateInput.style.display = 'none';
      hearingDateText.style.display = 'inline-block';

      try {
        const res = await api.put(`/cases/${data.active.id}`, { hearing_date: newDate });
        if(res.ok){
          const activeItem = $('.case-item.active');
          if(activeItem){
            activeItem.dataset.hearing = newDate;
            renderCase(activeItem);
          }
          toast('Hearing date updated', 'success');
        } else {
          throw new Error(res.error || 'Update failed');
        }
      } catch (err) {
        console.error('Update error:', err);
        hearingDateText.textContent = originalText;
        alert(err.message || 'Failed to update date');
      }
    }
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
          if(data.ok){
            setStatus('AI Research started...', true);
            // Start polling for completion
            setTimeout(() => loadChatHistory(caseId), 3000);
          } else {
            throw new Error(data.error || 'Failed to start research');
          }
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
                    // Extract actions if present
                    let cleanContent = fullContent;
                    let actions = [];
                    const actionMatch = fullContent.match(/ACTIONS:\s*(\[.*?\])\s*$/s);
                    if(actionMatch){
                      try {
                        actions = JSON.parse(actionMatch[1]);
                        cleanContent = fullContent.replace(/ACTIONS:\s*\[.*?\]\s*$/s, '').trim();
                      } catch(e) { console.error('Pill parse error', e); }
                    }

                    bub.innerHTML = marked.parse(cleanContent);
                    
                    if(actions.length){
                      const actionWrap = document.createElement('div');
                      actionWrap.className = 'msg-actions';
                      actionWrap.innerHTML = actions.map(a => `
                        <button class="pill-action" data-prompt="${escapeHTML(a.prompt)}">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                          ${escapeHTML(a.label)}
                        </button>
                      `).join('');
                      
                      actionWrap.addEventListener('click', e => {
                        const pill = e.target.closest('.pill-action');
                        if(!pill) return;
                        const prompt = pill.dataset.prompt;
                        chatInput.value = prompt;
                        chatForm && chatForm.requestSubmit();
                        actionWrap.remove(); // Remove after use
                      });
                      
                      wrap.appendChild(actionWrap);
                    }

                    chatBody.scrollTop = chatBody.scrollHeight;
                    return;
                }
                const chunk = decoder.decode(value, { stream: true });
                fullContent += chunk;
                
                // Real-time preview without the raw JSON block
                const preview = fullContent.replace(/ACTIONS:\s*\[.*?\]\s*$/s, '').trim();
                bub.innerHTML = marked.parse(preview); 
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
      appendMessage({ role:'user', content: txt });
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
    } else if (data.active) {
      // Direct navigation logic
      updateChatUI();
    }

    // Auto-scroll chat to the bottom on load.
    if(chatBody) chatBody.scrollTop = chatBody.scrollHeight;
  });
})();
