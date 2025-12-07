export const HELP_CONTENT = `
    <div class="modal-content doc-content">
        <span class="modal-close close-help-modal">&times;</span>

        <h2 style="margin-top: 0">Documentation</h2>

        <!-- 1. USER GUIDE -->
        <div class="doc-section">
            <h3>🔍 Search Guide</h3>
            <p>
                This engine uses <strong>Vector Embeddings</strong> to
                understand the <em>meaning</em> of your query, not just
                keyword matching.
            </p>

            <div class="doc-grid">
                <div class="doc-card">
                    <h4>Semantic Search</h4>
                    <p>Describe the scene or plot in English.</p>
                    <code>"Office lady romance plot"</code><br />
                    <code>"Action movie with rain scene"</code>
                </div>
                <div class="doc-card">
                    <h4>Exact ID Search</h4>
                    <p>
                        Enter a standard ID code to find exact matches.
                    </p>
                    <code>"ABC-123"</code><br />
                    <code>"ipz-999"</code>
                </div>
                <div class="doc-card">
                    <h4>Syntax: Deep Similarity</h4>
                    <p>
                        Force a vector similarity search for a specific
                        ID using the <code>id:</code> prefix.
                    </p>
                    <code>"id:abc-123"</code>
                </div>
                <div class="doc-card">
                    <h4>Actress Boost</h4>
                    <p>
                        If a known actress name is detected, results
                        featuring her are automatically boosted in the
                        ranking algorithm.
                    </p>
                </div>
            </div>
        </div>

        <hr class="doc-divider" />

        <!-- 2. UI INTERACTIVITY -->
        <div class="doc-section">
            <h3>🖱️ Interface Features</h3>
            <p>Hidden features to make browsing faster.</p>
            <ul
                style="
                    margin-left: 20px;
                    margin-top: 10px;
                    line-height: 1.8;
                    color: #bdc1c6;
                "
            >
                <li>
                    <strong>One-Click Copy:</strong> Click on the video
                    ID code (e.g., <u>ABC-123</u>) in any result to
                    instantly copy it to your clipboard.
                </li>
                <li>
                    <strong>Image Zoom:</strong> Click on any thumbnail
                    image to view the high-resolution cover art in a
                    modal window.
                </li>
                <li>
                    <strong>Find Similar Button:</strong> Every result
                    has a "Find Similar" button. This takes the
                    mathematical vector of that specific result and
                    finds its nearest neighbors in the database.
                </li>
            </ul>
        </div>

        <hr class="doc-divider" />

        <!-- 3. URL PARAMETERS -->
        <div class="doc-section">
            <h3>🔗 URL Parameters</h3>
            <p>
                You can share search results or bookmark specific
                configurations using these URL parameters.
            </p>

            <table class="doc-table">
                <thead>
                    <tr>
                        <th>Parameter</th>
                        <th>Value</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><code>q</code></td>
                        <td>String</td>
                        <td>
                            The search query (e.g.,
                            <code>?q=office</code>).
                        </td>
                    </tr>
                    <tr>
                        <td><code>top_k</code></td>
                        <td>Integer (10-50)</td>
                        <td>
                            Limits the number of results returned.
                            Default is <strong>20</strong>.
                        </td>
                    </tr>
                    <tr>
                        <td><code>threshold</code></td>
                        <td>Float (0.0-1.0)</td>
                        <td>
                            Strictness filter. <strong>0.65</strong> is
                            default. Higher = stricter matching.
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <hr class="doc-divider" />

        <!-- 4. API REFERENCE -->
        <div class="doc-section">
            <h3>⚡ API Reference</h3>
            <p>
                The backend exposes JSON endpoints for programmatic
                access.
            </p>

            <h4>1. Search Endpoint</h4>
            <code class="code-block">GET /api/search</code>
            <p>Returns semantic matches for a text query.</p>
            <ul class="api-list">
                <li>
                    <strong>Params:</strong> <code>q</code>,
                    <code>top_k</code>, <code>threshold</code>
                </li>
                <li>
                    <strong>Response:</strong> JSON object containing
                    <code>results</code> array and search
                    <code>mode</code>.
                </li>
            </ul>

            <h4>2. Similarity Endpoint</h4>
            <code class="code-block">GET /api/similar</code>
            <p>
                Finds items mathematically similar to a specific video
                vector.
            </p>
            <ul class="api-list">
                <li>
                    <strong>Params:</strong>
                    <code>dvd_id</code> (Required), <code>top_k</code>,
                    <code>threshold</code>
                </li>
                <li>
                    <strong>Example:</strong>
                    <code>/api/similar?dvd_id=ABC-123</code>
                </li>
            </ul>
        </div>

        <div class="doc-footer">
            <p>
                Powered by <strong>Lancedb</strong> &
                <strong>Sentence-Transformers</strong>
            </p>
        </div>
    </div>
`;

/**
 * Injects the help content into the container and attaches the close listener.
 * @param {HTMLElement} container - The #helpModal element
 * @param {Function} onClose - The function to call when close is clicked
 */
export function initHelpModal(container, onClose) {
  if (!container) return;

  // Inject HTML
  container.innerHTML = HELP_CONTENT;

  // Attach event listener to the newly created close button
  const closeBtn = container.querySelector(".close-help-modal");
  if (closeBtn) {
    closeBtn.addEventListener("click", onClose);
  }
}
