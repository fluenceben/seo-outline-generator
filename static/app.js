const state = {
  intent: "informational",
  primaryKeyword: "",
  secondaryKeywords: "",
  clientUrl: "",
  pageType: "new",
  existingHeaders: [],
  existingPageError: null,
  paaQuestions: [],
  serpResults: [],
  pages: [],
  outlineHeaders: [],
  alternateHeaders: [],
  tfidfTerms: [],
  contentBenchmarks: null,
  faqCandidates: [],
  outlineRows: [],
  outlineFaqs: [],
  title: "",
  h1: "",
};

const el = (id) => document.getElementById(id);

function showStep(n) {
  document.querySelectorAll(".step").forEach((s) => (s.hidden = true));
  el(`step${n}`).hidden = false;
  document.querySelectorAll("#stepIndicator li").forEach((li) => {
    li.classList.toggle("active", Number(li.dataset.step) === n);
    li.classList.toggle("done", Number(li.dataset.step) < n);
  });
}

function showGlobalError(message) {
  const banner = el("globalError");
  if (!message) {
    banner.hidden = true;
    banner.textContent = "";
    return;
  }
  banner.hidden = false;
  banner.textContent = message;
}

function setBusy(button, busy, busyLabel) {
  if (busy) {
    button.dataset.originalLabel = button.textContent;
    button.textContent = busyLabel || "Working...";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalLabel || button.textContent;
    button.disabled = false;
  }
}

async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.error || `Request failed (${resp.status})`);
  }
  return data;
}

// ---------- Step 1: Search ----------

el("pageTypeToggle").addEventListener("click", (e) => {
  const btn = e.target.closest(".segmented-option");
  if (!btn) return;
  state.pageType = btn.dataset.value;
  document
    .querySelectorAll("#pageTypeToggle .segmented-option")
    .forEach((b) => b.classList.toggle("active", b === btn));

  const isExisting = state.pageType === "existing";
  el("existingPageHint").hidden = !isExisting;
  el("clientUrlLabel").innerHTML = isExisting
    ? 'Existing page URL <span class="hint">(required — we\'ll diff recommendations against it)</span>'
    : 'Client website <span class="hint">(optional — excluded from competitor set)</span>';
});

el("btnSearch").addEventListener("click", async () => {
  showGlobalError(null);
  state.intent = el("intent").value;
  state.primaryKeyword = el("primaryKeyword").value.trim();
  state.secondaryKeywords = el("secondaryKeywords").value.trim();
  state.clientUrl = el("clientUrl").value.trim();

  if (!state.primaryKeyword) {
    showGlobalError("Enter a primary keyword to continue.");
    return;
  }
  if (state.pageType === "existing" && !state.clientUrl) {
    showGlobalError("Enter the existing page's URL to continue.");
    return;
  }

  const btn = el("btnSearch");
  setBusy(btn, true, "Searching...");
  try {
    const data = await postJSON("/api/search", {
      primary_keyword: state.primaryKeyword,
      client_url: state.clientUrl,
    });
    state.serpResults = data.results || [];
    state.paaQuestions = data.people_also_ask || [];
    if (state.serpResults.length === 0) {
      showGlobalError("No results came back for that keyword. Try adjusting it.");
      return;
    }
    renderSerpResults();
    showStep(2);
  } catch (err) {
    showGlobalError(err.message);
  } finally {
    setBusy(btn, false);
  }
});

function renderSerpResults() {
  const list = el("serpList");
  list.innerHTML = "";
  state.serpResults.forEach((result, idx) => {
    const row = document.createElement("label");
    row.className = "serp-row";
    row.innerHTML = `
      <input type="checkbox" class="serp-checkbox" data-idx="${idx}" checked>
      <div class="serp-body">
        <a href="${result.link}" target="_blank" rel="noopener">${escapeHtml(result.title)}</a>
        <div class="serp-link">${escapeHtml(result.displayLink || result.link)}</div>
        <div class="serp-snippet">${escapeHtml(result.snippet || "")}</div>
      </div>`;
    list.appendChild(row);
  });
}

el("btnBackTo1").addEventListener("click", () => showStep(1));

// ---------- Step 2 -> 3: Analyze ----------

