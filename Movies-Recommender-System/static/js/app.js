/* =============================================================================
   CINEVIBE — App Logic
   Search → Show Details → Click Recommend → Get Recommendations
   ============================================================================= */

const API = '';  // Same origin
const FALLBACK_POSTER = '/no_poster.png';

// ─── State ─────────────────────────────────────────────────────────────────────
let allMovies = [];
let selectedGenre = 'All';
let currentMovie = '';

// ─── Genre Color Map (for poster placeholders) ─────────────────────────────────
const GENRE_COLORS = {
    'Action':          'genre-action',
    'Drama':           'genre-drama',
    'Comedy':          'genre-comedy',
    'Horror':          'genre-horror',
    'Romance':         'genre-romance',
    'Science Fiction': 'genre-sci-fi',
    'Thriller':        'genre-thriller',
    'Animation':       'genre-animation',
};

// ─── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const resp = await fetch(`${API}/api/movies`);
        allMovies = await resp.json();
    } catch (e) {
        console.error('Failed to load movies:', e);
    }

    setupSearch();
    setupGenreFilters();
    setupThemeToggle();
    setupControls();
    loadRecPosterWall();
});

// ─── Poster Wall for Recommend Page ────────────────────────────────────────────
async function loadRecPosterWall() {
    const wall = document.getElementById('recPosterWall');
    if (!wall) return;

    const colors = ['#1a1028','#0f1a2e','#1a0f1e','#0d1f2d','#1f0d1a','#12102a','#1a1520'];
    const cardCount = 35;

    function createCards() {
        const frag = document.createDocumentFragment();
        for (let i = 0; i < cardCount; i++) {
            const card = document.createElement('div');
            card.className = 'poster-card';
            card.style.animationDelay = `${(i % 7) * 0.6}s`;
            card.style.background = `linear-gradient(145deg, ${colors[i % 7]}, #0a0a12)`;
            frag.appendChild(card);
        }
        return frag;
    }

    wall.appendChild(createCards());
    wall.appendChild(createCards());

    const allCards = wall.querySelectorAll('.poster-card');
    allCards.forEach(card => {
        const img = document.createElement('img');
        img.src = FALLBACK_POSTER;
        img.alt = '';
        img.loading = 'lazy';
        card.appendChild(img);
    });

    try {
        const resp = await fetch(`${API}/api/popular`);
        const posters = await resp.json();
        if (!Array.isArray(posters) || posters.length === 0) return;
        posters.forEach((p, i) => {
            if (p.poster) {
                [i, i + cardCount].forEach(idx => {
                    if (allCards[idx]) {
                        const img = allCards[idx].querySelector('img');
                        if (img) {
                            img.onload = () => {
                                allCards[idx].style.background = 'none';
                            };
                            img.onerror = () => {
                                img.src = FALLBACK_POSTER;
                            };
                            img.src = p.poster;
                        }
                    }
                });
            }
        });
    } catch (e) {}
}


