// Slips (e.g. Parent Tree) print as soon as they open; a slip opened in its own small window closes after printing.
window.addEventListener("load", function () {
  if (window.opener) {
    window.addEventListener("afterprint", function () { window.close(); });
  }
  setTimeout(function () { window.print(); }, 300);
});
