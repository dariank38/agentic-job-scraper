document.addEventListener('DOMContentLoaded', async () => {
  const exportBtn = document.getElementById('exportBtn');
  const statusDiv = document.getElementById('status');
  const apiUrlInput = document.getElementById('apiUrl');
  const sourceSelect = document.getElementById('sourceSelect');
  const refreshBtn = document.getElementById('refreshBtn');
  const cookiePreview = document.getElementById('cookiePreview');

  let bossjobSources = [];

  // Load saved API URL
  chrome.storage.local.get(['apiUrl'], (result) => {
    if (result.apiUrl) apiUrlInput.value = result.apiUrl;
    loadSources();
  });

  // Save API URL on change
  apiUrlInput.addEventListener('change', () => {
    chrome.storage.local.set({ apiUrl: apiUrlInput.value });
    loadSources();
  });

  // Refresh sources button
  refreshBtn.addEventListener('click', () => {
    loadSources();
  });

  // Load bossjob sources from API
  async function loadSources() {
    const apiUrl = apiUrlInput.value.trim();
    if (!apiUrl) {
      sourceSelect.innerHTML = '<option value="">Enter API URL first</option>';
      sourceSelect.disabled = true;
      return;
    }

    sourceSelect.innerHTML = '<option value="">Loading sources...</option>';
    sourceSelect.disabled = true;

    try {
      const response = await fetch(`${apiUrl}/api/website-sources`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      const sources = data.sources || [];
      
      // Filter for bossjob sources
      bossjobSources = sources.filter(s => s.site_type === 'bossjob' || s.url.includes('bossjob.com'));
      
      if (bossjobSources.length === 0) {
        sourceSelect.innerHTML = '<option value="">No bossjob sources found</option>';
        showStatus('No bossjob sources in dashboard. Add one first.', 'error');
        return;
      }

      // Populate dropdown
      sourceSelect.innerHTML = bossjobSources.map(s => 
        `<option value="${s.id}">${s.name} (${s.url})</option>`
      ).join('');
      sourceSelect.disabled = false;
      showStatus(`Found ${bossjobSources.length} bossjob source(s). Select one to export cookies.`, 'info');
    } catch (error) {
      sourceSelect.innerHTML = '<option value="">Error loading sources</option>';
      showStatus(`Error loading sources: ${error.message}`, 'error');
    }
  }

  exportBtn.addEventListener('click', async () => {
    const apiUrl = apiUrlInput.value.trim();
    const sourceId = sourceSelect.value;

    if (!apiUrl) {
      showStatus('Please enter API URL', 'error');
      return;
    }
    if (!sourceId) {
      showStatus('Please select a website source', 'error');
      return;
    }

    exportBtn.disabled = true;
    showStatus('Fetching cookies from bossjob.com...', 'info');

    try {
      // Get cookies from bossjob.com
      const cookies = await chrome.cookies.getAll({ domain: 'bossjob.com' });
      
      if (cookies.length === 0) {
        showStatus('No cookies found. Please login to bossjob.com first.', 'error');
        exportBtn.disabled = false;
        return;
      }

      // Format cookies for Playwright
      const formattedCookies = cookies.map(c => {
        // Convert sameSite to Playwright format
        let sameSite = 'Lax';
        if (c.sameSite === 'no_restriction') sameSite = 'None';
        else if (c.sameSite === 'strict') sameSite = 'Strict';
        else if (c.sameSite === 'lax') sameSite = 'Lax';
        
        return {
          name: c.name,
          value: c.value,
          domain: c.domain.startsWith('.') ? c.domain.slice(1) : c.domain,
          path: c.path,
          secure: c.secure,
          httpOnly: c.httpOnly,
          sameSite: sameSite
        };
      });

      // Show preview
      const essentialCookies = formattedCookies.filter(c => 
        ['sessionid', 'user', 'csrftoken', 'uuid'].includes(c.name)
      );
      cookiePreview.textContent = `Found ${formattedCookies.length} cookies\nEssential: ${essentialCookies.map(c => c.name).join(', ')}`;
      cookiePreview.style.display = 'block';

      showStatus('Sending cookies to dashboard...', 'info');

      // Send to backend
      const formData = new FormData();
      formData.append('cookies', JSON.stringify(formattedCookies));

      const response = await fetch(`${apiUrl}/api/website-sources/${sourceId}`, {
        method: 'PUT',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        showStatus(`✓ Cookies exported successfully! ${formattedCookies.length} cookies saved.`, 'success');
      } else {
        const error = await response.text();
        showStatus(`Error: ${response.status} - ${error}`, 'error');
      }
    } catch (error) {
      showStatus(`Error: ${error.message}`, 'error');
    } finally {
      exportBtn.disabled = false;
    }
  });

  function showStatus(message, type) {
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
  }

  // Check if on bossjob.com
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const url = tabs[0]?.url || '';
    if (url.includes('bossjob.com')) {
      showStatus('Ready to export cookies from bossjob.com', 'success');
    } else {
      showStatus('Navigate to bossjob.com and login first', 'info');
    }
  });
});
