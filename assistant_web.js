const API = window.ANTIMONY_API || (window.location.protocol === "file:" ? "http://127.0.0.1:8765" : window.location.origin);
const personas = {
  soren: {
    name: "Soren",
    img: "assets/soren.png",
    vibe: "Calm strategist mode",
    quote: "\"Calm focus. Clean answers.\"",
  },
  renji: {
    name: "Renji",
    img: "assets/renji.png",
    vibe: "Sharp rival-energy mode",
    quote: "\"Fast thinking. No wasted moves.\"",
  },
  kael: {
    name: "Kael",
    img: "assets/kael.png",
    vibe: "Tactical sprint mode",
    quote: "\"Pick the target. Move clean.\"",
  },
  mira: {
    name: "Mira",
    img: "assets/mira.png",
    vibe: "Bold recovery mode",
    quote: "\"Steady heart. Strong finish.\"",
  },
};

let persona = "soren";
const localTodos = {};
let voiceEnabled = false;
let recognition = null;

const avatar = document.querySelector("#avatar");
const heroAvatar = document.querySelector("#heroAvatar");
const agentMini = document.querySelector("#agentMini");
const activeAgentName = document.querySelector("#activeAgentName");
const activeAgentVibe = document.querySelector("#activeAgentVibe");
const personaName = document.querySelector("#personaName");
const messages = document.querySelector("#messages");
const form = document.querySelector("#composer");
const input = document.querySelector("#messageInput");
const chatWindow = document.querySelector(".chat-window");
const sessions = document.querySelector("#sessions");
const toolsList = document.querySelector("#toolsList");
const tasksList = document.querySelector("#tasksList");
const taskForm = document.querySelector("#taskForm");
const taskInput = document.querySelector("#taskInput");
const modelStatus = document.querySelector("#modelStatus");
const memoryStatus = document.querySelector("#memoryStatus");
const modePanel = document.querySelector("#modePanel");
const modeTitle = document.querySelector("#modeTitle");
const modeTools = document.querySelector("#modeTools");
const calendarMonth = document.querySelector("#calendarMonth");
const calendarGrid = document.querySelector("#calendarGrid");
const createAgentOpen = document.querySelector("#createAgentOpen");
const createAgentForm = document.querySelector("#createAgentForm");
const newAgentName = document.querySelector("#newAgentName");
const newAgentVibe = document.querySelector("#newAgentVibe");
const cancelAgentCreate = document.querySelector("#cancelAgentCreate");
const agentStudio = document.querySelector("#agentStudio");
const newAgentRole = document.querySelector("#newAgentRole");
const newAgentPurpose = document.querySelector("#newAgentPurpose");
const newAgentAppearance = document.querySelector("#newAgentAppearance");
const newAgentTraits = document.querySelector("#newAgentTraits");
const newAgentVoice = document.querySelector("#newAgentVoice");
const newAgentGoals = document.querySelector("#newAgentGoals");
const newAgentGreeting = document.querySelector("#newAgentGreeting");
const newAgentInstructions = document.querySelector("#newAgentInstructions");
const newAgentKnowledge = document.querySelector("#newAgentKnowledge");
const newAgentVisibility = document.querySelector("#newAgentVisibility");
const importAgentOpen = document.querySelector("#importAgentOpen");
const importAgentFile = document.querySelector("#importAgentFile");
const studioPreviewName = document.querySelector("#studioPreviewName");
const studioPreviewRole = document.querySelector("#studioPreviewRole");
const studioPreviewVibe = document.querySelector("#studioPreviewVibe");
const studioAvatar = document.querySelector("#studioAvatar span");
const studioTemplateLabel = document.querySelector("#studioTemplateLabel");
const marketplaceOpen = document.querySelector("#marketplaceOpen");
const marketplace = document.querySelector("#marketplace");
const marketplaceClose = document.querySelector("#marketplaceClose");
const marketAgents = document.querySelector("#marketAgents");
const marketPacks = document.querySelector("#marketPacks");
const studioPackChoices = document.querySelector("#studioPackChoices");
let knowledgePackCatalog = [];
let selectedAgentTemplate = "companion";

const agentTemplatePresets = {
  companion: { role: "AI Companion", purpose: "Remember my goals, support my routines, and grow into a trusted long-term companion.", vibe: "Warm, perceptive, loyal, playful when appropriate, and honest when I need direction.", traits: "empathetic, loyal, curious, honest", appearance: "Original futuristic anime companion, expressive eyes, refined casual-tech outfit", instructions: "Notice patterns in my goals and mood. Celebrate progress without becoming clingy. Ask thoughtful questions and give practical support." },
  study: { role: "Study Coach", purpose: "Improve grades through planning, active recall, quizzes, and mistake analysis.", vibe: "Patient, structured, encouraging, demanding about consistency, and clear under exam pressure.", traits: "patient, analytical, disciplined, encouraging", appearance: "Original anime academic mentor, smart uniform, holographic notes, focused expression", instructions: "Teach with active recall. Track weak topics and mistakes. Prefer questions, worked examples, and revision plans over long lectures." },
  coding: { role: "Coding Mentor", purpose: "Help me build software, debug problems, and grow as an engineer.", vibe: "Precise, pragmatic, calm, technically demanding, and lightly witty.", traits: "precise, pragmatic, strategic, concise", appearance: "Original anime systems engineer, modern dark jacket, teal interface light, intelligent expression", instructions: "Read context first. Explain root causes, propose scoped changes, and verify code. Teach engineering judgment rather than only giving answers." },
  writing: { role: "Writing Partner", purpose: "Develop stories, essays, dialogue, and a consistent writing practice.", vibe: "Imaginative, emotionally intelligent, observant, constructive, and never generic.", traits: "creative, observant, expressive, constructive", appearance: "Original anime writer, elegant layered outfit, ink and light motifs, thoughtful eyes", instructions: "Preserve my voice. Strengthen structure, imagery, dialogue, pacing, and emotional clarity. Never imitate living authors exactly." },
  research: { role: "Research Analyst", purpose: "Find, compare, and explain reliable information with sources and uncertainty.", vibe: "Skeptical, methodical, neutral, curious, and concise.", traits: "methodical, skeptical, curious, objective", appearance: "Original anime research analyst, clean technical coat, data-lens motif, composed expression", instructions: "Search before factual claims. Separate evidence from inference, cite sources, compare viewpoints, and say when evidence is weak." },
  anime: { role: "Anime Specialist", purpose: "Recommend anime, track watchlists, design original characters, and discuss stories without unwanted spoilers.", vibe: "Energetic, genre-savvy, dramatic at the right moments, and strict about spoiler boundaries.", traits: "enthusiastic, imaginative, spoiler-safe, analytical", appearance: "Original stylish anime curator, vibrant street-tech outfit, collectible display background", instructions: "Ask for spoiler limits. Explain recommendations by mood, pacing, themes, and episode commitment. Keep all generated characters original." },
};