// ─── Search Autocomplete ───────────────────────────────────────────────────────
function setupSearch() {
    const input = document.getElementById('searchInput');
    const dropdown = document.getElementById('searchDropdown');
    const toggleBtn = document.getElementById('dropdownToggle');
    let activeIndex = -1;
    let dropdownOpen = false;

    function hideMoviePanel() {
        const sel = document.getElementById('selectedMovie');
        const ctrl = document.getElementById('controlsBar');
        const res = document.getElementById('resultsSection');
        const hor = document.getElementById('horizontalSection');
        if (sel) sel.style.display = 'none';
        if (ctrl) ctrl.style.display = 'none';
        if (res) res.style.display = 'none';
        if (hor) hor.style.display = 'none';
    }

    function restoreMoviePanel() {
        if (currentMovie) {
            const sel = document.getElementById('selectedMovie');
            const ctrl = document.getElementById('controlsBar');
            if (sel) sel.style.display = 'flex';
            if (ctrl) ctrl.style.display = 'block';
        }
    }

    function openDropdown(items) {
        dropdown.innerHTML = items;
        dropdown.classList.add('show');
        dropdownOpen = true;
        hideMoviePanel();
        bindDropdownClicks(dropdown);
    }

    function closeDropdown() {
        dropdown.classList.remove('show');
        if (toggleBtn) toggleBtn.classList.remove('open');
        dropdownOpen = false;
        restoreMoviePanel();
    }

    // Dropdown toggle button
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            if (dropdownOpen) {
                closeDropdown();
            } else {
                const moviesToShow = allMovies.slice(0, 200);
                const html = moviesToShow.map((m, i) =>
                    `<div class="dropdown-item" data-index="${i}" data-title="${escapeHtml(m)}">${escapeHtml(m)}</div>`
                ).join('');
                openDropdown(html);
                toggleBtn.classList.add('open');
                input.focus();
            }
        });
    }

    function bindDropdownClicks(dd) {
        dd.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                closeDropdown();
                onMovieSelected(item.dataset.title);
            });
            item.addEventListener('mouseenter', () => {
                dd.querySelectorAll('.dropdown-item').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
            });
        });
    }

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        if (query.length < 2) {
            closeDropdown();
            return;
        }
        const matches = allMovies
            .filter(m => m.toLowerCase().includes(query))
            .slice(0, 15);

        if (matches.length === 0) {
            closeDropdown();
            return;
        }

        const html = matches.map((m, i) =>
            `<div class="dropdown-item" data-index="${i}" data-title="${escapeHtml(m)}">${highlightMatch(m, query)}</div>`
        ).join('');
        openDropdown(html);
        if (toggleBtn) toggleBtn.classList.remove('open');
        activeIndex = -1;
    });

    // Keyboard navigation
    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.dropdown-item');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, items.length - 1);
            items.forEach(el => el.classList.remove('active'));
            items[activeIndex].classList.add('active');
            items[activeIndex].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            items.forEach(el => el.classList.remove('active'));
            items[activeIndex].classList.add('active');
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (activeIndex >= 0) {
                closeDropdown();
                onMovieSelected(items[activeIndex].dataset.title);
            } else if (input.value.trim()) {
                const exact = allMovies.find(m => m.toLowerCase() === input.value.trim().toLowerCase());
                if (exact) {
                    closeDropdown();
                    onMovieSelected(exact);
                }
            }
        } else if (e.key === 'Escape') {
            closeDropdown();
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-wrapper')) {
            closeDropdown();
        }
    });
}


// ─── When a Movie is Selected: Show Details (NO recommendations yet) ───────────
async function onMovieSelected(title) {
    currentMovie = title;
    const input = document.getElementById('searchInput');
    input.value = title;

    // Close dropdown immediately
    const dropdown = document.getElementById('searchDropdown');
    const toggleBtn = document.getElementById('dropdownToggle');
    if (dropdown) dropdown.classList.remove('show');
    if (toggleBtn) toggleBtn.classList.remove('open');

    // Show selected movie details
    const section = document.getElementById('selectedMovie');
    const posterEl = document.getElementById('selectedPoster');
    const titleEl = document.getElementById('selectedTitle');
    const metaEl = document.getElementById('selectedMeta');
    const genresEl = document.getElementById('selectedGenres');
    const overviewEl = document.getElementById('selectedOverview');

    // Show loading state
    section.style.display = 'flex';
    titleEl.textContent = title;
    metaEl.innerHTML = '<span style="color:var(--text-muted)">Loading...</span>';
    genresEl.innerHTML = '';
    overviewEl.textContent = '';
    posterEl.innerHTML = '<div class="skeleton-poster" style="width:180px;border-radius:14px;"></div>';

    // Show controls bar
    document.getElementById('controlsBar').style.display = 'block';

    // Hide previous results
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('horizontalSection').style.display = 'none';

    try {
        const resp = await fetch(`${API}/api/movie-by-title?title=${encodeURIComponent(title)}`);
        if (!resp.ok) throw new Error('Not found');
        const movie = await resp.json();

        // Poster
        if (movie.poster) {
            posterEl.innerHTML = `<img src="${movie.poster}" alt="${escapeHtml(title)}" onerror="this.parentElement.innerHTML='<div class=\\'poster-placeholder genre-default\\' style=\\'width:180px;aspect-ratio:2/3;\\'><div class=\\'placeholder-title\\'>${escapeHtml(title)}</div><div class=\\'placeholder-text\\'>Poster not available</div></div>'">`;
        } else {
            posterEl.innerHTML = `<div class="poster-placeholder genre-default" style="width:180px;aspect-ratio:2/3;">
                <div class="placeholder-title">${escapeHtml(title)}</div>
                <div class="placeholder-text">Poster not available</div>
            </div>`;
        }

        // Meta
        const metaParts = [];
        if (movie.rating) metaParts.push(`<span class="meta-badge badge-rating">⭐ ${Number(movie.rating).toFixed(1)}</span>`);
        if (movie.year) metaParts.push(`<span class="meta-badge badge-year">📅 ${movie.year}</span>`);
        if (movie.runtime) metaParts.push(`<span class="meta-badge badge-runtime">⏱ ${movie.runtime}</span>`);
        metaEl.innerHTML = metaParts.join('');

        // Genres
        genresEl.innerHTML = (movie.genres || []).map(g => `<span class="tag">${g}</span>`).join('');

        // Overview
        overviewEl.textContent = movie.overview || 'No overview available.';
    } catch (e) {
        metaEl.innerHTML = '<span style="color:var(--text-muted)">Could not load details.</span>';
    }
}