el("btnAnalyze").addEventListener("click", async () => {
  showGlobalError(null);
  const checked = Array.from(document.querySelectorAll(".serp-checkbox:checked"));
  const urls = checked.map((cb) => state.serpResults[Number(cb.dataset.idx)].link);

  if (urls.length === 0) {
    showGlobalError("Select at least one result to analyze.");
    return;
  }

  const btn = el("btnAnalyze");
  setBusy(btn, true, "Analyzing...");
  try {
    const data = await postJSON("/api/analyze", {
      urls,
      intent: state.intent,
      primary_keyword: state.primaryKeyword,
      secondary_keywords: state.secondaryKeywords,
      existing_page_url: state.pageType === "existing" ? state.clientUrl : "",
      people_also_ask: state.paaQuestions,
    });
    state.pages = data.pages || [];
    const recs = data.header_recommendations || [];
    state.outlineHeaders = recs.filter((r) => r.recommended);
    state.alternateHeaders = recs.filter((r) => !r.recommended);
    state.tfidfTerms = data.tfidf_terms || [];
    state.faqCandidates = data.faq_candidates || [];
    state.contentBenchmarks = data.content_benchmarks || null;

    const existingPage = data.existing_page || null;
    if (state.pageType === "existing" && existingPage) {
      state.existingHeaders = existingPage.error ? [] : existingPage.headers || [];
      state.existingPageError = existingPage.error;
    } else {
      state.existingHeaders = [];
      state.existingPageError = null;
    }

    try {
      const titleData = await postJSON("/api/title", {
        intent: state.intent,
        primary_keyword: state.primaryKeyword,
        client_url: state.clientUrl,
      });
      state.title = titleData.title;
      state.h1 = titleData.h1;
    } catch (err) {
      state.title = state.primaryKeyword;
      state.h1 = state.primaryKeyword;
    }
    el("h1Input").value = state.h1;

    renderAnalysis();
    showStep(3);
  } catch (err) {
    showGlobalError(err.message);
  } finally {
    setBusy(btn, false);
  }
});

el("btnBackTo2").addEventListener("click", () => showStep(2));

function domainFromUrl(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (e) {
    return url;
  }
}

function renderAnalysis() {
  const warnBox = el("pageWarnings");
  const failed = state.pages.filter((p) => p.error);
  if (failed.length > 0) {
    warnBox.hidden = false;
    warnBox.innerHTML =
      "Couldn't analyze " +
      failed.length +
      " page(s): " +
      failed.map((p) => `${escapeHtml(domainFromUrl(p.url))} (${escapeHtml(p.error)})`).join("; ");
  } else {
    warnBox.hidden = true;
  }

  const existingWarnBox = el("existingPageWarning");
  if (state.pageType === "existing" && state.existingPageError) {
    existingWarnBox.hidden = false;
    existingWarnBox.textContent = `Couldn't scrape the existing page (${state.existingPageError}) — showing recommendations without the new/existing comparison.`;
  } else {
    existingWarnBox.hidden = true;
  }
  el("existingPageLegend").hidden = !(state.pageType === "existing" && state.existingHeaders.length > 0);

  renderHeaderLists();

  const benchBox = el("contentBenchmarks");
  const b = state.contentBenchmarks;
  if (b) {
    benchBox.hidden = false;
    benchBox.innerHTML =
      `Based on <strong>${b.page_count}</strong> competitor page(s) (outlier pages excluded): ` +
      (b.typical_word_count != null
        ? `typically <strong>${b.typical_word_count} words</strong> (${b.min_word_count}–${b.max_word_count}) `
        : "") +
      `across <strong>${b.typical_header_count} headers</strong> (${b.min_header_count}–${b.max_header_count}). ` +
      `Aim for a similar length and header count rather than padding it out.`;
  } else {
    benchBox.hidden = true;
  }

  const tfidfList = el("tfidfList");
  tfidfList.innerHTML = "";
  if (state.tfidfTerms.length === 0) {
    tfidfList.innerHTML = '<p class="subtle">No terms extracted.</p>';
  } else {
    const table = document.createElement("table");
    table.innerHTML =
      "<thead><tr><th>Term</th><th>Target uses</th></tr></thead><tbody>" +
      state.tfidfTerms
        .map((t) => {
          const target = t.max_uses ? `${t.min_uses}–${t.max_uses}` : "—";
          return `<tr><td title="TF-IDF score: ${t.score}">${escapeHtml(t.term)}</td><td>${target}</td></tr>`;
        })
        .join("") +
      "</tbody>";
    tfidfList.appendChild(table);
  }

  const faqBox = el("faqCandidateList");
  faqBox.innerHTML = "";
  if (state.faqCandidates.length === 0) {
    faqBox.innerHTML = '<p class="subtle">No FAQ candidates found.</p>';
  } else {
    state.faqCandidates.forEach((q, idx) => {
      const row = document.createElement("label");
      row.className = "faq-candidate-row";
      row.innerHTML = `<input type="checkbox" class="faq-checkbox" data-idx="${idx}" checked> <span>${escapeHtml(q)}</span>`;
      faqBox.appendChild(row);
    });
  }
}

