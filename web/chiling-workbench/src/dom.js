export function find(root, selector) {
  return root.querySelector(selector);
}

export function findAll(root, selector) {
  return Array.from(root.querySelectorAll(selector));
}

export function bindDelegatedClick(root, selector, handler) {
  root.addEventListener("click", (event) => {
    if (!event.target?.closest) return;

    const target = event.target.closest(selector);
    if (!target || !root.contains(target)) return;
    handler(event, target);
  });
}
