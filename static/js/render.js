import { formatDate } from "./utils.js";

// --- MAIN RESULT CARD (Videos) ---
export function createResultCard(item, score) {
    const row = item.data || item;

    // If the item is a Bio/Actress, render the "Entity Header" (The top result)
    if (item.is_bio || row.type === 'bio') {
        return createEntityHeader(row);
    }

    // Standard Video Card Logic
    const scorePct = Math.round(score * 100);
    const dateStr = formatDate(row.releasedate);

    let metaHtml = `<span class="result-id" data-action="copy-id" data-id="${row.dvdid}" title="Click to copy ID">${row.dvdid}</span>`;
    if (dateStr) metaHtml += ` &rsaquo; ${dateStr}`;
    if (row.actress_names) {
        const names = row.actress_names.split(",").slice(0, 2).join(", ");
        metaHtml += ` &rsaquo; ${names}`;
    }

    const snippet = row.jptitle || "No Japanese title available.";
    const safeTitle = row.title.replace(/'/g, "\\'");

    const thumbHtml = row.image
        ? `<div class="result-thumb" data-action="view-image" data-src="${row.image}" data-caption="${safeTitle}">
           <img src="${row.image}" loading="lazy" alt="${row.dvdid}">
         </div>`
        : "";

    const div = document.createElement("div");
    div.className = "result-item";
    div.style.animation = "fadeIn 0.5s ease forwards";

    div.innerHTML = `
            ${thumbHtml}
            <div class="result-content">
                <div class="result-meta">
                    ${metaHtml}
                    <span class="chip">${scorePct}% Match</span>
                </div>
                <a href="${row.generated_url}" target="_blank" class="result-title">${row.title}</a>
                <div class="result-snippet">${snippet}</div>
                <div style="margin-top:4px">
                    <button class="similar-btn"
                        data-action="find-similar"
                        data-id="${row.dvdid}"
                        data-title="${safeTitle}"
                        data-img="${row.image || ""}">
                        Find similar Movies
                    </button>
                </div>
            </div>
        `;
    return div;
}

// --- 1. ENTITY HEADER (Top of Search List - Tier 1+) ---
export function createEntityHeader(bio) {
    const div = document.createElement("div");
    div.className = "entity-header-card";
    div.style.animation = "fadeIn 0.5s ease forwards";

    // Fallback subtitle
    const subtitle = bio.jpName
        ? `${bio.jpName} • Actress`
        : `Actress`;

    div.innerHTML = `
        <img src="${bio.avatar}" class="entity-avatar-small" alt="${bio.name}">
        <div class="entity-info">
            <h2>${bio.name}</h2>
            <div class="entity-subtitle">${subtitle}</div>
        </div>
    `;
    return div;
}

// --- 2. KNOWLEDGE PANEL (Sidebar Content - Tier 2+) ---
export function renderKnowledgePanel(bio) {
    const tier = bio.tier || 0;

    // Helper to add a row
    const addFact = (label, val) => {
        if (!val || val === "?" || val === "N/A") return '';
        // If val has newlines (common in scraped bio text), replace with commas
        const displayVal = String(val).replace(/\n/g, ', ');
        return `<div class="kp-fact"><b>${label}:</b> ${displayVal}</div>`;
    };

    // --- A. Personal Info Section ---
    let personalHtml = '';

    // Tier 2/2.5/3 Fields
    personalHtml += addFact("Born", bio.birthday);
    personalHtml += addFact("Sign", bio.sign);              // Tier 2.5
    personalHtml += addFact("Birthplace", bio.birthplace);  // Tier 2.5
    personalHtml += addFact("Nationality", bio.nationality);
    personalHtml += addFact("Ethnicity", bio.ethnicity);
    personalHtml += addFact("Debut", bio.debut);            // Tier 2.5
    personalHtml += addFact("Years Active", bio.yearsActive);
    personalHtml += addFact("Aliases", bio.alsoKnownAs);

    if (personalHtml) {
        personalHtml = `<div class="kp-group-title">Personal Info</div>` + personalHtml;
    }

    // --- B. Physical Stats Section ---
    let physicalHtml = '';

    physicalHtml += addFact("Height", bio.height ? `${bio.height} cm` : null);
    physicalHtml += addFact("Body Type", bio.type);

    // Measurements logic
    let measureStr = "";
    if (bio.bust) measureStr += `B${bio.bust}`;
    if (bio.cup) measureStr += `(${bio.cup})`;
    if (bio.waist) measureStr += ` W${bio.waist}`;
    if (bio.hip) measureStr += ` H${bio.hip}`;
    if (measureStr) physicalHtml += addFact("Measurements", measureStr);

    physicalHtml += addFact("Breast Type", bio.boobs); // Natural/Augmented
    physicalHtml += addFact("Blood Type", bio.blood_type);
    physicalHtml += addFact("Shoe Size", bio.shoe_size); // Tier 2.5
    physicalHtml += addFact("Eye Color", bio.eyeColor);

    // Hair Logic: Tier 2.5 sends "hair_color" & "hair_length", Tier 3 sends "hair"
    // We prefer specific fields if available, fall back to generic "hair"
    if (bio.hair_color) {
        physicalHtml += addFact("Hair Color", bio.hair_color);
    } else {
        physicalHtml += addFact("Hair", bio.hair);
    }
    physicalHtml += addFact("Hair Length", bio.hair_length); // Tier 2.5


    // Extended Tier 3 Detail
    physicalHtml += addFact("Underarm", bio.underarmHair);
    physicalHtml += addFact("Pubic Hair", bio.pubicHair);

    if (physicalHtml) {
        physicalHtml = `<div class="kp-group-title">Physical Stats</div>` + physicalHtml;
    }

    // --- C. Description (Tier 3 Only) ---
    let descHtml = "";
    if (tier >= 3 && bio.wiki_desc) {
        let desc = bio.wiki_desc;
        if (desc.length > 400) desc = desc.substring(0, 400) + "...";
        descHtml = `
            <h2 class="kp-section-title">Overview</h2>
            <div class="kp-desc">${desc}</div>
        `;
    } else {
        // For Tier 2/2.5 we use a generic header since we don't have a wiki text
        descHtml = `<h2 class="kp-section-title">About</h2>`;
    }

    // --- D. Social Profiles ---
    let socialHtml = '';
    let links = [];

    if (bio.twitter) {
        links.push(`
            <a href="https://twitter.com/${bio.twitter}" target="_blank" class="social-icon-btn">
                <div class="social-circle">𝕏</div>
                <span>X</span>
            </a>
        `);
    }

    links.push(`
        <a href="https://www.google.com/search?q=${bio.name}+actress" target="_blank" class="social-icon-btn">
            <div class="social-circle">G</div>
            <span>Google</span>
        </a>
    `);

    if (links.length > 0) {
        socialHtml = `
            <div class="kp-divider"></div>
            <div class="kp-profiles-header">Profiles</div>
            <div class="kp-social-grid">
                ${links.join('')}
            </div>
        `;
    }

    // --- Final Assembly ---
    return `
        <div class="kp-container">
            <div class="kp-images">
                <div class="kp-main-img">
                    <img src="${bio.avatar}" alt="${bio.name}">
                </div>
            </div>

            ${descHtml}
            
            ${personalHtml}
            
            ${physicalHtml ? '<div class="kp-divider" style="margin:15px 0;"></div>' + physicalHtml : ''}

            ${socialHtml}
        </div>
    `;
}

// --- SKELETON LOADER ---
export function renderLoader() {
    const items = Array(4)
        .fill(0)
        .map(
            () => `
    <div class="skeleton-item">
        <div class="skeleton-thumb"></div>
        <div class="skeleton-content">
            <div class="skeleton-line meta"></div>
            <div class="skeleton-line title"></div>
            <div class="skeleton-line desc"></div>
            <div class="skeleton-line desc-short"></div>
        </div>
    </div>
  `,
        )
        .join("");

    return `
    <div class="skeleton-wrapper">
        <div class="loading-status" id="loadingStatusText">Initializing search protocol...</div>
        ${items}
    </div>
  `;
}

export function renderError(message) {
    return `<div style="padding:20px;"><h3>Error</h3><p>${message}</p></div>`;
}

// --- 3. RECOMMENDATIONS (Dynamic) ---
export function renderActressRecommendations(profile, videos) {
    if (!profile || !videos || videos.length === 0) return "";

    // Row 1: Profile
    const profileHtml = `
        <div class="rec-profile-header">
            <img src="${profile.avatar}" class="rec-avatar" alt="${profile.name}">
            <div class="rec-info">
                 <div class="rec-name">${profile.name}</div>
                 <div class="rec-jpname">${profile.jpName || ''}</div>
            </div>
        </div>
    `;

    // Row 2: Horizontal Scroll
    const videosHtml = videos.map(v => {
        return `
            <div class="rec-video-card">
                 <a href="${v.generated_url || '#'}" target="_blank">
                    <img src="${v.image}" loading="lazy" class="rec-video-img" alt="${v.dvdid}">
                 </a>
                 <div class="rec-video-title" title="${v.title}">${v.dvdid}</div>
            </div>
        `;
    }).join('');

    return `
        <div class="kp-recommendations">
            <div class="kp-group-title">You might like these videos...</div>
            ${profileHtml}
            <div class="rec-video-scroll">
                ${videosHtml}
            </div>
        </div>
    `;
}