// ---------- Recommended outline / alternates (drag & drop) ----------

const GROUP_STATE_KEY = { recommended: "outlineHeaders", alternate: "alternateHeaders" };
let dragSource = null; // { group, idx }

function groupList(group) {
  return state[GROUP_STATE_KEY[group]];
}

function renderHeaderLists() {
  renderHeaderGroup("headerList", "recommended");
  renderHeaderGroup("alternateHeaderList", "alternate");
}

function renderHeaderGroup(containerId, group) {
  const box = el(containerId);
  const list = groupList(group);
  box.innerHTML = "";
  if (list.length === 0) {
    box.innerHTML = `<p class="subtle">${
      group === "recommended" ? "No headers in the outline yet — drag some up from alternates." : "No alternates left."
    }</p>`;
    return;
  }
  list.forEach((rec, idx) => {
    const row = document.createElement("div");
    row.className = "header-row draggable-row";
    if (rec.is_new) row.className += " header-row-new";
    row.draggable = true;
    row.dataset.group = group;
    row.dataset.idx = idx;
    const actionBtn =
      group === "recommended"
        ? `<button type="button" class="btn-icon" data-action="remove-header" title="Remove from outline">&times;</button>`
        : `<button type="button" class="btn-icon" data-action="add-header" title="Add to outline">+</button>`;
    const coverageBadge =
      rec.coverage === undefined
        ? `<span class="header-coverage header-coverage-ai">&#10024; AI suggested</span>`
        : `<span class="header-coverage" title="${escapeHtml((rec.sources || []).join(", "))}">${rec.coverage}/${rec.total_pages} competitors</span>`;
    const newBadge = rec.is_new ? `<span class="new-badge">NEW</span>` : "";
    row.innerHTML = `
      <span class="drag-handle" aria-hidden="true">&#8942;&#8942;</span>
      <span class="level-badge level-${rec.level}">${rec.level}</span>
      <span class="header-text">${escapeHtml(rec.text)}</span>
      ${newBadge}
      ${coverageBadge}
      ${actionBtn}`;
    box.appendChild(row);
  });
}

function clearDropIndicator() {
  document.querySelectorAll(".drop-indicator").forEach((n) => n.remove());
  document.querySelectorAll(".dropzone.drag-over").forEach((n) => n.classList.remove("drag-over"));
}

function autoScrollDuringDrag(box, clientY) {
  if (box.scrollHeight <= box.clientHeight) return;
  const rect = box.getBoundingClientRect();
  const edge = 40;
  if (clientY < rect.top + edge) {
    box.scrollTop -= 12;
  } else if (clientY > rect.bottom - edge) {
    box.scrollTop += 12;
  }
}

function computeDropIndex(box, clientY) {
  const rows = Array.from(box.querySelectorAll(".draggable-row"));
  for (let i = 0; i < rows.length; i++) {
    const rect = rows[i].getBoundingClientRect();
    if (clientY < rect.top + rect.height / 2) return i;
  }
  return rows.length;
}

function moveHeader(source, targetGroup, targetIdx) {
  const sourceList = groupList(source.group);
  const [item] = sourceList.splice(source.idx, 1);
  let idx = targetIdx;
  if (source.group === targetGroup && source.idx < idx) idx -= 1;
  groupList(targetGroup).splice(idx, 0, item);
  renderHeaderLists();
}