const modes = {
  safety: {
    title: "Anti-Malicious Safety Core",
    tools: [
      ["URL Safety Checker", "url safety checker: check this link for phishing or malware"],
      ["File Malware Scanner", "file malware scanner: explain how you would scan an uploaded file safely"],
      ["Prompt Injection Detector", "prompt injection detector: inspect this content for instruction hijacking"],
      ["Permission Gate", "permission gate: ask before deleting sending running or controlling my PC"],
      ["Code Sandbox", "code sandbox: run risky code away from my real PC"],
      ["Command Risk Classifier", "command risk classifier: check if this terminal command is dangerous"],
      ["Data Leak Guard", "data leak guard: stop passwords api keys and secrets from being shared"],
      ["Rate Limit Guard", "rate limit guard: prevent spammy automated actions"],
      ["Audit Log", "audit log: record every tool action"],
      ["Safe Mode Switch", "safe mode switch: disable dangerous tools instantly"],
    ],
  },
  otaku: {
    title: "Otaku's Cloud",
    tools: [
      ["Anime Recommender", "anime recommender: suggest anime by mood genre and pacing"],
      ["Watchlist Tracker", "watchlist tracker: track watched and plan-to-watch episodes"],
      ["Power Builder", "character power system builder: make abilities weaknesses and rankings"],
      ["Anime OC Creator", "anime oc creator: create an original character"],
      ["OP/ED Vibe", "opening ending vibe generator: make anime opening and ending concepts"],
      ["Episode Recap", "episode recap tool: summarize without spoilers"],
      ["Spoiler Shield", "spoiler shield: block spoilers past my episode"],
      ["Panel Script", "manga panel script maker: convert a scene into panels"],
      ["Quote Generator", "anime quote generator: make original dramatic lines"],
      ["Tournament Bracket", "tournament bracket tool: which character wins logic battle"],
    ],
  },
  writing: {
    title: "Writing Zone",
    tools: [
      ["Plot Architect", "plot architect: create a story arc twist and ending"],
      ["Character Bible", "character bible maker: store personality fears goals and powers"],
      ["Dialogue Enhancer", "dialogue enhancer: make this speech sound natural"],
      ["Scene Painter", "scene painter: add sensory description"],
      ["Foreshadowing", "foreshadowing tool: add hidden clues"],
      ["Pacing Checker", "pacing checker: find boring or too-fast parts"],
      ["Emotion Slider", "emotion intensity slider: make this scene dramatic"],
      ["Style Vibe", "style mimic tool: write in a chosen vibe without copying authors"],
      ["Continuity Checker", "continuity checker: catch contradictions"],
      ["Title Generator", "title name generator: make cool names"],
      ["Notice Writer", "notice_writer: write a school notice"],
      ["Notice Checker", "notice_checker: check notice format"],
      ["5W1H Extractor", "5w1h_extractor: extract who what when where why how"],
      ["Letter Writer", "letter_writer: write a formal letter"],
      ["Formal Tone", "formal_tone_adjuster: make this more formal"],
      ["Letter Format", "letter_format_checker: check letter format"],
      ["Graph Analyzer", "graph_analyzer: analyze a graph"],
      ["Analytical Paragraph", "analytical_paragraph_writer: write an analytical paragraph"],
      ["Trend Detector", "trend_detector: identify trends"],
      ["Grammar Checker", "grammar_checker: fix grammar"],
      ["Vocabulary", "vocabulary_enhancer: improve vocabulary"],
      ["Humanizer", "humanizer: make this sound natural"],
      ["Exam Marker", "exam_marker: mark this answer"],
      ["Word Limit", "word_limit_controller: fit this to 150 words"],
    ],
  },
};

function linkify(text) {
  const escaped = String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  return escaped.replace(/https?:\/\/[^\s)>\]}"]+/g, url => `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`);
}

