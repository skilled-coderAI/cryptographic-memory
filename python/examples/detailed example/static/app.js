"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const esc = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const state = { busy: false, started: false };

const CHECK = '<svg class="vmark ok" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M5 13l4 4L19 7"/></svg>';
const CROSS = '<svg class="vmark bad" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M6 6l12 12M18 6L6 18"/></svg>';

/* ---------------- bootstrap ---------------- */
async function init() {
  bindUI();
  await Promise.all([loadHealth(), loadMemory()]);
}

async function loadHealth() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("#model-name").textContent = h.model;
    $("#ollama-dot").className = "dot " + (h.ollama_alive ? "ok" : "bad");
    $("#model-pill").title =
      `host ${h.host}\nembedder: ${h.embedder}\ngrounding threshold: ${h.min_confidence}` +
      (h.ollama_alive ? "" : "\nOllama not reachable \u2014 run `ollama serve`");
  } catch (e) {
    $("#model-name").textContent = "offline";
    $("#ollama-dot").className = "dot bad";
  }
}

async function loadMemory() {
  try {
    const data = await (await fetch("/api/memory")).json();
    const list = $("#fact-list");
    list.innerHTML = "";
    for (const f of data.facts) {
      const node = el("div", "fact");
      node.innerHTML =
        `<div class="fact-top"><span class="fact-entity">${esc(f.entity)}</span>` +
        `<span class="fact-badge">${f.verified ? "verified" : "unverified"}</span></div>` +
        `<div class="fact-content">${esc(f.content)}</div>` +
        `<div class="fact-meta">${esc(f.node_id)}${f.hash ? " \u00b7 " + esc(f.hash) : ""}</div>`;
      list.appendChild(node);
    }
  } catch (e) {
    /* sidebar stays empty */
  }
}

/* ---------------- UI wiring ---------------- */
function bindUI() {
  const send = () => submit($("#input-hero").value);
  $("#send-hero").addEventListener("click", send);
  $("#input-hero").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  autoGrow($("#input-hero"));

  const sendDock = () => submit($("#input-dock").value);
  $("#send-dock").addEventListener("click", sendDock);
  $("#input-dock").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendDock(); }
  });
  autoGrow($("#input-dock"));

  document.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => submit(c.dataset.q))
  );

  $("#reasoning-toggle").addEventListener("change", (e) => toggleReasoning(e.target.checked));
  $("#reasoning-close").addEventListener("click", () => {
    $("#reasoning-toggle").checked = false;
    toggleReasoning(false);
  });

  $("#new-chat").addEventListener("click", () => location.reload());
}

function autoGrow(t) {
  t.addEventListener("input", () => {
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 180) + "px";
  });
}

function toggleReasoning(on) {
  $("#app").classList.toggle("with-reasoning", on);
  $("#reasoning").hidden = !on;
}

/* ---------------- conversation flow ---------------- */
function ensureConversation() {
  if (state.started) return;
  state.started = true;
  $("#hero").hidden = true;
  $("#conversation").hidden = false;
  $("#composer-dock").hidden = false;
}

function addUser(text) {
  const m = el("div", "msg user");
  m.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  $("#conversation").appendChild(m);
  scrollChat();
}

function addAssistantShell() {
  const m = el("div", "msg assistant");
  m.innerHTML =
    `<div class="avatar">cm</div>` +
    `<div class="bubble"><div class="body"><span class="typing"><span></span><span></span><span></span></span></div></div>`;
  $("#conversation").appendChild(m);
  scrollChat();
  return m;
}

function renderAnswer(shell, content, provenance) {
  const body = shell.querySelector(".body");
  const paras = String(content).trim().split(/\n{2,}/).map((p) => `<p>${esc(p)}</p>`).join("");
  body.innerHTML = paras || "<p></p>";
  if (provenance) body.appendChild(provBlock(provenance));
  scrollChat();
}

function provBlock(p) {
  const wrap = el("div", "provenance");
  if (p.grounded) {
    wrap.appendChild(el("span", "prov-badge ok", CHECK + " verified"));
    (p.injected_nodes || []).forEach((id) =>
      wrap.appendChild(el("span", "node-chip", esc(id)))
    );
  } else {
    wrap.appendChild(el("span", "prov-badge abstain", "&#9888; abstained"));
  }
  if (p.ledger_root) {
    wrap.appendChild(el("span", "prov-root", "root " + esc(String(p.ledger_root).slice(0, 14)) + "\u2026"));
  }
  return wrap;
}

