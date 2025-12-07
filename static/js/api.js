import { elements } from "./elements.js";
import { setResultsMode, updateMeta, startLoader, stopLoader } from "./ui.js"; // Import new functions
import { createResultCard, renderError } from "./render.js";
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
      stopLoader(); // STOP LOADER

      const count = data.results.length;
      updateMeta(
        `About ${count} results <span style="margin: 0 10px">•</span> Mode: ${data.mode}`,
      );

      if (count === 0) {
        elements.resultsList.innerHTML = `
            <div style="padding: 20px 0; color: #bdc1c6;">
                <p>No results found for <strong>${query}</strong>.</p>
                <p>Try lowering the 'Strictness'.</p>
            </div>`;
        return;
      }

      const fragment = document.createDocumentFragment();
      data.results.forEach((item) => {
        fragment.appendChild(createResultCard(item.data, item.sem_score));
      });
      // Clear skeleton before appending (though innerHTML set handles it mostly, this is safer)
      elements.resultsList.innerHTML = "";
      elements.resultsList.appendChild(fragment);
    };

    if (animate) withTransition(renderNewContent);
    else renderNewContent();
  } catch (error) {
    stopLoader(); // STOP LOADER ON ERROR
    elements.resultsList.innerHTML = renderError(error.message);
  }
}
