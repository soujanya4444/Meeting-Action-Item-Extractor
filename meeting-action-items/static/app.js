const SAMPLE_TRANSCRIPT = `Sarah: I'll send the updated design deck to the client by Friday.
James: Sounds good. We should also schedule a follow-up call next week.
Priya: Can you review the API docs? It's kind of urgent, we're blocked on it.
James: Sure, I'll do it by tomorrow.
Sarah: Also, someone needs to update the project timeline before the Monday sync.
Priya: I'll handle the timeline update.
James: When you get a chance, could you also clean up the shared drive? No rush on that one.
Sarah: Sure, I'll get to it next week.`;

const transcriptInput = document.getElementById("transcriptInput");
const meetingDateInput = document.getElementById("meetingDate");
const extractBtn = document.getElementById("extractBtn");
const btnText = document.getElementById("btnText");
const errorMsg = document.getElementById("errorMsg");
const emptyState = document.getElementById("emptyState");
const tableWrapper = document.getElementById("tableWrapper");
const resultsBody = document.getElementById("resultsBody");
const itemCount = document.getElementById("itemCount");
const loadSampleBtn = document.getElementById("loadSampleBtn");

// default meeting date = today
meetingDateInput.value = new Date().toISOString().slice(0, 10);

loadSampleBtn.addEventListener("click", () => {
  transcriptInput.value = SAMPLE_TRANSCRIPT;
});

extractBtn.addEventListener("click", async () => {
  const transcript = transcriptInput.value.trim();
  errorMsg.textContent = "";

  if (!transcript) {
    errorMsg.textContent = "Paste a transcript first.";
    return;
  }

  extractBtn.disabled = true;
  btnText.textContent = "Extracting...";

  try {
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transcript: transcript,
        meeting_date: meetingDateInput.value || null,
      }),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Extraction failed.");
    }

    renderResults(data.items);
  } catch (err) {
    errorMsg.textContent = err.message;
  } finally {
    extractBtn.disabled = false;
    btnText.textContent = "Extract action items";
  }
});

function renderResults(items) {
  resultsBody.innerHTML = "";

  if (!items || items.length === 0) {
    emptyState.classList.remove("hidden");
    tableWrapper.classList.add("hidden");
    emptyState.querySelector("p").textContent =
      "No action items detected. Try a transcript with clearer commitments (\"will\", \"needs to\", \"by Friday\"...).";
    itemCount.textContent = "";
    return;
  }

  emptyState.classList.add("hidden");
  tableWrapper.classList.remove("hidden");
  itemCount.textContent = `${items.length} item${items.length === 1 ? "" : "s"}`;

  for (const item of items) {
    const tr = document.createElement("tr");

    tr.innerHTML = `
      <td><span class="owner-pill">${escapeHtml(item.owner)}</span></td>
      <td>${escapeHtml(item.task)}</td>
      <td class="deadline-cell">${item.deadline ? escapeHtml(item.deadline) : "—"}</td>
      <td><span class="priority-badge priority-${item.priority}">${item.priority}</span></td>
    `;
    resultsBody.appendChild(tr);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