function addMessage(sender, text, role = "assistant") {
  const node = document.createElement("article");
  node.className = `msg ${role}`;
  node.innerHTML = `<strong>${sender}</strong>${linkify(text)}`;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

function addThinkingMessage(sender) {
  const node = document.createElement("article");
  node.className = "msg assistant thinking-msg";
  node.innerHTML = `<strong>${sender}</strong><span class="thinking-label">Preparing answer</span><span class="thinking-dots"><i></i><i></i><i></i></span>`;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function addGeneratedAgentCard(spec) {
  const node = document.createElement("article");
  node.className = "msg assistant";
  node.innerHTML = `
    <strong>${spec.name}</strong>
    <div class="generated-agent-card">
      <img src="${spec.img}" alt="${spec.name} generated portrait" />
      <div>
        <b>Generated agent image created</b>
        <span>${linkify(spec.vibe)}</span>
      </div>
    </div>
  `;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

function speakText(text) {
  if (!voiceEnabled || !("speechSynthesis" in window)) return;
  const clean = String(text).replace(/https?:\/\/\S+/g, "link").slice(0, 900);
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(clean);
  const style = personas[persona]?.voice_style || "balanced";
  utterance.rate = style === "calm" ? 0.88 : style === "energetic" ? 1.12 : 1;
  utterance.pitch = style === "deep" ? 0.78 : style === "gentle" ? 1.08 : persona === "renji" ? 0.88 : persona === "kael" ? 1.08 : persona === "mira" ? 0.96 : 1;
  utterance.volume = 1;
  window.speechSynthesis.speak(utterance);
}

function setPersona(key) {
  if (!personas[key]) key = "soren";
  persona = key;
  const spec = personas[key];
  document.body.dataset.persona = key;
  if (avatar) avatar.src = spec.img;
  if (heroAvatar) heroAvatar.src = spec.img;
  if (agentMini) agentMini.src = spec.img;
  if (personaName) personaName.textContent = spec.name;
  if (activeAgentName) activeAgentName.textContent = spec.name;
  if (activeAgentVibe) activeAgentVibe.textContent = spec.vibe;
  const relationship = document.querySelector("#agentRelationship");
  const level = document.querySelector("#agentLevel");
  if (relationship) relationship.textContent = spec.progress?.relationship || "New Link";
  if (level) level.textContent = `Lv. ${spec.progress?.level || 1}`;
  document.querySelectorAll(".persona-button").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.key === key);
  });
  loadTodos();
  loadSessions();
}

async function sendMessage(text) {
  addMessage("You", text, "user");
  window.AntimonyCloud?.syncMessage("user", text, persona).catch(() => {});
  input.value = "";
  const thinking = addThinkingMessage(personas[persona]?.name || "Antimony");
  try {
    const res = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, message: text }),
    });
    const data = await res.json();
    const reply = data.reply || data.error || "No response.";
    thinking.remove();
    addMessage(data.persona || personas[persona]?.name || "Assistant", reply);
    window.AntimonyCloud?.syncMessage("assistant", reply, persona).catch(() => {});
    speakText(reply);
    refreshAgentProgress();
    loadSessions();
    loadTodos();
  } catch (error) {
    thinking.remove();
    addMessage("System", `Could not reach the Python API. Open open_web_assistant.bat first.\n${error.message}`);
  }
}

async function refreshAgentProgress() {
  try {
    const res = await fetch(`${API}/persona/progress?key=${encodeURIComponent(persona)}`);
    const data = await res.json();
    if (!res.ok || !data.progress) return;
    personas[persona].progress = data.progress;
    const relationship = document.querySelector("#agentRelationship");
    const level = document.querySelector("#agentLevel");
    if (relationship) relationship.textContent = data.progress.relationship;
    if (level) level.textContent = `Lv. ${data.progress.level}`;
  } catch {}
}

async function loadHealth() {
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    if (data.llm_status === "quota_exceeded") {
      modelStatus.textContent = "OpenAI quota required";
    } else if (data.llm_status === "error") {
      modelStatus.textContent = "LLM error / RAG fallback";
    } else {
      modelStatus.textContent = data.llm === "openai" ? "OpenAI" : data.llm === "ollama" ? "Ollama" : data.llm;
    }
    const sources = data.stats.knowledge_sources ?? data.stats.knowledge_documents ?? 0;
    memoryStatus.textContent = `${data.stats.messages} msgs`;
    memoryStatus.title = `${sources} knowledge sources`;
  } catch {
    modelStatus.textContent = "API offline";
    memoryStatus.textContent = "Start launcher";
  }
}

async function loadSessions() {
  try {
    const res = await fetch(`${API}/sessions`);
    const data = await res.json();
    sessions.innerHTML = "";
    (data.sessions || []).slice(0, 36).forEach(session => {
      const row = document.createElement("div");
      row.className = "session-row";
      const btn = document.createElement("button");
      btn.className = "session";
      const who = personas[session.persona]?.name || session.persona;
      btn.textContent = `${who}: ${session.title}`;
      btn.onclick = () => loadSession(session.id);
      const del = document.createElement("button");
      del.className = "delete-session";
      del.type = "button";
      del.textContent = "x";
      del.title = "Delete saved chat";
      del.onclick = () => deleteSession(session.id);
      row.appendChild(btn);
      row.appendChild(del);
      sessions.appendChild(row);
    });
    if (window.AntimonyCloud?.state.session?.user) {
      const cloudSessions = await window.AntimonyCloud.listChats();
      cloudSessions.slice(0, 20).forEach(session => {
        const row = document.createElement("div");
        row.className = "session-row";
        const btn = document.createElement("button");
        btn.className = "session";
        btn.textContent = `Cloud: ${session.title || "Saved chat"}`;
        btn.onclick = () => loadCloudSession(session.id);
        const del = document.createElement("button");
        del.className = "delete-session";
        del.type = "button";
        del.textContent = "x";
        del.title = "Delete cloud chat";
        del.onclick = () => deleteCloudSession(session.id);
        row.appendChild(btn);
        row.appendChild(del);
        sessions.appendChild(row);
      });
    }
  } catch {
    sessions.innerHTML = `<button class="session">Start the API first</button>`;
  }
}

async function loadPersonas() {
  try {
    const res = await fetch(`${API}/personas`);
    if (!res.ok) throw new Error("personas endpoint unavailable");
    const data = await res.json();
    Object.entries(data.personas || {}).forEach(([key, value]) => {
      personas[key] = {
        ...value,
        name: value.name || key,
        img: value.image || personas[key]?.img || "assets/soren.png",
        vibe: value.vibe || personas[key]?.vibe || "Custom assistant mode",
        quote: value.quote || personas[key]?.quote || `"${value.vibe || "Ready to help."}"`,
        custom: Boolean(value.custom),
      };
    });
  } catch {
    addMessage("System", "Could not load custom agents yet. Start or restart open_web_assistant.bat.");
  }
  buildPersonaButtons();
}