function attachHeaderContainer(containerId, group) {
  const box = el(containerId);

  box.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const row = btn.closest(".draggable-row");
    const idx = Number(row.dataset.idx);
    if (btn.dataset.action === "add-header") {
      moveHeader({ group: "alternate", idx }, "recommended", state.outlineHeaders.length);
    } else if (btn.dataset.action === "remove-header") {
      moveHeader({ group: "recommended", idx }, "alternate", 0);
    }
  });

  box.addEventListener("dragstart", (e) => {
    const row = e.target.closest(".draggable-row");
    if (!row) return;
    dragSource = { group: row.dataset.group, idx: Number(row.dataset.idx) };
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", "");
    row.classList.add("dragging");
  });

  box.addEventListener("dragend", (e) => {
    const row = e.target.closest(".draggable-row");
    if (row) row.classList.remove("dragging");
    dragSource = null;
    clearDropIndicator();
  });

  box.addEventListener("dragover", (e) => {
    if (!dragSource) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    box.classList.add("drag-over");
    autoScrollDuringDrag(box, e.clientY);
    const dropIdx = computeDropIndex(box, e.clientY);
    document.querySelectorAll(".drop-indicator").forEach((n) => n.remove());
    const indicator = document.createElement("div");
    indicator.className = "drop-indicator";
    const rows = box.querySelectorAll(".draggable-row");
    if (dropIdx >= rows.length) {
      box.appendChild(indicator);
    } else {
      box.insertBefore(indicator, rows[dropIdx]);
    }
  });

  box.addEventListener("dragleave", (e) => {
    if (!box.contains(e.relatedTarget)) box.classList.remove("drag-over");
  });

  box.addEventListener("drop", (e) => {
    e.preventDefault();
    if (!dragSource) return;
    const dropIdx = computeDropIndex(box, e.clientY);
    moveHeader(dragSource, group, dropIdx);
    dragSource = null;
    clearDropIndicator();
  });
}

attachHeaderContainer("headerList", "recommended");
attachHeaderContainer("alternateHeaderList", "alternate");

el("h1Input").addEventListener("input", (e) => {
  state.h1 = e.target.value;
});

el("btnAiOutline").addEventListener("click", async () => {
  showGlobalError(null);
  const btn = el("btnAiOutline");
  setBusy(btn, true, "Generating...");
  try {
    const data = await postJSON("/api/ai-outline", {
      intent: state.intent,
      primary_keyword: state.primaryKeyword,
      secondary_keywords: state.secondaryKeywords,
      client_url: state.clientUrl,
      pages: state.pages,
      tfidf_terms: state.tfidfTerms,
      content_benchmarks: state.contentBenchmarks,
      existing_headers: state.existingHeaders,
    });
    state.outlineHeaders = (data.headers || []).map((h) => ({ level: h.level, text: h.text, is_new: h.is_new }));
    state.faqCandidates = data.faqs || [];
    renderAnalysis();
  } catch (err) {
    showGlobalError(err.message);
  } finally {
    setBusy(btn, false);
  }
});

// ---------- Step 3 -> 4: Build outline ----------

const LEVEL_NUM = { H1: 1, H2: 2, H3: 3, H4: 4, H5: 5, H6: 6 };

el("btnBuildOutline").addEventListener("click", () => {
  showGlobalError(null);
  const selectedFaqs = Array.from(document.querySelectorAll(".faq-checkbox:checked")).map(
    (cb) => state.faqCandidates[Number(cb.dataset.idx)]
  );

  if (state.outlineHeaders.length === 0) {
    showGlobalError("Add at least one header to the outline before continuing.");
    return;
  }

  state.h1 = el("h1Input").value.trim();
  if (!state.h1) {
    showGlobalError("Enter an H1 before continuing.");
    return;
  }

  const levels = state.outlineHeaders.map((h) => LEVEL_NUM[h.level] || 2);
  const minLevel = Math.min(...levels);
  const offset = 2 - minLevel;

  state.outlineRows = state.outlineHeaders.map((h) => {
    const original = LEVEL_NUM[h.level] || 2;
    const normalized = Math.min(4, Math.max(2, original + offset));
    return { level: `H${normalized}`, text: h.text, is_new: h.is_new };
  });
  state.outlineFaqs = selectedFaqs.slice();

  renderOutlineBuilder();
  showStep(4);
});

