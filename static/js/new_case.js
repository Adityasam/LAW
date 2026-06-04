/* -------------------------------------------------------------------------
   New Case Modal logic.
   Handles multi-file upload, form submission, and case creation.
   ------------------------------------------------------------------------- */
(function(){
  'use strict';
  const { $, $$, escapeHTML, api, toast } = App;

  // ---------- "New Case" modal ---------- //
  const modal     = $('#new-case-modal');
  const openBtns  = $$('#open-new-case'); // Support multiple trigger buttons
  const closeBtn  = $('#close-new-case');
  const cancelBtn = $('#cancel-new-case');
  const form      = $('#new-case-form');
  const dz        = $('#drop-zone');
  const fileInput = $('#doc-files');
  const fileList  = $('#doc-file-list');

  let stagedFiles = []; // File[]

  function openModal(){
    if(!modal) return;
    modal.classList.add('open');
    // Focus the first field for keyboard users.
    setTimeout(() => $('#f-title')?.focus(), 50);
  }
  function closeModal(){
    if(!modal) return;
    modal.classList.remove('open');
    if(form) form.reset();
    stagedFiles = [];
    renderFileList();
  }

  function fmtSize(bytes){
    if(bytes < 1024) return bytes + ' B';
    if(bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
    return (bytes/(1024*1024)).toFixed(1) + ' MB';
  }

  function addFiles(fileLikeList){
    const allowed = ['pdf','doc','docx','txt','jpg','jpeg','png'];
    Array.from(fileLikeList).forEach(f => {
      const ext = (f.name.split('.').pop() || '').toLowerCase();
      if(!allowed.includes(ext)){
        toast(`Skipped ${f.name} — unsupported file type`, 'error');
        return;
      }
      if(f.size > 16 * 1024 * 1024){
        toast(`Skipped ${f.name} — exceeds 16 MB`, 'error');
        return;
      }
      // De-dupe by name+size.
      const key = f.name + ':' + f.size;
      if(stagedFiles.some(x => (x.name + ':' + x.size) === key)) return;
      stagedFiles.push(f);
    });
    renderFileList();
  }

  function renderFileList(){
    if(!fileList) return;
    fileList.innerHTML = stagedFiles.map((f, i) => `
      <div class="upload-item" data-idx="${i}">
        <div class="ic">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6"/></svg>
        </div>
        <div class="meta">
          <div class="n">${escapeHTML(f.name)}</div>
          <div class="s">${fmtSize(f.size)}</div>
        </div>
        <button class="rm" type="button" title="Remove" data-rm="${i}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M6 18L18 6"/></svg>
        </button>
      </div>`).join('');

    $$('.rm', fileList).forEach(btn => {
      btn.addEventListener('click', e => {
        e.preventDefault();
        const idx = parseInt(btn.dataset.rm, 10);
        stagedFiles.splice(idx, 1);
        renderFileList();
      });
    });
  }

  function wireModal(){
    if(!modal) return;

    openBtns.forEach(btn => btn.addEventListener('click', openModal));
    closeBtn && closeBtn.addEventListener('click', closeModal);
    cancelBtn && cancelBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', e => {
      if(e.target === modal) closeModal();
    });
    document.addEventListener('keydown', e => {
      if(e.key === 'Escape' && modal.classList.contains('open')) closeModal();
    });

    if(dz){
      dz.addEventListener('click', () => fileInput?.click());
      dz.addEventListener('dragover', e => { e.preventDefault(); dz.style.borderColor = 'var(--gold)'; });
      dz.addEventListener('dragleave', () => { dz.style.borderColor = ''; });
      dz.addEventListener('drop', e => {
        e.preventDefault();
        dz.style.borderColor = '';
        if(e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
      });
    }
    if(fileInput){
      fileInput.addEventListener('change', () => {
        if(fileInput.files) addFiles(fileInput.files);
        // Reset the input so the same file can be re-selected.
        fileInput.value = '';
      });
    }

    if(form){
      form.addEventListener('submit', async e => {
        e.preventDefault();
        const submit = $('#submit-new-case');
        if(submit){ submit.disabled = true; submit.textContent = 'Creating…'; }

        const payload = {
          lawyer_id:   1, // Default to first lawyer for now
          title:       $('#f-title').value.trim(),
          client_name: $('#f-client').value.trim(),
          case_type:   $('#f-type').value,
          court:       $('#f-court').value.trim() || null,
          sections:    $('#f-sections').value.split(',').map(s => s.trim()).filter(Boolean),
          hearing_date:$('#f-hearing').value || null,
          status:      'Active',
          facts:       $('#f-facts').value.trim() || null,
        };
        if(!payload.title || !payload.client_name || !payload.case_type){
          toast('Title, client and case type are required', 'error');
          if(submit){ submit.disabled = false; submit.textContent = 'Create Case'; }
          return;
        }

        try {
          // 1. Create the case
          const r1 = await api.post('/cases/', payload);
          if(!r1.ok) throw new Error(r1.error || 'Failed to create case');
          const caseId = r1.case.id;

          // 2. Upload each staged file
          for(const f of stagedFiles){
            const fd = new FormData();
            fd.append('file', f);
            const r2 = await api.postForm(`/cases/${caseId}/documents`, fd);
            if(!r2.ok){
              console.warn('Upload failed for', f.name, r2.error);
            }
          }

          toast('Case created — opening workspace…', 'success', 1500);
          // 3. Go to the case details page so the user can start chatting.
          setTimeout(() => { window.location.href = `/case/${caseId}`; }, 600);
        } catch(err){
          toast(err.message || 'Something went wrong', 'error');
          if(submit){ submit.disabled = false; submit.textContent = 'Create Case'; }
        }
      });
    }
  }

  // ---------- Init ---------- //
  document.addEventListener('DOMContentLoaded', () => {
    wireModal();
  });
})();