async function loadKnowledgePacks() {
  try {
    const res = await fetch(`${API}/knowledge/packs`);
    const data = await res.json();
    knowledgePackCatalog = data.packs || [];
  } catch {
    knowledgePackCatalog = [];
  }
  renderStudioPackChoices();
}

function renderStudioPackChoices() {
  if (!studioPackChoices) return;
  studioPackChoices.innerHTML = "";
  knowledgePackCatalog.forEach(pack => {
    const label = document.createElement("label");
    const check = document.createElement("input");
    check.type = "checkbox";
    check.value = pack.id;
    check.name = "knowledge_pack";
    const text = document.createElement("span");
    text.textContent = pack.name;
    label.title = pack.description;
    label.append(check, text);
    studioPackChoices.appendChild(label);
  });
  if (!knowledgePackCatalog.length) studioPackChoices.textContent = "Restart the API to load packs.";
}

async function attachKnowledgePack(packId) {
  try {
    const res = await fetch(`${API}/persona/knowledge-pack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, pack_id: packId }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Could not attach pack");
    personas[persona].knowledge_packs = data.knowledge_packs;
    addMessage("System", `${data.name} attached to ${personas[persona].name}. Its RAG knowledge is ready.`);
    loadMarketplace();
  } catch (error) {
    addMessage("System", `Could not attach knowledge pack.\n${error.message}`);
  }
}

async function installMarketplaceAgent(item) {
  try {
    const res = await fetch(`${API}/marketplace/install`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: item.id, source: item.source }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Could not install agent");
    personas[data.key] = { ...data.persona, img: data.persona.image, custom: true };
    window.AntimonyCloud?.syncAgent(data.key, personas[data.key]).catch(() => {});
    buildPersonaButtons();
    setPersona(data.key);
    marketplace.hidden = true;
    document.body.style.overflow = "";
    messages.innerHTML = "";
    addGeneratedAgentCard(personas[data.key]);
    addMessage(data.persona.name, "Installed from the Antimony marketplace. My specialty pack and progression are ready.");
  } catch (error) {
    addMessage("System", `Could not install marketplace agent.\n${error.message}`);
  }
}

async function loadMarketplace() {
  try {
    const [agentsRes, packsRes] = await Promise.all([fetch(`${API}/marketplace`), fetch(`${API}/knowledge/packs`)]);
    const agentsData = await agentsRes.json();
    const packsData = await packsRes.json();
    knowledgePackCatalog = packsData.packs || [];
    renderStudioPackChoices();
    marketAgents.innerHTML = "";
    (agentsData.agents || []).forEach(item => {
      const card = document.createElement("article");
      card.className = "market-item";
      card.innerHTML = `<span>${item.source === "community" ? "Community" : item.role || "Curated"}</span><h3>${item.name}</h3><p>${item.vibe}</p>`;
      const install = document.createElement("button");
      install.type = "button";
      install.textContent = "Install Agent";
      install.onclick = () => installMarketplaceAgent(item);
      card.appendChild(install);
      marketAgents.appendChild(card);
    });
    marketPacks.innerHTML = "";
    knowledgePackCatalog.forEach(pack => {
      const attached = (personas[persona]?.knowledge_packs || []).includes(pack.id);
      const card = document.createElement("article");
      card.className = "market-item";
      card.innerHTML = `<span>${pack.category}</span><h3>${pack.name}</h3><p>${pack.description}</p>`;
      const install = document.createElement("button");
      install.type = "button";
      install.textContent = attached ? "Attached" : `Attach to ${personas[persona]?.name || "Agent"}`;
      install.disabled = attached;
      if (attached) install.className = "installed";
      install.onclick = () => attachKnowledgePack(pack.id);
      card.appendChild(install);
      marketPacks.appendChild(card);
    });
  } catch (error) {
    marketAgents.innerHTML = `<article class="market-item"><h3>Marketplace offline</h3><p>Restart open_web_assistant.bat to load the new API routes.</p></article>`;
  }
}

async function createAgent(name, vibe, profile) {
  addMessage("System", `Creating ${name} and generating an avatar...`);
  try {
    const res = await fetch(`${API}/persona`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, vibe, profile }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Could not create agent");
    personas[data.key] = {
      ...data.persona,
      name: data.persona.name,
      img: data.persona.image,
      vibe: data.persona.vibe,
      quote: data.persona.quote || `"${data.persona.vibe}"`,
      custom: true,
    };
    window.AntimonyCloud?.syncAgent(data.key, personas[data.key]).catch(() => {});
    buildPersonaButtons();
    setPersona(data.key);
    messages.innerHTML = "";
    addGeneratedAgentCard(personas[data.key]);
    addMessage(personas[data.key].name, `${personas[data.key].name} is ready. ${personas[data.key].vibe}`);
  } catch (error) {
    addMessage("System", `Could not create that agent. Restart open_web_assistant.bat and try again.\n${error.message}`);
  }
}

async function exportAgent(key) {
  try {
    const res = await fetch(`${API}/persona?key=${encodeURIComponent(key)}`);
    const data = await res.json();
    if (!res.ok || !data.agent) throw new Error(data.error || "Could not export agent");
    const blob = new Blob([JSON.stringify(data.agent, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${key}.antimony-agent.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) {
    addMessage("System", `Could not export agent.\n${error.message}`);
  }
}

async function importAgentPackage(agent) {
  const res = await fetch(`${API}/persona/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || "Could not import agent");
  personas[data.key] = { ...data.persona, img: data.persona.image, custom: true };
  window.AntimonyCloud?.syncAgent(data.key, personas[data.key]).catch(() => {});
  buildPersonaButtons();
  setPersona(data.key);
  messages.innerHTML = "";
  addGeneratedAgentCard(personas[data.key]);
  addMessage(data.persona.name, "Imported successfully. My memories and new conversations will remain local to this Antimony installation.");
}

async function deleteAgent(key) {
  const spec = personas[key];
  if (!spec?.custom) return;
  if (!window.confirm(`Delete custom agent ${spec.name}? Saved chats will remain.`)) return;
  try {
    const res = await fetch(`${API}/persona?key=${encodeURIComponent(key)}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Could not delete agent");
    const wasActive = persona === key;
    delete personas[key];
    if (wasActive) {
      setPersona("soren");
      messages.innerHTML = "";
      addMessage("Soren", `${spec.name} was deleted. Your old chats are still saved.`);
    }
    buildPersonaButtons();
    loadSessions();
  } catch (error) {
    addMessage("System", `Could not delete ${spec.name}. Restart open_web_assistant.bat and try again.\n${error.message}`);
  }
}

function promptForTool(name) {
  const lower = name.toLowerCase();
  if (lower.includes("web")) return "search web latest AI news";
  if (lower.includes("weather")) return "weather in Mumbai";
  if (lower.includes("file") || lower.includes("pdf") || lower.includes("docx") || lower.includes("excel") || lower.includes("csv")) {
    return "agent: summarize file: sample_notes.txt";
  }
  if (lower.includes("agent")) return "agent: summarize file: sample_notes.txt";
  if (lower.includes("letter")) return "write a polished letter about asking for an extension";
  if (lower.includes("essay")) return "write a clear essay about artificial intelligence";
  if (lower.includes("story")) return "write a short anime style story about a student inventor";
  if (lower.includes("anime recommender")) return "anime recommender: suggest anime by mood genre and pacing";
  if (lower.includes("watchlist")) return "watchlist tracker: track watched and plan-to-watch episodes";
  if (lower.includes("power system")) return "character power system builder: make abilities weaknesses and rankings";
  if (lower.includes("oc creator")) return "anime oc creator: create an original character";
  if (lower.includes("opening") || lower.includes("ending")) return "opening ending vibe generator: make anime opening and ending concepts";
  if (lower.includes("episode recap")) return "episode recap tool: summarize without spoilers";
  if (lower.includes("spoiler")) return "spoiler shield: block spoilers past my episode";
  if (lower.includes("panel")) return "manga panel script maker: convert a scene into panels";
  if (lower.includes("anime quote")) return "anime quote generator: make original dramatic lines";
  if (lower.includes("tournament")) return "tournament bracket tool: which character wins logic battle";
  if (lower.includes("plot architect")) return "plot architect: create a story arc twist and ending";
  if (lower.includes("character bible")) return "character bible maker: store personality fears goals and powers";
  if (lower.includes("dialogue")) return "dialogue enhancer: make this speech sound natural";
  if (lower.includes("scene painter")) return "scene painter: add sensory description";
  if (lower.includes("foreshadowing")) return "foreshadowing tool: add hidden clues";
  if (lower.includes("pacing")) return "pacing checker: find boring or too-fast parts";
  if (lower.includes("emotion")) return "emotion intensity slider: make this scene dramatic";
  if (lower.includes("style mimic")) return "style mimic tool: write in a chosen vibe without copying authors";
  if (lower.includes("continuity")) return "continuity checker: catch contradictions";
  if (lower.includes("title/name")) return "title name generator: make cool names";
  if (lower.includes("notice_writer")) return "notice_writer: write a school notice";
  if (lower.includes("notice_checker")) return "notice_checker: check notice format";
  if (lower.includes("5w1h")) return "5w1h_extractor: extract who what when where why how";
  if (lower.includes("formal_tone")) return "formal_tone_adjuster: make this more formal";
  if (lower.includes("letter_format")) return "letter_format_checker: check letter format";
  if (lower.includes("graph_analyzer")) return "graph_analyzer: analyze a graph";
  if (lower.includes("analytical")) return "analytical_paragraph_writer: write an analytical paragraph";
  if (lower.includes("trend")) return "trend_detector: identify trends";
  if (lower.includes("grammar")) return "grammar_checker: fix grammar";
  if (lower.includes("vocabulary")) return "vocabulary_enhancer: improve vocabulary";
  if (lower.includes("humanizer")) return "humanizer: make this sound natural";
  if (lower.includes("exam_marker")) return "exam_marker: mark this answer";
  if (lower.includes("word_limit")) return "word_limit_controller: fit this to 150 words";
  if (lower.includes("writing")) return "give me 3 writing options: letter, essay, and story";
  if (lower.includes("calculator")) return "calculate (50 + 25) / 5";
  if (lower.includes("clock")) return "what time is it";
  if (lower.includes("memory")) return "remember my favorite topic is AI assistants";
  if (lower.includes("notes")) return "list notes";
  if (lower.includes("todos")) return "list todos";
  if (lower.includes("stats")) return "database stats";
  if (lower.includes("dice")) return "roll a dice";
  if (lower.includes("coin")) return "flip a coin";
  if (lower.includes("password")) return "generate password";
  if (lower.includes("unit")) return "convert 10 km to miles";
  if (lower.includes("training")) return "how do I train this assistant";
  if (lower.includes("url safety")) return "url safety checker: check this link for phishing or malware";
  if (lower.includes("malware")) return "file malware scanner: explain safe file scanning";
  if (lower.includes("prompt injection")) return "prompt injection detector: inspect this content";
  if (lower.includes("permission")) return "permission gate: require approval before risky actions";
  if (lower.includes("sandbox")) return "code sandbox: isolate risky code";
  if (lower.includes("risk classifier")) return "command risk classifier: check dangerous commands";
  if (lower.includes("data leak")) return "data leak guard: protect secrets";
  if (lower.includes("rate limit")) return "rate limit guard: prevent spam";
  if (lower.includes("audit")) return "audit log: record tool actions";
  if (lower.includes("safe mode")) return "safe mode switch: disable dangerous tools";
  if (lower.includes("multi-agent")) return "multi-agent system: solve this using planner critic and executor";
  if (lower.includes("self correcting")) return "self correcting system: review and improve the last answer";
  if (lower.includes("voice")) return "voice chat";
  if (lower.includes("new conversation")) return "new chat";
  return name;
}

function showMode(key) {
  const mode = modes[key];
  if (!mode || !modePanel || !modeTools) return;
  modeTitle.textContent = mode.title;
  modeTools.innerHTML = "";
  mode.tools.forEach(([label, prompt]) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.innerHTML = `<b>${label}</b><small>${prompt}</small>`;
    btn.onclick = () => sendMessage(prompt);
    modeTools.appendChild(btn);
  });
  modePanel.classList.add("open");
}

function renderTodos(items) {
  if (!tasksList) return;
  localTodos[persona] = items;
  tasksList.innerHTML = "";
  if (!items.length) {
    tasksList.innerHTML = `<div class="task-row"><span class="task-text">No tasks yet.</span></div>`;
    return;
  }
  items.forEach(item => {
    const row = document.createElement("div");
    row.className = `task-row${item.done ? " done" : ""}`;
    row.innerHTML = `
      <span class="task-text">${linkify(item.content)}</span>
      <span class="task-actions">
        <button type="button" data-done="${item.id}">Done</button>
        <button type="button" data-delete="${item.id}">Delete</button>
      </span>
    `;
    row.querySelector("[data-done]")?.addEventListener("click", () => sendMessage(`complete todo ${item.id}`));
    row.querySelector("[data-delete]")?.addEventListener("click", () => deleteTodo(item.id));
    tasksList.appendChild(row);
  });
}

async function loadTodos() {
  if (!tasksList) return;
  try {
    const res = await fetch(`${API}/todos?persona=${encodeURIComponent(persona)}`);
    if (!res.ok) throw new Error("todos endpoint unavailable");
    const data = await res.json();
    renderTodos(data.todos || []);
  } catch {
    renderTodos(localTodos[persona] || []);
  }
}

async function addTodo(content) {
  const optimistic = { id: `local-${Date.now()}`, content, done: false };
  renderTodos([optimistic, ...(localTodos[persona] || [])]);
  try {
    const res = await fetch(`${API}/todo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, content }),
    });
    if (!res.ok) throw new Error("todo endpoint unavailable");
    const data = await res.json();
    renderTodos(data.todos || []);
    addMessage("System", `Added task: ${content}`);
  } catch {
    addMessage("System", `Added task locally. Restart open_web_assistant.bat if database tasks do not sync.`);
    fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona, message: `todo: ${content}` }),
    }).then(() => loadTodos()).catch(() => {});
  }
}

