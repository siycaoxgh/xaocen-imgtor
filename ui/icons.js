(function () {
  const paths = {
    brand: '<rect x="4" y="4" width="16" height="16" rx="3"></rect><rect x="8" y="8" width="8" height="8" rx="1"></rect>',
    home: '<path d="m3 10 9-7 9 7"></path><path d="M5 9v11h14V9M9 20v-6h6v6"></path>',
    capture: '<path d="M5 3H3v2M19 3h2v2M21 19v2h-2M3 19v2h2"></path><circle cx="12" cy="12" r="4"></circle>',
    record: '<circle cx="12" cy="12" r="8"></circle><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"></circle>',
    gallery: '<rect x="3" y="4" width="18" height="16" rx="2"></rect><circle cx="8.5" cy="9" r="1.5"></circle><path d="m4 17 5-5 3 3 2-2 6 5"></path>',
    crop: '<path d="M6 3v12a3 3 0 0 0 3 3h12M3 6h12a3 3 0 0 1 3 3v12"></path>',
    settings: '<path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h10M18 18h2"></path><circle cx="16" cy="6" r="2"></circle><circle cx="8" cy="12" r="2"></circle><circle cx="16" cy="18" r="2"></circle>',
    about: '<circle cx="12" cy="12" r="9"></circle><path d="M12 11v5M12 8h.01"></path>',
    moon: '<path d="M20 15.5A8 8 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z"></path>',
    sun: '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path>',
    arrow: '<path d="M5 12h13M13 6l6 6-6 6"></path>',
    arrowLeft: '<path d="M19 12H6M11 6l-6 6 6 6"></path>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.7-4L3 10"></path><path d="M3 5v5h5M4 13a8 8 0 0 0 14.7 4L21 14"></path><path d="M21 19v-5h-5"></path>',
    check: '<path d="m5 12 4 4L19 6"></path>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"></path>',
    save: '<path d="M5 3h12l3 3v15H4V3h1Z"></path><path d="M8 3v6h8V3M8 21v-7h8v7"></path>',
    play: '<path d="m9 6 9 6-9 6V6Z"></path>',
    pause: '<path d="M9 6v12M15 6v12"></path>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3"></path>',
    close: '<path d="m6 6 12 12M18 6 6 18"></path>'
    ,menu: '<path d="M4 6h16M4 12h16M4 18h16"></path>',
    chevronLeft: '<path d="m15 18-6-6 6-6"></path>',
    chevronRight: '<path d="m9 18 6-6-6-6"></path>'
  };

  window.icon = function (name, size) {
    const body = paths[name] || paths.about;
    const px = size || 20;
    return `<svg class="svg-icon" width="${px}" height="${px}" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
  };

  window.renderIcons = function (root) {
    (root || document).querySelectorAll('[data-icon]').forEach(function (node) {
      node.innerHTML = window.icon(node.dataset.icon, node.dataset.size || 20);
    });
  };
})();
