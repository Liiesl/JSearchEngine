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

      // --- NEW: Check for Dominant Actress (>= 60%) ---
      const actressCounts = {};
      let totalVideos = 0;

      data.results.forEach((item) => {
        // Skip bio items
        if (item.is_bio || (item.data && item.data.type === 'bio')) return;

        totalVideos++;
        const row = item.data;
        if (row && row.actress_names) {
          const names = row.actress_names.split(",").map(n => n.trim());
          names.forEach(name => {
            if (name) actressCounts[name] = (actressCounts[name] || 0) + 1;
          });
        }
      });

      if (totalVideos > 0) {
        let dominantActress = null;
        // Check if any actress appears in >= 60% of videos
        for (const [name, count] of Object.entries(actressCounts)) {
          if (count / totalVideos >= 0.6) {
            dominantActress = name;
            break;
          }
        }

        if (dominantActress) {
          // Determine if we should append to existing panel or start new
          // If we already rendered a bio for this actress (Tier 2), we might duplicate info?
          // But the user said "do this after load complete" and "add functionality to knowledge panel".
          // If existing panel shows "About", this adds "You would like these video...".
          // So appending is correct.

          fetch(`/api/actress_top_videos?name=${encodeURIComponent(dominantActress)}`)
            .then(res => res.json())
            .then(recData => {
              if (recData.profile && recData.videos && recData.videos.length > 0) {
                const kpHtml = renderActressRecommendations(recData.profile, recData.videos);

                // If panel was hidden (no purely High Tier bio result), show it now
                if (elements.knowledgePanel.classList.contains("hidden")) {
                  elements.knowledgePanel.classList.remove("hidden");
                  elements.body.classList.add("has-sidebar");
                }

                const div = document.createElement("div");
                div.innerHTML = kpHtml;
                elements.knowledgePanel.appendChild(div);
              }
            })
            .catch(err => console.error("Rec Error:", err));
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