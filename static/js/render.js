import { formatDate } from "./utils.js";

// ... existing createResultCard function ...

export function createResultCard(item, score) {
  // ... existing code ...
  // (Keep the existing function exactly as it was)
  const row = item.data || item;
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

// --- NEW FUNCTION ---
export function renderLoader() {
  // Create 3 skeleton items
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
