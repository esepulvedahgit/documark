// Minimal JS: wires the CSRF token into every HTMX request (Django's CSRF
// cookie is readable by JS because CSRF_COOKIE_HTTPONLY = False) and shows
// a friendly message if an HTMX request fails outright.

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

document.body.addEventListener("htmx:configRequest", (event) => {
  const token = getCookie("csrftoken");
  if (token) {
    event.detail.headers["X-CSRFToken"] = token;
  }
});

document.body.addEventListener("htmx:responseError", (event) => {
  const target = event.detail.target;
  if (target) {
    target.innerHTML =
      '<div class="rounded-md bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">' +
      "Ocurrió un error al procesar la solicitud. Intenta nuevamente." +
      "</div>";
  }
});
