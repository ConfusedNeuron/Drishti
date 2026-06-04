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
  box.textContent = d.answer;
}