// ─── Controls: Recommend Button + Count Slider ─────────────────────────────────
function setupControls() {
    const slider = document.getElementById('resultCount');
    const countDisplay = document.getElementById('countValue');
    const recBtn = document.getElementById('recommendBtn');

    if (slider && countDisplay) {
        slider.addEventListener('input', () => {
            countDisplay.textContent = slider.value;
        });
    }

    if (recBtn) {
        recBtn.addEventListener('click', () => {
            if (currentMovie) {
                fetchRecommendations(currentMovie);
            }
        });
    }
}


// ─── Fetch Recommendations (triggered by button click) ─────────────────────────
async function fetchRecommendations(title) {
    const n = document.getElementById('resultCount')?.value || 12;

    // Show loading message
    const resultsSection = document.getElementById('resultsSection');
    const grid = document.getElementById('movieGrid');
    const heading = document.getElementById('resultsHeading');
    resultsSection.style.display = 'block';
    heading.textContent = '🎬 FINDING SIMILAR MOVIES...';
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:60px;">
        <div style="font-size:2.5rem;margin-bottom:12px;animation:pulse 1s ease-in-out infinite;">🎬</div>
        <p style="color:var(--text-secondary);font-size:1rem;">Searching through 5000+ movies for the best matches...</p>
    </div>`;
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const genreParam = selectedGenre !== 'All' ? `&genre=${encodeURIComponent(selectedGenre)}` : '';
        const resp = await fetch(`${API}/api/recommend?movie=${encodeURIComponent(title)}&n=${n}${genreParam}`);

        if (!resp.ok) throw new Error('Movie not found');
        const results = await resp.json();

        hideSkeleton();
        renderResults(results, title);

        // Auto-scroll to results
        document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'start' });

        // Horizontal "more like this"
        const moreResp = await fetch(`${API}/api/recommend?movie=${encodeURIComponent(title)}&n=20`);
        if (moreResp.ok) {
            const moreResults = await moreResp.json();
            renderHorizontal(moreResults.slice(parseInt(n)), title);
        }
    } catch (e) {
        hideSkeleton();
        document.getElementById('resultsSection').style.display = 'block';
        document.getElementById('movieGrid').innerHTML =
            `<div style="grid-column:1/-1;text-align:center;padding:60px;color:var(--text-muted);">
                <p style="font-size:1.2rem;">😕 Could not find recommendations for "${escapeHtml(title)}"</p>
                <p style="margin-top:8px;">Try a different movie name.</p>
            </div>`;
    }
}


// ─── Render Results Grid ───────────────────────────────────────────────────────
function renderResults(results, searchTitle) {
    const section = document.getElementById('resultsSection');
    const grid = document.getElementById('movieGrid');
    const heading = document.getElementById('resultsHeading');

    heading.textContent = `BECAUSE YOU LIKED "${searchTitle.toUpperCase()}"`;
    section.style.display = 'block';

    grid.innerHTML = results.map((movie, i) => createMovieCard(movie, i)).join('');
}


// ─── Create Movie Card HTML ────────────────────────────────────────────────────
function createMovieCard(movie, index) {
    const delay = index * 0.06;
    const genreClass = getGenreClass(movie.genres);

    const posterHtml = movie.poster
        ? `<img src="${movie.poster}" alt="${escapeHtml(movie.title)}" loading="lazy" onerror="this.onerror=null; this.parentElement.innerHTML=window.makePlaceholder('${escapeHtml(movie.title).replace(/'/g, "\\'")}','${genreClass}')">`
        : `<div class="poster-placeholder ${genreClass}">
            <div class="placeholder-title">${escapeHtml(movie.title)}</div>
            <div class="placeholder-text">Poster not available</div>
           </div>`;

    const genreTags = (movie.genres || []).slice(0, 3)
        .map(g => `<span class="mini-tag">${g}</span>`).join('');

    const overview = movie.overview || '';
    const rating = movie.rating ? `⭐ ${Number(movie.rating).toFixed(1)}` : '';
    const matchBadge = movie.score ? `<div class="match-badge">${movie.score}%</div>` : '';

    return `
    <div class="movie-card" style="animation-delay:${delay}s">
        <div class="card-poster">
            ${matchBadge}
            ${posterHtml}
            <div class="card-overlay">
                <p>${escapeHtml(overview.substring(0, 150))}${overview.length > 150 ? '...' : ''}</p>
            </div>
        </div>
        <div class="card-info">
            <div class="card-title">${escapeHtml(movie.title)}</div>
            <div class="card-meta">
                ${rating ? `<span class="rating">${rating}</span>` : ''}
                ${movie.year ? `<span>${movie.year}</span>` : ''}
                ${movie.runtime ? `<span>${movie.runtime}</span>` : ''}
            </div>
            <div class="card-genres">${genreTags}</div>
        </div>
    </div>`;
}