el("btnBackTo3").addEventListener("click", () => showStep(3));

function renderOutlineBuilder() {
  el("outlineTitle").value = state.title;
  el("outlineH1").value = state.h1;
  renderOutlineRows();
  renderOutlineFaqRows();
}

function renderOutlineRows() {
  const box = el("outlineRows");
  box.innerHTML = "";
  state.outlineRows.forEach((row, idx) => {
    const div = document.createElement("div");
    div.className = row.is_new ? "outline-row outline-row-new" : "outline-row";
    div.innerHTML = `
      <select class="outline-level" data-idx="${idx}">
        <option value="H2" ${row.level === "H2" ? "selected" : ""}>H2</option>
        <option value="H3" ${row.level === "H3" ? "selected" : ""}>H3</option>
        <option value="H4" ${row.level === "H4" ? "selected" : ""}>H4</option>
      </select>
      <input type="text" class="outline-text" data-idx="${idx}" value="${escapeAttr(row.text)}">
      ${row.is_new ? '<span class="new-badge">NEW</span>' : ""}
      <button class="btn-icon" data-action="up" data-idx="${idx}" title="Move up">&uarr;</button>
      <button class="btn-icon" data-action="down" data-idx="${idx}" title="Move down">&darr;</button>
      <button class="btn-icon" data-action="remove" data-idx="${idx}" title="Remove">&times;</button>`;
    box.appendChild(div);
  });
}

el("outlineRows").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const idx = Number(btn.dataset.idx);
  if (btn.dataset.action === "remove") {
    state.outlineRows.splice(idx, 1);
  } else if (btn.dataset.action === "up" && idx > 0) {
    [state.outlineRows[idx - 1], state.outlineRows[idx]] = [state.outlineRows[idx], state.outlineRows[idx - 1]];
  } else if (btn.dataset.action === "down" && idx < state.outlineRows.length - 1) {
    [state.outlineRows[idx + 1], state.outlineRows[idx]] = [state.outlineRows[idx], state.outlineRows[idx + 1]];
  }
  syncOutlineRowsFromDOM();
  renderOutlineRows();
});

el("outlineRows").addEventListener("change", (e) => {
  if (e.target.classList.contains("outline-level")) {
    state.outlineRows[Number(e.target.dataset.idx)].level = e.target.value;
  }
});

function syncOutlineRowsFromDOM() {
  document.querySelectorAll(".outline-text").forEach((input) => {
    const idx = Number(input.dataset.idx);
    if (state.outlineRows[idx]) state.outlineRows[idx].text = input.value;
  });
}

function renderOutlineFaqRows() {
  const box = el("outlineFaqRows");
  box.innerHTML = "";
  state.outlineFaqs.forEach((q, idx) => {
    const div = document.createElement("div");
    div.className = "outline-faq-row";
    div.innerHTML = `
      <input type="text" class="outline-faq-text" data-idx="${idx}" value="${escapeAttr(q)}">
      <button class="btn-icon" data-action="remove-faq" data-idx="${idx}" title="Remove">&times;</button>`;
    box.appendChild(div);
  });
}

el("outlineFaqRows").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-action='remove-faq']");
  if (!btn) return;
  state.outlineFaqs.splice(Number(btn.dataset.idx), 1);
  renderOutlineFaqRows();
});

el("btnAddFaq").addEventListener("click", () => {
  state.outlineFaqs.push("New FAQ question?");
  renderOutlineFaqRows();
});

// ---------- Step 4 -> 5: Generate ----------

el("btnGenerate").addEventListener("click", () => {
  state.title = el("outlineTitle").value.trim();
  state.h1 = el("outlineH1").value.trim();
  syncOutlineRowsFromDOM();
  document.querySelectorAll(".outline-faq-text").forEach((input) => {
    const idx = Number(input.dataset.idx);
    if (state.outlineFaqs[idx] !== undefined) state.outlineFaqs[idx] = input.value;
  });

  el("outlineOutput").value = buildMarkdown();
  renderExportPreview();
  showStep(5);
});

function renderExportPreview() {
  el("outlinePreview").innerHTML = mdToHtml(el("outlineOutput").value);
}

el("outlineOutput").addEventListener("input", renderExportPreview);

