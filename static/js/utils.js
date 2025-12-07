export async function copyToClipboard(text, element) {
  try {
    await navigator.clipboard.writeText(text);
    element.classList.add("copied");
    setTimeout(() => element.classList.remove("copied"), 2000);
  } catch (err) {
    console.error("Failed to copy!", err);
  }
}

export function withTransition(updateCallback) {
  if (!document.startViewTransition) {
    updateCallback();
    return;
  }
  document.startViewTransition(updateCallback);
}

export function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return !isNaN(d) ? d.toLocaleDateString("en-US", { year: "numeric", month: "short" }) : "";
}
