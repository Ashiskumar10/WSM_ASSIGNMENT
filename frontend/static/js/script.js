(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const landingView = $('#landing-view');
  const resultsView = $('#results-view');
  const heroForm = $('#hero-search-form');
  const resultsForm = $('#results-search-form');
  const heroQuery = $('#hero-query');
  const resultsQuery = $('#results-query');
  const resultsPhonetic = $('#results-phonetic');
  const resultsSpellCorrect = $('#results-spellcorrect');
  const resultsContainer = $('#results-container');
  const toastRegion = $('#toast-region');
  const uploadOverlay = $('#upload-overlay');
  const fileInput = $('#file-input');
  const modeDescription = $('#mode-description');
  const historyStoreKey = 'findly-search-history';
  const themeStoreKey = 'findly-theme';

  let currentMode = 'ranked';
  let currentSoundex = false;
  let currentSpellCorrect = true;
  let lastQuery = '';
  let searchSequence = 0;

  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'error' : ''}`;
    toast.textContent = message;
    toastRegion.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3600);
  }

  function setLoading(loading) {
    document.querySelectorAll('.search-submit').forEach((button) => {
      button.disabled = loading;
      button.classList.toggle('is-loading', loading);
      const span = button.querySelector('span');
      if (span) span.textContent = loading ? 'Searching' : 'Search';
    });
  }

  async function loadStats() {
    try {
      const response = await fetch('/stats');
      const stats = await response.json();
      $('#stat-documents').textContent = Number(stats.document_count || 0).toLocaleString();
      $('#stat-terms').textContent = Number(stats.unique_terms || 0).toLocaleString();
      $('#stat-tokens').textContent = Number(stats.total_tokens || 0).toLocaleString();
    } catch (_error) {
      $('#stat-documents').textContent = '—';
      $('#stat-terms').textContent = '—';
      $('#stat-tokens').textContent = '—';
    }
  }

  function readHistory() {
    try {
      const parsed = JSON.parse(localStorage.getItem(historyStoreKey) || '[]');
      return Array.isArray(parsed) ? parsed.slice(0, 8) : [];
    } catch (_error) {
      return [];
    }
  }

  function saveHistory(query) {
    const history = readHistory().filter((item) => item.toLowerCase() !== query.toLowerCase());
    history.unshift(query);
    localStorage.setItem(historyStoreKey, JSON.stringify(history.slice(0, 8)));
    renderHistory();
  }

  function renderHistory() {
    const target = $('#search-history');
    const history = readHistory();
    target.replaceChildren();
    if (!history.length) {
      const empty = document.createElement('p');
      empty.className = 'history-empty';
      empty.textContent = 'Your searches will appear here.';
      target.appendChild(empty);
      return;
    }
    history.forEach((query) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'history-item';
      button.textContent = query;
      button.title = query;
      button.addEventListener('click', () => runSearch(query));
      target.appendChild(button);
    });
  }

  function syncFeatureControls() {
    const selected = {
      boolean: currentMode === 'boolean',
      wildcard: currentMode === 'wildcard',
      soundex: currentSoundex,
      spellcorrect: currentSpellCorrect,
    };
    document.querySelectorAll('[data-feature]').forEach((button) => {
      const active = Boolean(selected[button.dataset.feature]);
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    document.querySelectorAll('.mode-option').forEach((button) => {
      button.classList.toggle('active', button.dataset.mode === currentMode);
    });
    if (resultsPhonetic) resultsPhonetic.checked = currentSoundex;
    if (resultsSpellCorrect) resultsSpellCorrect.checked = currentSpellCorrect;
    const modeText = currentMode === 'boolean' ? 'Boolean retrieval'
      : currentMode === 'wildcard' ? 'K-gram wildcard expansion' : 'TF-IDF ranking';
    const activeHints = [modeText];
    if (currentSoundex) activeHints.push('Soundex on');
    if (currentSpellCorrect) activeHints.push('spelling help on');
    document.querySelectorAll('.tools-hint').forEach((hint) => {
      hint.textContent = activeHints.join(' · ');
    });
    if (modeDescription) {
      modeDescription.textContent = currentMode === 'boolean'
        ? 'Combine terms with AND, OR, NOT and parentheses.'
        : currentMode === 'wildcard'
          ? 'Use * for many characters or ? for one character.'
          : 'Sort documents by TF-IDF relevance.';
    }
  }

  function setSearchMode(mode) {
    currentMode = ['boolean', 'wildcard'].includes(mode) ? mode : 'ranked';
    syncFeatureControls();
  }

  function toggleFeature(feature) {
    if (feature === 'boolean' || feature === 'wildcard') {
      setSearchMode(currentMode === feature ? 'ranked' : feature);
    } else if (feature === 'soundex') {
      currentSoundex = !currentSoundex;
      syncFeatureControls();
    } else if (feature === 'spellcorrect') {
      currentSpellCorrect = !currentSpellCorrect;
      syncFeatureControls();
    }
    if (!resultsView.classList.contains('hidden') && lastQuery) runSearch(lastQuery);
  }

  function showResultsView(query) {
    landingView.classList.add('hidden');
    resultsView.classList.remove('hidden');
    resultsQuery.value = query;
    $('#clear-query').classList.toggle('visible', Boolean(query));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function showLandingView() {
    resultsView.classList.add('hidden');
    landingView.classList.remove('hidden');
    heroQuery.value = '';
    heroQuery.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function renderResults(data, query) {
    resultsContainer.replaceChildren();
    const total = Number(data.total || 0);
    const time = Number(data.execution_time_ms || 0);
    $('#results-heading').textContent = total === 1 ? '1 document found' : `${total.toLocaleString()} documents found`;
    $('#results-meta').textContent = `${total.toLocaleString()} matching ${total === 1 ? 'document' : 'documents'} · ${time.toFixed(2)} ms · ${data.mode === 'boolean' ? 'Boolean retrieval' : data.mode === 'wildcard' ? 'K-gram wildcard search' : 'TF-IDF ranking'}${data.phonetic ? ' · Soundex' : ''}${data.spell_correct ? ' · Spell correction' : ''}`;
    $('#sort-label').innerHTML = data.mode === 'boolean' ? 'Boolean match <span>✓</span>' : data.mode === 'wildcard' ? 'Wildcard match <span>＊</span>' : 'Relevance <span>↓</span>';
    $('#results-footer').classList.toggle('hidden', total === 0);
    $('#footer-count').textContent = `Showing ${Math.min(total, data.results.length)} of ${total} results`;

    const correctionBanner = $('#correction-banner');
    correctionBanner.classList.add('hidden');
    correctionBanner.replaceChildren();
    if (data.corrected_query) {
      correctionBanner.classList.remove('hidden');
      correctionBanner.append('Showing results for ');
      const corrected = document.createElement('strong');
      corrected.textContent = data.corrected_query;
      correctionBanner.append(corrected, ' · Original query: ', query);
    } else if (Array.isArray(data.suggestions) && data.suggestions.length) {
      correctionBanner.classList.remove('hidden');
      correctionBanner.append('Possible spelling: ');
      data.suggestions.slice(0, 3).forEach((suggestion, index) => {
        if (index) correctionBanner.append(', ');
        const item = document.createElement('strong');
        item.textContent = `${suggestion.original} → ${suggestion.suggestion}`;
        correctionBanner.append(item);
      });
    }

    if (!total) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      const icon = document.createElement('div');
      icon.className = 'empty-icon';
      icon.textContent = '⌕';
      const heading = document.createElement('h3');
      heading.textContent = 'No matches this time.';
      const message = document.createElement('p');
      message.textContent = data.message || 'Try another phrase, remove a filter, or check your spelling.';
      empty.append(icon, heading, message);
      resultsContainer.appendChild(empty);
      return;
    }

    data.results.forEach((result, index) => {
      const card = document.createElement('article');
      card.className = 'result-card';
      card.style.animationDelay = `${Math.min(index * 45, 250)}ms`;

      const top = document.createElement('div');
      top.className = 'result-topline';
      const rank = document.createElement('span');
      rank.className = 'result-rank';
      rank.textContent = String(result.rank);
      const source = document.createElement('span');
      source.className = 'result-source';
      source.textContent = result.source || 'Corpus document';
      const id = document.createElement('span');
      id.className = 'result-id';
      id.textContent = result.doc_id;
      top.append(rank, source, id);

      const title = document.createElement('h3');
      title.className = 'result-title';
      title.textContent = result.title;
      const snippet = document.createElement('p');
      snippet.className = 'result-snippet';
      // snippet_html is generated server-side with all source text HTML-escaped.
      snippet.innerHTML = result.snippet_html || '';

      const bottom = document.createElement('div');
      bottom.className = 'result-bottom';
      const tags = document.createElement('div');
      tags.className = 'result-tags';
      (result.matched_terms || []).slice(0, 4).forEach((term) => {
        const tag = document.createElement('span');
        tag.className = 'term-tag';
        tag.textContent = term;
        tags.appendChild(tag);
      });
      const score = document.createElement('div');
      score.className = 'result-score';
      const scoreText = document.createElement('span');
      scoreText.textContent = `Relevance ${Number(result.score_percent || 0).toFixed(1)}%`;
      const track = document.createElement('span');
      track.className = 'score-track';
      const fill = document.createElement('span');
      fill.className = 'score-fill';
      fill.style.display = 'block';
      fill.style.width = `${Math.max(0, Math.min(100, Number(result.score_percent || 0)))}%`;
      track.appendChild(fill);
      score.append(scoreText, track);
      bottom.append(tags, score);
      card.append(top, title, snippet, bottom);
      resultsContainer.appendChild(card);
    });
  }

  async function runSearch(query) {
    const cleanQuery = String(query || '').trim();
    if (!cleanQuery) {
      showToast('Enter a query to search.', 'error');
      return;
    }
    lastQuery = cleanQuery;
    showResultsView(cleanQuery);
    setLoading(true);
    const sequence = ++searchSequence;
    try {
      const response = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: cleanQuery,
          mode: currentMode,
          phonetic: currentSoundex,
          spell_correct: currentSpellCorrect,
        }),
      });
      const data = await response.json();
      if (sequence !== searchSequence) return;
      if (!response.ok) throw new Error(data.error || 'Search request failed.');
      renderResults(data, cleanQuery);
      saveHistory(cleanQuery);
      $('#clear-query').classList.add('visible');
    } catch (error) {
      resultsContainer.replaceChildren();
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      const heading = document.createElement('h3');
      heading.textContent = 'Search could not be completed.';
      const message = document.createElement('p');
      message.textContent = error.message;
      empty.append(heading, message);
      resultsContainer.appendChild(empty);
      $('#results-heading').textContent = 'Search error';
      $('#results-meta').textContent = 'Check the query and try again.';
    } finally {
      if (sequence === searchSequence) setLoading(false);
    }
  }

  async function uploadFiles(files) {
    const selected = Array.from(files || []);
    if (!selected.length) return;
    const invalid = selected.filter((file) => !file.name.toLowerCase().endsWith('.txt'));
    if (invalid.length) {
      showToast('Only .txt files are supported.', 'error');
      return;
    }
    const formData = new FormData();
    selected.forEach((file) => formData.append('files', file));
    uploadOverlay.classList.remove('hidden');
    try {
      const response = await fetch('/upload', { method: 'POST', body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Upload failed.');
      await loadStats();
      showToast(data.message || 'Corpus indexed successfully.');
      if (data.rejected_files && data.rejected_files.length) showToast(`Skipped: ${data.rejected_files.join(', ')}`, 'error');
      if (!resultsView.classList.contains('hidden') && lastQuery) runSearch(lastQuery);
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      uploadOverlay.classList.add('hidden');
      fileInput.value = '';
    }
  }

  function applyTheme(theme) {
    const dark = theme === 'dark';
    document.body.classList.toggle('dark', dark);
    $('#theme-toggle').setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    localStorage.setItem(themeStoreKey, dark ? 'dark' : 'light');
  }

  heroForm.addEventListener('submit', (event) => {
    event.preventDefault();
    runSearch(heroQuery.value);
  });
  resultsForm.addEventListener('submit', (event) => {
    event.preventDefault();
    runSearch(resultsQuery.value);
  });
  $('#clear-query').addEventListener('click', () => {
    resultsQuery.value = '';
    lastQuery = '';
    $('#clear-query').classList.remove('visible');
    $('#results-heading').textContent = 'Search your documents';
    $('#results-meta').textContent = 'Your indexed content, all in one place.';
    $('#correction-banner').classList.add('hidden');
    $('#results-footer').classList.add('hidden');
    resultsContainer.innerHTML = '<div class="welcome-results"><div class="welcome-orbit">✳</div><h3>Ready when you are.</h3><p>Enter a query to explore your indexed documents.</p></div>';
    resultsQuery.focus();
  });
  resultsQuery.addEventListener('input', () => $('#clear-query').classList.toggle('visible', Boolean(resultsQuery.value)));
  document.querySelectorAll('.suggestion-chip').forEach((button) => {
    button.addEventListener('click', () => {
      heroQuery.value = button.dataset.query || '';
      heroForm.requestSubmit();
    });
  });
  document.querySelectorAll('.mode-option').forEach((button) => {
    button.addEventListener('click', () => {
      setSearchMode(button.dataset.mode);
      if (!resultsView.classList.contains('hidden') && lastQuery) runSearch(lastQuery);
    });
  });
  document.querySelectorAll('[data-feature]').forEach((button) => {
    button.addEventListener('click', () => toggleFeature(button.dataset.feature));
  });
  resultsPhonetic.addEventListener('change', () => {
    currentSoundex = resultsPhonetic.checked;
    syncFeatureControls();
    if (lastQuery) runSearch(lastQuery);
  });
  resultsSpellCorrect.addEventListener('change', () => {
    currentSpellCorrect = resultsSpellCorrect.checked;
    syncFeatureControls();
    if (lastQuery) runSearch(lastQuery);
  });
  $('#upload-trigger').addEventListener('click', () => fileInput.click());
  $('#upload-trigger-results').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => uploadFiles(fileInput.files));
  $('#back-home').addEventListener('click', showLandingView);
  $('#new-search').addEventListener('click', showLandingView);
  $('#brand-home').addEventListener('click', (event) => {
    event.preventDefault();
    showLandingView();
  });
  $('#clear-history').addEventListener('click', () => {
    localStorage.removeItem(historyStoreKey);
    renderHistory();
    showToast('Search history cleared.');
  });
  $('#theme-toggle').addEventListener('click', () => applyTheme(document.body.classList.contains('dark') ? 'light' : 'dark'));

  applyTheme(localStorage.getItem(themeStoreKey) || 'light');
  setSearchMode('ranked');
  syncFeatureControls();
  renderHistory();
  loadStats();
})();
