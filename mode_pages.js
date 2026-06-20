const API = "http://127.0.0.1:8765";
const page = document.body.dataset.page || "otaku";
const persona = page === "writing" ? "mira" : "soren";
const messages = document.querySelector("#modeMessages");
const form = document.querySelector("#modeForm");
const input = document.querySelector("#modeInput");

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function linkify(text) {
  return escapeHtml(text).replace(/https?:\/\/[^\s)>\]}"]+/g, url => `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`);
}

function addMessage(sender, text, role = "assistant") {
  const node = document.createElement("article");
  node.className = `mode-msg ${role}`;
  node.innerHTML = `<strong>${sender}</strong>${linkify(text)}`;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

async function sendModePrompt(prompt) {
  addMessage("You", prompt, "user");
  try {
    const res = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, message: prompt }),
    });
    const data = await res.json();
    addMessage(data.persona || "Antimony", data.reply || data.error || "No response.");
  } catch (error) {
    addMessage("System", `Could not reach Antimony API. Run open_web_assistant.bat first.\n${error.message}`);
  }
}

document.querySelectorAll("[data-prompt]").forEach(button => {
  button.addEventListener("click", () => sendModePrompt(button.dataset.prompt));
});

form?.addEventListener("submit", event => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendModePrompt(text);
});

addMessage("Antimony", page === "writing"
  ? "Writing Zone is ready. Choose a tool or write your request here."
  : "Otaku's Cloud is ready. Choose a tool or ask an anime question here.");
