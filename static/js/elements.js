export const elements = {
  body: document.body,
  // Search Inputs
  searchInput: document.getElementById("searchInput"),
  searchBtn: document.getElementById("searchBtn"),
  resetBtn: document.getElementById("resetBtn"),

  // Headers & Panels
  standardSearch: document.getElementById("standardSearch"),
  similarContext: document.getElementById("similarContext"),
  toolsBtn: document.getElementById("toolsBtn"),
  helpBtn: document.getElementById("helpBtn"),
  toolsPanel: document.getElementById("toolsPanel"),
  loader: document.getElementById("loader"),
  searchMeta: document.getElementById("searchMeta"),
  resultsList: document.getElementById("resultsList"),
  backToTopBtn: document.getElementById("backToTop"),

  //main area
  knowledgePanel: document.getElementById("knowledgePanel"),

  // Similar Context Elements
  scImg: document.getElementById("scImg"),
  scId: document.getElementById("scId"),
  scTitle: document.getElementById("scTitle"),
  closeSimilarBtn: document.getElementById("closeSimilarBtn"),

  // Settings
  limitInput: document.getElementById("limitInput"),
  threshInput: document.getElementById("threshInput"),
  limitVal: document.getElementById("limitVal"),
  threshVal: document.getElementById("threshVal"),

  // Modals
  imageModal: document.getElementById("imageModal"),
  modalImg: document.getElementById("modalImg"),
  modalCaption: document.getElementById("modalCaption"),
  closeImgModalBtn: document.querySelector(".close-img-modal"),

  helpModal: document.getElementById("helpModal"),
  // Note: closeHelpModalBtn removed from here, handled in help.js
};
