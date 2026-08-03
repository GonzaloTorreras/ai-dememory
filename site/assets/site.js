"use strict";

document.documentElement.classList.add("js");

for (const block of document.querySelectorAll("[data-copy-block]")) {
  const code = block.querySelector("code");
  if (!code) continue;

  const button = document.createElement("button");
  button.className = "copy-button";
  button.type = "button";
  button.textContent = "Copy";
  button.setAttribute("aria-label", "Copy commands to clipboard");

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(code.textContent.trim());
      button.textContent = "Copied";
      button.setAttribute("aria-label", "Commands copied to clipboard");
      window.setTimeout(() => {
        button.textContent = "Copy";
        button.setAttribute("aria-label", "Copy commands to clipboard");
      }, 1600);
    } catch {
      let selected = false;
      try {
        const selection = window.getSelection();
        if (selection) {
          const range = document.createRange();
          range.selectNodeContents(code);
          selection.removeAllRanges();
          selection.addRange(range);
          selected = true;
        }
      } catch {
        // The commands remain visible and keyboard-focusable without selection APIs.
      }
      button.textContent = selected ? "Selected" : "Select text";
      button.setAttribute(
        "aria-label",
        selected
          ? "Clipboard unavailable; commands selected"
          : "Clipboard unavailable; select commands manually",
      );
      code.parentElement?.focus();
    }
  });

  block.append(button);
}