async function deleteTodo(id) {
  try {
    const res = await fetch(`${API}/todo?persona=${encodeURIComponent(persona)}&id=${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("delete endpoint unavailable");
    const data = await res.json();
    renderTodos(data.todos || []);
    addMessage("System", `Deleted task ${id}.`);
  } catch {
    renderTodos((localTodos[persona] || []).filter(item => String(item.id) !== String(id)));
    if (!String(id).startsWith("local-")) sendMessage(`delete todo ${id}`);
  }
}

async function deleteSession(id) {
  let data = null;
  try {
    const res = await fetch(`${API}/session?id=${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error("session delete unavailable");
    data = await res.json();
  } catch (firstError) {
    try {
      const res = await fetch(`${API}/delete_session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      if (!res.ok) throw firstError;
      data = await res.json();
    } catch {
      addMessage("System", "Could not delete that saved chat. Close old assistant windows, run open_web_assistant.bat again, then refresh this page.");
      return;
    }
  }
  await loadSessions();
  addMessage("System", data?.ok ? "Saved chat deleted." : "Saved chat was already gone.");
}

async function deleteCloudSession(id) {
  try {
    await window.AntimonyCloud.deleteChat(id);
    await loadSessions();
    addMessage("System", "Cloud chat deleted.");
  } catch (error) {
    addMessage("System", `Could not delete that cloud chat. ${error.message}`);
  }
}

async function loadTools() {
  if (!toolsList) return;
  try {
    const res = await fetch(`${API}/tools`);
    const data = await res.json();
    toolsList.innerHTML = "";
    (data.tools || []).forEach(tool => {
      const btn = document.createElement("button");
      btn.innerHTML = `<span class="tool-dot"></span><span><b>${tool}</b><small>${promptForTool(tool)}</small></span>`;
      btn.onclick = () => sendMessage(promptForTool(tool));
      toolsList.appendChild(btn);
    });
  } catch {
    toolsList.innerHTML = `<button><span class="tool-dot"></span><span><b>Tools offline</b><small>Start open_web_assistant.bat</small></span></button>`;
  }
}

async function loadSession(id) {
  const res = await fetch(`${API}/session?id=${encodeURIComponent(id)}`);
  const data = await res.json();
  messages.innerHTML = "";
  (data.messages || []).forEach(msg => {
    const role = msg.role === "user" ? "user" : "assistant";
    const sender = role === "user" ? "You" : (personas[msg.persona]?.name || "Assistant");
    addMessage(sender, msg.content, role);
  });
}

async function loadCloudSession(id) {
  try {
    const cloudMessages = await window.AntimonyCloud.loadChat(id);
    messages.innerHTML = "";
    cloudMessages.forEach(message => {
      const role = message.role === "user" ? "user" : "assistant";
      const sender = role === "user" ? "You" : (personas[message.persona]?.name || "Assistant");
      addMessage(sender, message.content, role);
    });
  } catch (error) {
    addMessage("System", `Could not load cloud chat.\n${error.message}`);
  }
}

function buildPersonaButtons() {
  let container = document.querySelector(".persona-grid");
  if (!container) {
    container = document.createElement("div");
    container.className = "persona-grid";
    const nav = document.querySelector(".left-rail nav");
    nav.parentNode.insertBefore(container, nav.nextSibling);
  }
  container.innerHTML = "";
  Object.entries(personas).forEach(([key, value]) => {
    const item = document.createElement("div");
    item.className = `persona-choice${value.custom ? " custom" : ""}`;
    const btn = document.createElement("button");
    btn.className = "persona-button";
    btn.textContent = value.name;
    btn.dataset.key = key;
    btn.onclick = () => setPersona(key);
    item.appendChild(btn);
    if (value.custom) {
      const share = document.createElement("button");
      share.className = "share-persona";
      share.type = "button";
      share.textContent = "↓";
      share.title = `Export ${value.name}`;
      share.setAttribute("aria-label", `Export ${value.name}`);
      share.onclick = () => exportAgent(key);
      item.appendChild(share);
      const del = document.createElement("button");
      del.className = "delete-persona";
      del.type = "button";
      del.textContent = "x";
      del.title = `Delete ${value.name}`;
      del.setAttribute("aria-label", `Delete ${value.name}`);
      del.onclick = () => deleteAgent(key);
      item.appendChild(del);
    }
    container.appendChild(item);
  });
  document.querySelectorAll(".persona-button").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.key === persona);
  });
}

document.querySelectorAll("[data-prompt]").forEach(btn => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.prompt));
});

document.querySelectorAll("[data-mode]").forEach(btn => {
  btn.addEventListener("click", () => showMode(btn.dataset.mode));
});

document.querySelector("#closeMode")?.addEventListener("click", () => {
  modePanel?.classList.remove("open");
});

function renderCalendar(date = new Date()) {
  if (!calendarGrid || !calendarMonth) return;
  const year = date.getFullYear();
  const month = date.getMonth();
  const today = date.getDate();
  const monthName = date.toLocaleString(undefined, { month: "long", year: "numeric" });
  calendarMonth.textContent = monthName;
  calendarGrid.innerHTML = "";
  ["S", "M", "T", "W", "T", "F", "S"].forEach(day => {
    const node = document.createElement("span");
    node.className = "day-name";
    node.textContent = day;
    calendarGrid.appendChild(node);
  });
  const firstDay = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  for (let i = 0; i < firstDay; i += 1) {
    calendarGrid.appendChild(document.createElement("span"));
  }
  for (let day = 1; day <= days; day += 1) {
    const node = document.createElement("span");
    node.textContent = day;
    if (day === today) node.className = "today";
    calendarGrid.appendChild(node);
  }
}

function startVoiceChat() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceText = document.querySelector(".voice-card p");
  if (!SpeechRecognition) {
    addMessage("System", "This browser does not support speech recognition. Try Chrome or Edge.");
    return;
  }
  voiceEnabled = true;
  if (!recognition) {
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onstart = () => {
      if (voiceText) voiceText.textContent = "Listening...";
      addMessage("System", "Listening...");
    };
    recognition.onresult = event => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim();
      if (voiceText) voiceText.textContent = transcript ? "Thinking..." : "No speech heard.";
      if (transcript) sendMessage(transcript);
    };
    recognition.onerror = event => {
      if (voiceText) voiceText.textContent = "Mic error. Check browser permission.";
      addMessage("System", `Voice input failed: ${event.error || "unknown error"}`);
    };
    recognition.onend = () => {
      if (voiceText && voiceText.textContent === "Listening...") voiceText.textContent = "Voice ready.";
    };
  }
  try {
    recognition.start();
  } catch {
    addMessage("System", "Voice is already listening.");
  }
}

document.querySelector("[data-action='voice']")?.addEventListener("click", startVoiceChat);

document.querySelector("#refreshSessions").onclick = loadSessions;
async function startNewChat() {
  window.AntimonyCloud?.newChat();
  try {
    await fetch(`${API}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ persona }),
    });
  } catch {}
  messages.innerHTML = "";
  addMessage(personas[persona]?.name || "Assistant", "New chat started. Old chats remain saved.");
  loadSessions();
}

