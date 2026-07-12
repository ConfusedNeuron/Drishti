async function loadMemo() {
  document.getElementById("memo-output").textContent = "Generating…";
  const r = await fetch(window.API + "/api/copilot/memo", { method: "POST" });
  if (!r.ok) { document.getElementById("memo-output").textContent = "Error: " + (await r.text()); return; }
  const d = await r.json();
  document.getElementById("memo-output").textContent = d.memo;
}

async function askCopilot() {
  const q = document.getElementById("q-input").value.trim();
  if (!q) return;
  const box = document.getElementById("answer-box");
  box.style.display = "block";
  box.textContent = "Thinking…";
  const r = await fetch(window.API + "/api/copilot/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q }),
  });
  const d = await r.json();
  const MODE_LABELS = {
    llm: "AI answer (grounded in the deterministic memo)",
    deterministic_memo: "Deterministic memo — no LLM key configured",
    safety_filter: "Refused — investment-advice question; showing risk-diagnostics guidance",
    llm_error: "LLM call failed — showing deterministic memo",
  };
  const mode = document.getElementById("answer-mode");
  mode.textContent = "↳ Mode: " + (MODE_LABELS[d.source] || d.source || "unknown");
  mode.style.display = "block";
  box.textContent = d.answer;
}
