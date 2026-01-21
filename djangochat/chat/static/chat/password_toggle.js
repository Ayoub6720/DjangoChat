(function () {
  function setupToggle(input) {
    if (!input || input.dataset.pwToggle === "1") {
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "pw-field";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-secondary pw-toggle-btn";
    button.setAttribute("aria-label", "Afficher le mot de passe");
    const eyeIcon =
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/>' +
      '<circle cx="12" cy="12" r="3"/>' +
      "</svg>";
    const eyeOffIcon =
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M17.94 17.94A10.5 10.5 0 0 1 12 19c-7 0-11-7-11-7a21.77 21.77 0 0 1 5.06-6.94"/>' +
      '<path d="M9.9 4.24A10.4 10.4 0 0 1 12 4c7 0 11 7 11 7a21.77 21.77 0 0 1-3.87 5.11"/>' +
      '<path d="M14.12 14.12a3 3 0 0 1-4.24-4.24"/>' +
      '<path d="M1 1l22 22"/>' +
      "</svg>";
    button.innerHTML =
      '<span class="pw-toggle-icon" aria-hidden="true">' +
      eyeIcon +
      "</span>";
    button.setAttribute("aria-pressed", "false");

    button.addEventListener("click", function () {
      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      const icon = button.querySelector(".pw-toggle-icon");
      if (icon) {
        icon.innerHTML = isHidden ? eyeOffIcon : eyeIcon;
      }
      button.setAttribute(
        "aria-label",
        isHidden ? "Masquer le mot de passe" : "Afficher le mot de passe"
      );
      button.setAttribute("aria-pressed", isHidden ? "true" : "false");
    });

    const parent = input.parentElement;
    if (!parent) {
      return;
    }

    parent.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    wrapper.appendChild(button);
    input.dataset.pwToggle = "1";
  }

  document.addEventListener("DOMContentLoaded", function () {
    const inputs = document.querySelectorAll('input[type="password"]');
    inputs.forEach(setupToggle);
  });
})();