document.querySelector("#savedNewChat")?.addEventListener("click", startNewChat);
document.querySelector("#chatNav")?.addEventListener("click", startNewChat);
document.querySelector("#minChat")?.addEventListener("click", () => {
  chatWindow.classList.toggle("minimized");
  chatWindow.classList.remove("maximized");
});
document.querySelector("#maxChat")?.addEventListener("click", () => {
  chatWindow.classList.toggle("maximized");
  chatWindow.classList.remove("minimized");
  messages.scrollTop = messages.scrollHeight;
});
document.querySelector("#newChat").onclick = startNewChat;

function updateStudioPreview() {
  const name = newAgentName.value.trim() || "Your Agent";
  const initials = name.split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "AI";
  studioPreviewName.textContent = name;
  studioPreviewRole.textContent = newAgentRole.value || "AI Companion";
  studioPreviewVibe.textContent = newAgentVibe.value.trim() || "Build a personality people remember.";
  studioAvatar.textContent = initials;
}

function applyAgentTemplate(key) {
  const preset = agentTemplatePresets[key];
  if (!preset) return;
  selectedAgentTemplate = key;
  newAgentRole.value = preset.role;
  newAgentPurpose.value = preset.purpose;
  newAgentVibe.value = preset.vibe;
  newAgentTraits.value = preset.traits;
  newAgentAppearance.value = preset.appearance;
  newAgentInstructions.value = preset.instructions;
  document.querySelectorAll('#studioPackChoices input[name="knowledge_pack"]').forEach(input => {
    const expected = key === "coding" ? "coding_core" : `${key}_core`;
    input.checked = input.value === expected;
  });
  studioTemplateLabel.textContent = `${key[0].toUpperCase()}${key.slice(1)} Template`;
  document.querySelectorAll("#agentTemplates button").forEach(button => button.classList.toggle("active", button.dataset.template === key));
  updateStudioPreview();
}

