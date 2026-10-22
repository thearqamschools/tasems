// Parent portal: lets the phone install the portal as an app and show a page when there is no internet.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/parents/sw.js", { scope: "/parents/" }).catch(function () {});
  });
}
