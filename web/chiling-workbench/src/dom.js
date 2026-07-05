export function find(root, selector) {
  return root.querySelector(selector);
}

export function findAll(root, selector) {
  return Array.from(root.querySelectorAll(selector));
}

export function bindDelegatedClick(root, selector, handler) {
  const listener = (event) => {
    const closestRoot = event.target?.closest ? event.target : event.target?.parentElement;
    if (!closestRoot?.closest) return;

    const target = closestRoot.closest(selector);
    if (!target || !root.contains(target)) return;
    handler(event, target);
  };

  root.addEventListener("click", listener);
  return () => root.removeEventListener("click", listener);
}
