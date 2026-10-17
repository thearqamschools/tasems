/* TASEMS staff screens: sidebar, branch picker and dropdowns. Every page works without this file;
   it only adds comfort (collapse, search, closing menus). No framework, no outside services. */
(function () {
  "use strict";
  var root = document.documentElement;
  var wide = window.matchMedia("(min-width: 64rem)");

  // ---------- Sidebar: collapse on wide screens (remembered), slide in on phones ----------
  var toggle = document.getElementById("sidebar-toggle");
  function remember(value) {
    try { localStorage.setItem("tasems.sidebar", value); } catch (e) { /* private mode: not remembered */ }
  }
  function syncExpanded() {
    if (!toggle) return;
    var open = wide.matches ? !root.classList.contains("sidebar-collapsed") : root.classList.contains("sidebar-open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      if (wide.matches) {
        var collapsed = root.classList.toggle("sidebar-collapsed");
        remember(collapsed ? "collapsed" : "open");
      } else {
        root.classList.toggle("sidebar-open");
      }
      syncExpanded();
    });
    wide.addEventListener("change", function () { root.classList.remove("sidebar-open"); syncExpanded(); });
    syncExpanded();
  }
  document.querySelectorAll("[data-close-sidebar]").forEach(function (el) {
    el.addEventListener("click", function () { root.classList.remove("sidebar-open"); syncExpanded(); });
  });

  // ---------- Dropdowns (<details data-dropdown>): close on outside click and Escape ----------
  var dropdowns = document.querySelectorAll("details[data-dropdown]");
  document.addEventListener("click", function (event) {
    dropdowns.forEach(function (d) { if (d.open && !d.contains(event.target)) d.open = false; });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    dropdowns.forEach(function (d) {
      if (d.open) { d.open = false; d.querySelector("summary").focus(); }
    });
    if (root.classList.contains("sidebar-open")) { root.classList.remove("sidebar-open"); syncExpanded(); }
  });

  // ---------- Branch picker: type to filter (350+ branches) ----------
  document.querySelectorAll(".branch-picker").forEach(function (picker) {
    var input = picker.querySelector("[data-branch-filter]");
    var empty = picker.querySelector("[data-branch-empty]");
    if (!input) return;
    picker.addEventListener("toggle", function () {
      if (picker.open) { input.value = ""; filter(); input.focus(); }
    });
    function filter() {
      var words = input.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
      var shown = 0;
      picker.querySelectorAll("[data-branch-group]").forEach(function (group) {
        var inGroup = 0;
        group.querySelectorAll("button[data-search]").forEach(function (button) {
          var text = button.getAttribute("data-search");
          var match = words.every(function (w) { return text.indexOf(w) !== -1; });
          button.parentElement.hidden = !match;
          if (match) inGroup++;
        });
        group.hidden = inGroup === 0;
        shown += inGroup;
      });
      if (empty) empty.hidden = shown !== 0;
    }
    input.addEventListener("input", filter);
    input.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;
      event.preventDefault();
      var first = picker.querySelector("li:not([hidden]) button[data-search]");
      if (first) first.click();
    });
  });
})();