// Global fallback for broken poster images
window.makePlaceholder = function(title, genreClass) {
    return `<div class="poster-placeholder ${genreClass}">
        <div class="placeholder-title">${title}</div>
        <div class="placeholder-text">Poster not available</div>
    </div>`;
};

function getGenreClass(genres) {
    if (!genres || !genres.length) return 'genre-default';
    return GENRE_COLORS[genres[0]] || 'genre-default';
}


// ─── Horizontal Scroll Section ─────────────────────────────────────────────────
function renderHorizontal(results, searchTitle) {
    if (!results || results.length === 0) return;
    const section = document.getElementById('horizontalSection');
    const scroll = document.getElementById('horizontalScroll');
    const heading = document.getElementById('horizontalHeading');

    heading.textContent = `MORE LIKE "${searchTitle.toUpperCase()}"`;
    section.style.display = 'block';
    scroll.innerHTML = results.map((movie, i) => createMovieCard(movie, i)).join('');
}


// ─── Skeleton Loading ──────────────────────────────────────────────────────────
function showSkeleton() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('horizontalSection').style.display = 'none';

    const section = document.getElementById('skeletonSection');
    const grid = document.getElementById('skeletonGrid');
    section.style.display = 'block';

    const n = document.getElementById('resultCount')?.value || 12;
    grid.innerHTML = Array(parseInt(n)).fill(0).map(() => `
        <div class="skeleton-card">
            <div class="skeleton-poster"></div>
            <div class="skeleton-text"></div>
            <div class="skeleton-text short"></div>
        </div>
    `).join('');
}

function hideSkeleton() {
    document.getElementById('skeletonSection').style.display = 'none';
}


// ─── Genre Filters ─────────────────────────────────────────────────────────────
function setupGenreFilters() {
    const container = document.getElementById('genreFilters');
    if (!container) return;

    container.addEventListener('click', (e) => {
        const chip = e.target.closest('.genre-chip');
        if (!chip) return;

        container.querySelectorAll('.genre-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        selectedGenre = chip.dataset.genre;
    });
}


// ─── Dark/Light Mode Toggle ────────────────────────────────────────────────────
function setupThemeToggle() {
    const toggle = document.getElementById('themeToggle');
    if (!toggle) return;

    const moon = toggle.querySelector('.icon-moon');
    const sun = toggle.querySelector('.icon-sun');
    const saved = localStorage.getItem('cinevibe-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved, moon, sun);

    toggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('cinevibe-theme', next);
        updateThemeIcon(next, moon, sun);
    });
}

function updateThemeIcon(theme, moon, sun) {
    if (theme === 'dark') {
        moon.style.display = 'inline';
        sun.style.display = 'none';
    } else {
        moon.style.display = 'none';
        sun.style.display = 'inline';
    }
}


// ─── Helpers ───────────────────────────────────────────────────────────────────
function highlightMatch(text, query) {
    const idx = text.toLowerCase().indexOf(query);
    if (idx === -1) return escapeHtml(text);
    return escapeHtml(text.substring(0, idx))
        + `<strong style="color:var(--accent)">${escapeHtml(text.substring(idx, idx + query.length))}</strong>`
        + escapeHtml(text.substring(idx + query.length));
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
