document.addEventListener('DOMContentLoaded', () => {
  const docSearch = document.getElementById('doc-search');
  const docRows = document.querySelectorAll('.doc-row');
  const summaryModal = document.getElementById('summary-modal');
  const closeSummary = document.getElementById('close-summary');
  const summaryText = document.getElementById('summary-text');
  const summaryDocName = document.getElementById('summary-doc-name');

  // Search logic
  if (docSearch) {
    docSearch.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase();
      docRows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? 'grid' : 'none';
      });
    });
  }

  // Summary modal logic
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.view-summary');
    if (btn) {
      const summary = btn.dataset.summary;
      const row = btn.closest('.doc-row');
      const docName = row.querySelector('.doc-name .n').textContent;
      
      summaryText.innerHTML = typeof marked !== 'undefined' ? marked.parse(summary) : summary;
      summaryDocName.textContent = docName;
      summaryModal.classList.add('open');
    }
  });

  if (closeSummary) {
    closeSummary.addEventListener('click', () => {
      summaryModal.classList.remove('open');
    });
  }

  if (summaryModal) {
    summaryModal.addEventListener('click', (e) => {
      if (e.target === summaryModal) {
        summaryModal.classList.remove('open');
      }
    });
  }
});