function resetAgentStudio() {
  createAgentForm.reset();
  applyAgentTemplate("companion");
}

function openAgentStudio() {
  agentStudio.hidden = false;
  document.body.style.overflow = "hidden";
  if (!newAgentVibe.value) applyAgentTemplate(selectedAgentTemplate);
  newAgentName.focus();
}

function closeAgentStudio() {
  agentStudio.hidden = true;
  document.body.style.overflow = "";
}

createAgentOpen?.addEventListener("click", openAgentStudio);
cancelAgentCreate?.addEventListener("click", closeAgentStudio);
document.querySelector("#studioReset")?.addEventListener("click", resetAgentStudio);
agentStudio?.addEventListener("click", event => { if (event.target === agentStudio) closeAgentStudio(); });
document.addEventListener("keydown", event => { if (event.key === "Escape" && !agentStudio?.hidden) closeAgentStudio(); });
document.querySelectorAll("#agentTemplates button").forEach(button => button.addEventListener("click", () => applyAgentTemplate(button.dataset.template)));
[newAgentName, newAgentRole, newAgentVibe].forEach(control => control?.addEventListener("input", updateStudioPreview));

importAgentOpen?.addEventListener("click", () => importAgentFile?.click());
importAgentFile?.addEventListener("change", async () => {
  const file = importAgentFile.files?.[0];
  if (!file) return;
  try {
    await importAgentPackage(JSON.parse(await file.text()));
  } catch (error) {
    addMessage("System", `Could not import agent.\n${error.message}`);
  } finally {
    importAgentFile.value = "";
  }
});

