const submitForm = document.querySelector("#submit-grade-form");
const viewForm = document.querySelector("#view-grades-form");
const submitStatus = document.querySelector("#submit-status");
const viewStatus = document.querySelector("#view-status");
const resultsContainer = document.querySelector("#grades-results");

function createCorrelationId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `frontend-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function setStatus(element, message, type) {
  element.textContent = message;
  element.className = `status is-visible ${type}`;
}

function clearStatus(element) {
  element.textContent = "";
  element.className = "status";
}

function formValue(form, name) {
  return new FormData(form).get(name).trim();
}

function renderGrades(grades) {
  if (!grades.length) {
    resultsContainer.innerHTML = '<p class="empty-state">No grade records found for this student.</p>';
    return;
  }
  const rows = grades.map(g => `
    <tr>
      <td>${escapeHtml(g.first_name)} ${escapeHtml(g.last_name)}</td>
      <td>${escapeHtml(g.class_name)}</td>
      <td>${escapeHtml(g.grade)}</td>
      <td>${g.id}</td>
    </tr>`).join("");
  resultsContainer.innerHTML = `
    <table>
      <thead><tr><th>Student</th><th>Class</th><th>Grade</th><th>Record ID</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function escapeHtml(value) {
  return String(value).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
}

submitForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearStatus(submitStatus);
  const correlationId = createCorrelationId();
  const payload = {
    first_name: formValue(submitForm, "first_name"),
    last_name: formValue(submitForm, "last_name"),
    class_name: formValue(submitForm, "class_name"),
    grade: formValue(submitForm, "grade"),
  };
  try {
    const response = await fetch("/api/grades", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Correlation-ID": correlationId },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Unable to submit grade");
    setStatus(submitStatus, `Grade submitted. Correlation ID: ${result.correlation_id}`, "success");
    submitForm.reset();
  } catch (error) {
    setStatus(submitStatus, `${error.message}. Correlation ID: ${correlationId}`, "error");
  }
});

viewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearStatus(viewStatus);
  const correlationId = createCorrelationId();
  const firstName = encodeURIComponent(formValue(viewForm, "first_name"));
  const lastName = encodeURIComponent(formValue(viewForm, "last_name"));
  try {
    const response = await fetch(`/api/grades?first_name=${firstName}&last_name=${lastName}`, {
      headers: { "X-Correlation-ID": correlationId },
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Unable to fetch grades");
    renderGrades(result.grades);
    setStatus(viewStatus, `Fetched ${result.count} record(s). Correlation ID: ${result.correlation_id}`, "success");
  } catch (error) {
    setStatus(viewStatus, `${error.message}. Correlation ID: ${correlationId}`, "error");
  }
});
