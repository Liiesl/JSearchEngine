import { elements } from "./elements.js";
import { setResultsMode, updateMeta, startLoader, stopLoader } from "./ui.js"; // Import new functions
import { createResultCard, renderError, renderKnowledgePanel, createEntityHeader, renderActressRecommendations } from "./render.js";
import { withTransition } from "./utils.js";
import { closeWebSocket } from "./socket.js";

export async function performStandardSearch(
  query,
  limit,
  threshold,
  pushState = true,
  animate = true,
) {
  if (!query.trim()) return;

  closeWebSocket();

  const startLoadingState = () => {
    setResultsMode();
    elements.searchInput.value = query;
    elements.resetBtn.style.display = "block";
    elements.standardSearch.classList.remove("hidden");
    elements.similarContext.classList.add("hidden");
    window.scrollTo(0, 0);
    elements.searchMeta.classList.add("hidden");

    // START INTERACTIVE LOADER
    startLoader();
  };

  if (animate) withTransition(startLoadingState);
  else startLoadingState();

  if (pushState) {
    const url = new URL(window.location);
    url.pathname = "/search";
    url.searchParams.set("q", query);
    if (limit) url.searchParams.set("top_k", limit);
    if (threshold) url.searchParams.set("threshold", threshold);
    window.history.pushState({}, "", url);
  }

  const apiUrl = `/api/search?q=${encodeURIComponent(query)}&top_k=${limit}&threshold=${threshold}`;

  try {
    const response = await fetch(apiUrl);
    if (!response.ok) throw new Error("API Error");
    const data = await response.json();

    const renderNewContent = () => {
      stopLoader();

      const count = data.results.length;
      updateMeta(`About ${count} results <span style="margin: 0 10px">•</span> Mode: ${data.mode}`);

      elements.resultsList.innerHTML = "";
      elements.knowledgePanel.innerHTML = "";

      // Reset Sidebar Visibility
      elements.knowledgePanel.classList.add("hidden");
      elements.body.classList.remove("has-sidebar");

      if (count === 0) {
        elements.resultsList.innerHTML = `<p style="padding:20px;color:#bdc1c6;">No results found.</p>`;
        return;
      }

      const fragment = document.createDocumentFragment();

      data.results.forEach((item) => {
        // CHECK FOR BIO ITEM
        if (item.is_bio || item.data.type === 'bio') {
          const tier = item.data.tier || 0;

          // TIER 1+: Render "Mini Header" at top of results list
          if (tier >= 1) {
            fragment.appendChild(createEntityHeader(item.data));
          }

          // TIER 2+: Render Sidebar (Knowledge Panel)
          if (tier >= 2) {
            elements.knowledgePanel.innerHTML = renderKnowledgePanel(item.data);
            elements.knowledgePanel.classList.remove("hidden");
            elements.body.classList.add("has-sidebar");
          }

        } else {
          // Standard Video Card
          fragment.appendChild(createResultCard(item.data, item.sem_score));
        }
      });

      elements.resultsList.appendChild(fragment);
      if (data.mode === 'semantic') {
        // --- NEW: Check for Dominant Actresses (Multi-Actresses Support) ---
        const actressCountsTop10 = {};
        const actressCountsTop50 = {};
        const qualifyingActresses = new Set();

        data.results.forEach((item, index) => {
          // Skip bio items
          if (item.is_bio || (item.data && item.data.type === 'bio')) return;

          const row = item.data;
          if (row && row.actress_names) {
            const names = row.actress_names.split(",").map(n => n.trim());
            names.forEach(name => {
              if (!name) return;

              // Count for Top 10
              if (index < 10) {
                actressCountsTop10[name] = (actressCountsTop10[name] || 0) + 1;
                if (actressCountsTop10[name] >= 3) qualifyingActresses.add(name);
              }

              // Count for Top 50 (or total results if less)
              if (index < 50) {
                actressCountsTop50[name] = (actressCountsTop50[name] || 0) + 1;
                if (actressCountsTop50[name] >= 5) qualifyingActresses.add(name);
              }
            });
          }
        });

        if (qualifyingActresses.size > 0) {
          // Process each qualifying actress
          const promises = Array.from(qualifyingActresses).map(actressName => {
            return fetch(`/api/actress_top_videos?name=${encodeURIComponent(actressName)}`)
              .then(res => res.json())
              .then(recData => {
                if (recData.profile && recData.videos && recData.videos.length > 0) {
                  return recData;
                }
                return null;
              })
              .catch(err => {
                console.error(`Rec Error for ${actressName}:`, err);
                return null;
              });
          });

          Promise.all(promises).then(results => {
            const validResults = results.filter(r => r !== null);

            if (validResults.length > 0) {
              // If panel was hidden (no purely High Tier bio result), show it now
              if (elements.knowledgePanel.classList.contains("hidden")) {
                elements.knowledgePanel.classList.remove("hidden");
                elements.body.classList.add("has-sidebar");
              }

              const fragment = document.createDocumentFragment();
              validResults.forEach(recData => {
                const kpHtml = renderActressRecommendations(recData.profile, recData.videos);
                const div = document.createElement("div");
                div.innerHTML = kpHtml;
                fragment.appendChild(div);
              });
              elements.knowledgePanel.appendChild(fragment);
            }
          });
        }
      }
    };

    if (animate) withTransition(renderNewContent);
    else renderNewContent();
  } catch (error) {
    stopLoader(); // STOP LOADER ON ERROR
    elements.resultsList.innerHTML = renderError(error.message);
  }
}