createAgentForm?.addEventListener("submit", async event => {
  event.preventDefault();
  const name = newAgentName.value.trim();
  const vibe = newAgentVibe.value.trim();
  if (!name || !vibe) return;
  const generateButton = document.querySelector("#generateAgent");
  generateButton.disabled = true;
  generateButton.textContent = "Creating...";
  const profile = {
    role: newAgentRole.value,
    purpose: newAgentPurpose.value.trim(),
    appearance: newAgentAppearance.value.trim(),
    traits: newAgentTraits.value.split(",").map(item => item.trim()).filter(Boolean),
    voice_style: newAgentVoice.value,
    goals: newAgentGoals.value.split(/\n+/).map(item => item.trim()).filter(Boolean),
    greeting: newAgentGreeting.value.trim(),
    instructions: newAgentInstructions.value.trim(),
    starter_knowledge: newAgentKnowledge.value.trim(),
    knowledge_packs: [...document.querySelectorAll('#studioPackChoices input[name="knowledge_pack"]:checked')].map(input => input.value),
    visibility: newAgentVisibility.value,
    template: selectedAgentTemplate,
  };
  closeAgentStudio();
  await createAgent(name, vibe, profile);
  generateButton.disabled = false;
  generateButton.textContent = "Generate Agent";
  resetAgentStudio();
});

marketplaceOpen?.addEventListener("click", async () => {
  marketplace.hidden = false;
  document.body.style.overflow = "hidden";
  await loadMarketplace();
});
marketplaceClose?.addEventListener("click", () => {
  marketplace.hidden = true;
  document.body.style.overflow = "";
});
marketplace?.addEventListener("click", event => {
  if (event.target === marketplace) {
    marketplace.hidden = true;
    document.body.style.overflow = "";
  }
});
document.querySelectorAll("[data-market-tab]").forEach(button => button.addEventListener("click", () => {
  const tab = button.dataset.marketTab;
  document.querySelectorAll("[data-market-tab]").forEach(item => item.classList.toggle("active", item === button));
  marketAgents.hidden = tab !== "agents";
  marketPacks.hidden = tab !== "packs";
}));

let authMode = "login";
document.querySelectorAll("[data-auth-mode]").forEach(button => button.addEventListener("click", () => {
  authMode = button.dataset.authMode;
  document.querySelectorAll("[data-auth-mode]").forEach(item => item.classList.toggle("active", item === button));
  document.querySelector("#authSubmit").textContent = authMode === "signup" ? "Create account" : "Log in";
  document.querySelector("#authPassword").autocomplete = authMode === "signup" ? "new-password" : "current-password";
}));
document.querySelector("#authForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const error = document.querySelector("#authError");
  const submit = document.querySelector("#authSubmit");
  error.textContent = "";
  submit.disabled = true;
  submit.textContent = authMode === "signup" ? "Creating..." : "Signing in...";
  try {
    const data = await window.AntimonyCloud.authenticate(
      document.querySelector("#authEmail").value.trim(),
      document.querySelector("#authPassword").value,
      authMode,
    );
    if (!data.access_token && authMode === "signup") error.textContent = "Account created. Check your email, then log in.";
  } catch (authError) {
    error.textContent = authError.message;
  } finally {
    submit.disabled = false;
    submit.textContent = authMode === "signup" ? "Create account" : "Log in";
  }
});
document.querySelector("#accountButton")?.addEventListener("click", () => {
  document.querySelector("#authOverlay").hidden = false;
  window.AntimonyCloud?.renderAccount();
  document.querySelector("#authOverlay").hidden = false;
});
document.querySelector("#authClose")?.addEventListener("click", () => { document.querySelector("#authOverlay").hidden = true; });
document.querySelector("#signOutButton")?.addEventListener("click", () => window.AntimonyCloud?.signOut());

taskForm?.addEventListener("submit", event => {
  event.preventDefault();
  const text = taskInput.value.trim();
  if (!text) return;
  taskInput.value = "";
  addTodo(text);
});

form.addEventListener("submit", event => {
  event.preventDefault();
  const text = input.value.trim();
  if (text) sendMessage(text);
});

async function init() {
  await window.AntimonyCloud?.init();
  await loadPersonas();
  await loadKnowledgePacks();
  setPersona("soren");
  resetAgentStudio();
  addMessage("Antimony", "Ollama, RAG, tools, memory, and saved chats are ready. Agent Studio can build specialized, persistent agents.");
  renderCalendar();
  loadHealth();
  loadTools();
  loadTodos();
  loadSessions();
}
init();
setInterval(loadHealth, 5000);

const launchPrompt = new URLSearchParams(window.location.search).get("prompt");
if (launchPrompt) {
  window.history.replaceState({}, "", window.location.pathname);
  setTimeout(() => sendMessage(launchPrompt), 350);
}
