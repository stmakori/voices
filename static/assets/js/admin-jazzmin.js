(function () {
  function updateSelectPlaceholderState(selectEl) {
    if (!selectEl) return;

    var selectedOption = selectEl.options[selectEl.selectedIndex];
    var hasMeaningfulValue = !!(selectEl.value && String(selectEl.value).trim() !== '');

    // Treat a first empty option as a placeholder state.
    var isPlaceholder = !hasMeaningfulValue;
    if (selectedOption && selectedOption.value === '' && selectEl.selectedIndex === 0) {
      isPlaceholder = true;
    }

    if (isPlaceholder) {
      selectEl.classList.add('is-placeholder');
    } else {
      selectEl.classList.remove('is-placeholder');
    }
  }

  function wireAdminToolbarSelects() {
    var selector = '#change-list-filters #changelist-search .search-filter, #changelist .actions select';
    var selects = document.querySelectorAll(selector);

    if (!selects.length) return;

    selects.forEach(function (selectEl) {
      updateSelectPlaceholderState(selectEl);
      selectEl.addEventListener('change', function () {
        updateSelectPlaceholderState(selectEl);
      });
    });
  }

  function normalizeAdminFormEditors() {
    var summernoteSelectors = [
      '.django-summernote-widget',
      '.django-summernote-widget iframe',
      '.note-editor',
      '.note-editor .note-editing-area',
      '.note-editor .note-editable'
    ];

    summernoteSelectors.forEach(function (selector) {
      var nodes = document.querySelectorAll(selector);
      nodes.forEach(function (node) {
        node.style.width = '100%';
        node.style.maxWidth = '100%';
        node.style.boxSizing = 'border-box';
      });
    });

    var toolbarSelects = document.querySelectorAll('.note-editor .note-toolbar select');
    toolbarSelects.forEach(function (selectEl) {
      selectEl.style.width = 'auto';
      selectEl.style.maxWidth = '140px';
      selectEl.style.minWidth = '88px';
    });
  }

  function styleAddButtons() {
    var candidateSelector = [
      'a.addlink',
      'a.btn-success[href*="/add/"]',
      'a[href*="/add/"]'
    ].join(',');

    var links = document.querySelectorAll(candidateSelector);
    links.forEach(function (link) {
      var text = (link.textContent || '').trim().toLowerCase();
      var href = (link.getAttribute('href') || '').toLowerCase();
      var isAddLike = text.indexOf('add') !== -1 || href.indexOf('/add/') !== -1;
      var isSidebar = !!link.closest('.main-sidebar');
      var isInlineIconOnly = link.classList.contains('related-widget-wrapper-link');

      if (isAddLike && !isSidebar && !isInlineIconOnly) {
        link.classList.add('vav-add-btn');
      }
    });
  }

  function initAdminUIEnhancements() {
    wireAdminToolbarSelects();
    normalizeAdminFormEditors();
    styleAddButtons();

    // Summernote can initialize after DOM ready; run a few times to catch late mounts.
    var attempts = 0;
    var timer = setInterval(function () {
      normalizeAdminFormEditors();
      styleAddButtons();
      attempts += 1;
      if (attempts >= 12) {
        clearInterval(timer);
      }
    }, 300);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdminUIEnhancements);
  } else {
    initAdminUIEnhancements();
  }
})();
