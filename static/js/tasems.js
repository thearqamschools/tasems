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

  // ---------- Confirm before risky actions: <form data-confirm="…"> ----------
  // The page stays usable without JavaScript (the form simply submits). With it, a dialog asks first;
  // the form is then sent with the same button that was pressed, so its name/value is kept.
  var dialog = document.getElementById("confirm-dialog");
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches("form[data-confirm]") || form.dataset.confirmed === "1") return;
    event.preventDefault();
    var submitter = event.submitter || null;
    if (!dialog || typeof dialog.showModal !== "function") {
      if (window.confirm(form.dataset.confirm)) { form.dataset.confirmed = "1"; send(form, submitter); }
      return;
    }
    dialog.querySelector("[data-dialog-text]").textContent = form.dataset.confirm;
    var ok = dialog.querySelector("[data-dialog-ok]");
    ok.textContent = form.dataset.confirmButton || ok.dataset.defaultLabel;
    dialog.returnValue = "";
    dialog.onclose = function () {
      if (dialog.returnValue === "ok") { form.dataset.confirmed = "1"; send(form, submitter); }
    };
    dialog.showModal();
  });
  function send(form, submitter) {
    if (typeof form.requestSubmit === "function") form.requestSubmit(submitter || undefined);
    else form.submit();
  }

  // ---------- Stop double submissions (e.g. a payment saved twice) ----------
  document.addEventListener("submit", function (event) {
    var form = event.target;
    // Read attributes, not form.method/form.target: a field named "method" (e.g. payment method) hides them.
    var method = (form.getAttribute("method") || "get").toLowerCase();
    if (event.defaultPrevented || method !== "post" || form.getAttribute("target") === "_blank") return;
    if (form.dataset.sending === "1") { event.preventDefault(); return; }
    form.dataset.sending = "1";
    var button = event.submitter;
    if (button && button.classList.contains("button")) button.setAttribute("aria-busy", "true");
    // If the answer is a download (no new page), make the form usable again.
    setTimeout(function () { reset(form); }, 8000);
  });
  function reset(form) {
    delete form.dataset.sending;
    delete form.dataset.confirmed;
    form.querySelectorAll('[aria-busy="true"]').forEach(function (b) { b.removeAttribute("aria-busy"); });
  }
  // Coming back with the browser's Back button shows the page from memory: clear busy states.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) document.querySelectorAll("form").forEach(reset);
  });

  // ---------- Dashboards: "Hide amounts" (remembered on this browser) ----------
  var moneyToggle = document.querySelector("[data-money-toggle]");
  function setMoney(hidden) {
    root.classList.toggle("hide-money", hidden);
    if (!moneyToggle) return;
    moneyToggle.setAttribute("aria-pressed", hidden ? "true" : "false");
    moneyToggle.textContent = hidden ? moneyToggle.dataset.labelShow : moneyToggle.dataset.labelHide;
  }
  if (moneyToggle) {
    var hiddenBefore = false;
    try { hiddenBefore = localStorage.getItem("tasems.money") === "hidden"; } catch (e) { /* not remembered */ }
    setMoney(hiddenBefore);
    moneyToggle.addEventListener("click", function () {
      var hidden = !root.classList.contains("hide-money");
      setMoney(hidden);
      try { localStorage.setItem("tasems.money", hidden ? "hidden" : "shown"); } catch (e) { /* not remembered */ }
    });
  }

  // ---------- Charts: tooltip on hover and keyboard focus (values also in each chart's table) ----------
  document.querySelectorAll("[data-chart]").forEach(function (figure) {
    var tip = figure.querySelector(".chart-tip");
    if (!tip) return;
    var money = figure.classList.contains("money-chart");
    function show(bar) {
      var hiddenMoney = money && root.classList.contains("hide-money");
      tip.textContent = "";
      var value = document.createElement("strong");
      value.textContent = hiddenMoney ? "••••" : bar.dataset.tipValue;
      var label = document.createElement("span");
      label.textContent = bar.dataset.tipTitle + (bar.dataset.tipDetail && !hiddenMoney ? " · " + bar.dataset.tipDetail : "");
      tip.appendChild(value);
      tip.appendChild(label);
      var box = figure.getBoundingClientRect();
      var mark = (bar.querySelector(".chart-mark") || bar).getBoundingClientRect();
      tip.style.left = (mark.left + mark.width / 2 - box.left) + "px";
      tip.style.top = (Math.max(mark.top - box.top, 16) - 6) + "px";
      tip.hidden = false;
    }
    function hide() { tip.hidden = true; }
    figure.querySelectorAll(".chart-bar").forEach(function (bar) {
      bar.addEventListener("pointerenter", function () { show(bar); });
      bar.addEventListener("focus", function () { show(bar); });
      bar.addEventListener("pointerleave", hide);
      bar.addEventListener("blur", hide);
    });
  });

  // ---------- Setup → role form: show only the place chooser that matches "Where" ----------
  document.querySelectorAll("[data-scope-form]").forEach(function (form) {
    var select = form.querySelector('select[name$="scope"]');
    if (!select) return;
    function sync() {
      form.querySelectorAll("[data-scope-only]").forEach(function (box) {
        box.hidden = box.getAttribute("data-scope-only") !== select.value;
      });
    }
    select.addEventListener("change", sync);
    sync();
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