function mdToHtml(markdown) {
  const html = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };
  markdown.split("\n").forEach((rawLine) => {
    const line = rawLine.trim();
    if (line === "") return;
    if (line === "---") {
      closeList();
      html.push("<hr>");
      return;
    }
    const headerMatch = line.match(/^(#{1,4})\s+(.*)$/);
    if (headerMatch) {
      closeList();
      const level = headerMatch[1].length;
      html.push(`<h${level}><span class="preview-level">(H${level})</span>${escapeHtml(headerMatch[2])}</h${level}>`);
      return;
    }
    const bulletMatch = line.match(/^-\s+(.*)$/);
    if (bulletMatch) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${escapeHtml(bulletMatch[1]).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</li>`);
      return;
    }
    closeList();
    const boldMatch = line.match(/^\*\*(.*)\*\*$/);
    if (boldMatch) {
      html.push(`<p class="preview-faq">${escapeHtml(boldMatch[1])}</p>`);
      return;
    }
    const italicMatch = line.match(/^_(.*)_$/);
    if (italicMatch) {
      html.push(`<p class="preview-meta">${escapeHtml(italicMatch[1])}</p>`);
      return;
    }
    if (line.toLowerCase().startsWith("title tag:")) {
      html.push(`<p class="preview-titletag"><strong>Title tag:</strong> ${escapeHtml(line.slice(10).trim())}</p>`);
      return;
    }
    html.push(`<p>${escapeHtml(line)}</p>`);
  });
  closeList();
  return html.join("\n");
}

el("btnDownloadDocx").addEventListener("click", async () => {
  showGlobalError(null);
  const btn = el("btnDownloadDocx");
  setBusy(btn, true, "Preparing...");
  try {
    const resp = await fetch("/api/export/docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: state.title,
        h1: state.h1,
        primary_keyword: state.primaryKeyword,
        secondary_keywords: state.secondaryKeywords,
        client_url: state.clientUrl,
        outline_rows: state.outlineRows,
        faqs: state.outlineFaqs,
        tfidf_terms: state.tfidfTerms,
      }),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(data.error || `Request failed (${resp.status})`);
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const slug = (state.primaryKeyword || "outline").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    a.href = url;
    a.download = `${slug || "content-outline"}.docx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    showGlobalError(err.message);
  } finally {
    setBusy(btn, false);
  }
});

function buildMarkdown() {
  const lines = [];
  lines.push(`Title tag: ${state.title}`);
  lines.push("");
  lines.push(`_Primary keyword: ${state.primaryKeyword}_`);
  if (state.secondaryKeywords) lines.push(`_Secondary keywords: ${state.secondaryKeywords}_`);
  if (state.clientUrl) lines.push(`_Client: ${state.clientUrl}_`);
  lines.push("");
  lines.push("---");
  lines.push("");
  lines.push(`# ${state.h1}`);
  lines.push("");
  state.outlineRows.forEach((row) => {
    const hashes = "#".repeat(Number(row.level.replace("H", "")));
    lines.push(`${hashes} ${row.text}`);
    lines.push("");
  });
  if (state.outlineFaqs.length > 0) {
    lines.push("## FAQs");
    lines.push("");
    state.outlineFaqs.forEach((q) => {
      lines.push(`**${q}**`);
      lines.push("");
    });
  }
  const keywordTargets = state.tfidfTerms.filter((t) => t.max_uses).slice(0, 15);
  if (keywordTargets.length > 0) {
    lines.push("## Keyword usage targets");
    lines.push("");
    keywordTargets.forEach((t) => {
      lines.push(`- **${t.term}**: ${t.min_uses}–${t.max_uses} times`);
    });
    lines.push("");
  }
  return lines.join("\n");
}

el("btnStartOver").addEventListener("click", () => {
  window.location.reload();
});

el("btnCopy").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(el("outlineOutput").value);
    const btn = el("btnCopy");
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => (btn.textContent = original), 1500);
  } catch (err) {
    showGlobalError("Couldn't copy to clipboard — select the text and copy manually.");
  }
});

el("btnDownload").addEventListener("click", () => {
  const blob = new Blob([el("outlineOutput").value], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const slug = (state.primaryKeyword || "outline").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  a.href = url;
  a.download = `${slug || "content-outline"}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

// ---------- utils ----------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/"/g, "&quot;");
}
