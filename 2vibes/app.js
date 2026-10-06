const form = document.getElementById("lead-form");
const thanks = document.getElementById("thanks");
form?.addEventListener("submit", (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  const leads = JSON.parse(localStorage.getItem("2vibes-leads") || "[]");
  leads.push({ ...data, at: new Date().toISOString() });
  localStorage.setItem("2vibes-leads", JSON.stringify(leads));
  form.hidden = true;
  thanks.hidden = false;
});
