(function(){
  'use strict';
  const { $, $$, api, toast } = App;

  // ---------- Tabs ---------- //
  $$('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      $$('.tab').forEach(b => b.classList.toggle('active', b === btn));
      $$('.tab-pane').forEach(p => p.classList.toggle('active', p.dataset.pane === target));
    });
  });

  // ---------- Save Logic ---------- //
  const saveBtn = $('#save-settings');
  if(saveBtn){
    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      const originalText = saveBtn.innerHTML;
      saveBtn.innerHTML = 'Saving...';

      // Collect data from all visible forms
      const firmFormData = new FormData($('#firm-form'));
      const aiFormData   = new FormData($('#ai-form'));
      
      const payload = {
        firm_name:      firmFormData.get('firm_name'),
        lawyer_name:    firmFormData.get('lawyer_name'),
        address:        firmFormData.get('address'),
        default_court:  firmFormData.get('default_court'),
        
        ai_language:    aiFormData.get('ai_language'),
        max_judgments:  parseInt(aiFormData.get('max_judgments')),
        include_ipc_equivalent: aiFormData.get('include_ipc_equivalent') === 'on'
      };

      try {
        const res = await api.post('/settings', payload);
        if(res.ok){
          toast('Settings saved successfully', 'success');
        } else {
          throw new Error(res.error || 'Failed to save settings');
        }
      } catch(err) {
        toast(err.message, 'error');
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = originalText;
      }
    });
  }
})();