function scrollChat() {
  const s = $("#stage");
  s.scrollTop = s.scrollHeight;
}

/* ---------------- reasoning timeline ---------------- */
function resetTimeline() {
  $("#timeline").innerHTML = "";
}

function tlAdd(ev) {
  const tl = $("#timeline");
  let cls = "tl-item stage-" + (ev.stage || ev.type);
  if (ev.type === "tool_call") cls = "tl-item toolcall";
  if (ev.decision === "abstain") cls += " abstain";
  const item = el("div", cls);

  let title = ev.title || "";
  if (ev.type === "tool_call") title = "Tool call \u00b7 recall_verified_memory";
  if (ev.type === "status") title = ev.label;
  item.appendChild(el("div", "tl-title", esc(title)));

  if (ev.type === "tool_call") {
    item.appendChild(el("div", "tl-detail mono", "query: " + esc(ev.query)));
  } else if (ev.detail) {
    item.appendChild(el("div", "tl-detail", esc(ev.detail)));
  }

  if (ev.items && ev.items.length) {
    const box = el("div", "tl-items");
    ev.items.forEach((it) => box.appendChild(tlRow(ev.stage, it)));
    item.appendChild(box);
  }
  tl.appendChild(item);
  tl.scrollTop = tl.scrollHeight;
  return item;
}

function tlRow(stage, it) {
  const row = el("div", "tl-row");
  if (stage === "retrieve") {
    const pct = Math.max(0, Math.min(1, it.similarity)) * 100;
    row.innerHTML =
      `<span class="rent">${esc(it.entity)}</span>` +
      `<span class="rtxt">${esc(it.content)}</span>` +
      `<span class="sim-wrap"><span class="sim-bar"><span class="sim-fill" style="width:${pct}%"></span></span>` +
      `<span class="sim-val">${it.similarity.toFixed(2)}</span></span>`;
  } else if (stage === "verify") {
    row.innerHTML =
      (it.verified ? CHECK : CROSS) +
      `<span class="rid">${esc(it.node_id)}</span>` +
      `<span class="rtxt">${it.hash ? esc(it.hash) : ""}</span>` +
      `<span class="sim-val">${it.verified ? "ok" : "drop"}</span>`;
  } else if (stage === "gate") {
    row.innerHTML =
      CHECK +
      `<span class="rent">${esc(it.entity)}</span>` +
      `<span class="rtxt">${esc(it.node_id)}</span>` +
      `<span class="sim-val">${Number(it.confidence).toFixed(2)}</span>`;
  } else {
    row.textContent = JSON.stringify(it);
  }
  return row;
}

/* ---------------- network ---------------- */
async function submit(raw) {
  const text = (raw || "").trim();
  if (!text || state.busy) return;
  state.busy = true;
  ensureConversation();
  $("#input-hero").value = "";
  $("#input-dock").value = "";
  $("#send-hero").disabled = true;
  $("#send-dock").disabled = true;

  addUser(text);
  resetTimeline();
  const shell = addAssistantShell();

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    await readSSE(resp, shell);
  } catch (e) {
    renderAnswer(shell, "Request failed: " + e.message, null);
  } finally {
    state.busy = false;
    $("#send-hero").disabled = false;
    $("#send-dock").disabled = false;
    loadMemory();
  }
}

async function readSSE(resp, shell) {
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop();
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let ev;
      try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
      handleEvent(ev, shell);
    }
  }
}

function handleEvent(ev, shell) {
  switch (ev.type) {
    case "tool_call":
    case "status":
    case "step":
      tlAdd(ev);
      if (ev.stage === "generate") {
        const body = shell.querySelector(".body");
        body.innerHTML = `<p class="muted"><span class="tl-spin"></span>Synthesizing grounded answer\u2026</p>`;
      }
      break;
    case "answer":
      renderAnswer(shell, ev.content, ev.provenance);
      break;
    case "error":
      shell.querySelector(".body").innerHTML = "";
      shell.querySelector(".bubble").appendChild(el("div", "banner", esc(ev.message)));
      break;
    case "done":
      break;
  }
}

init();
