"use strict";

const contaminantScores = {
  coagulase_negative_staphylococcus: 0.85,
  staphylococcus_epidermidis: 0.85,
  staphylococcus_haemolyticus: 0.80,
  staphylococcus_lugdunensis: 0.30,
  corynebacterium: 0.90,
  cutibacterium_acnes: 0.95,
  bacillus: 0.90,
  micrococcus: 0.95
};

const pathogenScores = {
  staphylococcus_aureus: 0.95,
  escherichia_coli: 0.98,
  klebsiella_pneumoniae: 0.97,
  pseudomonas_aeruginosa: 0.97,
  enterococcus_faecalis: 0.85,
  enterococcus_faecium: 0.85,
  candida_albicans: 0.98,
  candida_glabrata: 0.97,
  streptococcus_pneumoniae: 0.98,
  neisseria_meningitidis: 0.99
};

const organismAliases = {
  s_aureus: "staphylococcus_aureus",
  staph_aureus: "staphylococcus_aureus",
  e_coli: "escherichia_coli",
  p_aeruginosa: "pseudomonas_aeruginosa",
  c_acnes: "cutibacterium_acnes",
  cons: "coagulase_negative_staphylococcus"
};

const gramExpected = {
  gram_positive_cocci_clusters: "Staphylococcus aureus or coagulase-negative staphylococci",
  gram_positive_cocci_chains: "Streptococcus spp. or Enterococcus spp.",
  gram_negative_rods: "Enterobacterales, Pseudomonas, Acinetobacter, or other Gram-negative bacilli",
  gram_negative_diplococci: "Neisseria spp. and other Gram-negative cocci",
  gram_positive_rods: "Listeria, Corynebacterium, Bacillus, Clostridium, Cutibacterium, or others",
  yeast: "Candida spp., Cryptococcus spp., or other yeasts",
  "": "Not available"
};

let lastResult = null;

function slug(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function normaliseOrganism(value) {
  const key = slug(value);
  return organismAliases[key] || key;
}

function heuristicScore(organism, ttp, positive, total) {
  const key = normaliseOrganism(organism);
  let base = 0.5;

  if (Object.prototype.hasOwnProperty.call(contaminantScores, key)) {
    base = contaminantScores[key];
  } else if (Object.prototype.hasOwnProperty.call(pathogenScores, key)) {
    base = 1 - pathogenScores[key];
  }

  const ttpAdjustment = ttp > 36 ? 0.15 : (ttp < 12 ? -0.20 : 0);
  const ratio = positive / total;
  let bottleAdjustment = ratio === 1 && total >= 2 ? -0.25 : 0;
  if (ratio <= 0.5) {
    bottleAdjustment += 0.15;
  }

  return Math.max(0, Math.min(1, base + ttpAdjustment + bottleAdjustment));
}

function classify(score) {
  if (score >= 0.75) return "LIKELY_CONTAMINANT";
  if (score >= 0.40) return "INDETERMINATE";
  return "LIKELY_TRUE_PATHOGEN";
}

function ttpCategory(ttp) {
  if (ttp < 12) return "RAPID_GROWTH";
  if (ttp <= 36) return "NORMAL_GROWTH";
  return "SLOW_GROWTH";
}

function reviewPriority(gram, ttp, highRiskHost) {
  if (highRiskHost || ttp < 12 || ["gram_negative_rods", "gram_negative_diplococci", "yeast"].includes(gram)) {
    return "STAT";
  }
  if (ttp <= 24 || ["gram_positive_cocci_clusters", "gram_positive_cocci_chains"].includes(gram)) {
    return "URGENT";
  }
  return "ROUTINE";
}

function validate(ttp, positive, total, organism) {
  if (!organism.trim()) return "Enter an organism or organism group.";
  if (!Number.isFinite(ttp) || ttp < 0) return "TTP must be a non-negative number.";
  if (!Number.isInteger(positive) || positive < 0) return "Positive bottles must be a non-negative integer.";
  if (!Number.isInteger(total) || total < 1) return "Total bottles must be at least 1.";
  if (positive > total) return "Positive bottles cannot exceed total bottles.";
  return "";
}

function replaceList(items) {
  const list = document.getElementById("reviewPrompts");
  list.replaceChildren();
  items.forEach(function (item) {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
}

function analyze(event) {
  event.preventDefault();

  const organism = document.getElementById("organism").value;
  const gram = document.getElementById("gramStain").value;
  const ttp = Number(document.getElementById("ttp").value);
  const positive = Number(document.getElementById("positiveBottles").value);
  const total = Number(document.getElementById("totalBottles").value);
  const highRiskHost = document.getElementById("highRiskHost").checked;
  const error = validate(ttp, positive, total, organism);
  const validation = document.getElementById("validation");

  if (error) {
    validation.textContent = error;
    return;
  }
  validation.textContent = "";

  const score = heuristicScore(organism, ttp, positive, total);
  const classification = classify(score);
  const category = ttpCategory(ttp);
  const priority = reviewPriority(gram, ttp, highRiskHost);

  let interpretation = "The combined heuristic is indeterminate.";
  if (classification === "LIKELY_CONTAMINANT") {
    interpretation = "The supplied pattern has a high heuristic contamination score. Confirm against collection pattern, repeat cultures, devices, and clinical findings.";
  } else if (classification === "LIKELY_TRUE_PATHOGEN") {
    interpretation = "The supplied pattern has a low heuristic contamination score. Review the isolate as clinically significant until organism, susceptibility, source, and clinical context are reconciled.";
  }

  const prompts = [
    "Correlate TTP with organism identity, number of positive sets, collection site, and prior antimicrobial exposure.",
    "Use local microbiology and antimicrobial-stewardship procedures for clinical actions.",
    priority === "STAT" ? "Prioritize immediate review because an early/high-priority signal is present." : "Use the displayed priority as a workflow prompt, not a treatment order."
  ];

  if (classification === "LIKELY_CONTAMINANT") {
    prompts.push("Consider repeat peripheral sampling when uncertainty remains.");
  }
  if (normaliseOrganism(organism) === "staphylococcus_aureus") {
    prompts.push("Apply the local S. aureus bloodstream-infection pathway, including clearance and source assessment.");
  }
  if (normaliseOrganism(organism).startsWith("candida")) {
    prompts.push("Apply the local candidemia/fungemia pathway and source-control review.");
  }

  document.getElementById("classification").textContent = classification.replaceAll("_", " ");
  document.getElementById("score").textContent = Math.round(score * 100) + "%";
  document.getElementById("ttpCategory").textContent = category.replaceAll("_", " ");
  document.getElementById("priority").textContent = priority;
  document.getElementById("interpretation").textContent = interpretation;
  document.getElementById("likelyOrganisms").textContent = gramExpected[gram] || "Not resolved from the supplied morphology.";
  replaceList(prompts);

  lastResult = {
    organism: organism,
    normalised_organism: normaliseOrganism(organism),
    gram_stain: gram || null,
    ttp_hours: ttp,
    positive_bottles: positive,
    total_bottles: total,
    high_risk_host: highRiskHost,
    contamination_probability: Number(score.toFixed(2)),
    score_is_calibrated_probability: false,
    classification: classification,
    ttp_category: category,
    review_priority: priority,
    note: "Research/education heuristic; not a validated clinical prediction model."
  };
  document.getElementById("exportButton").disabled = false;
}

function exportJson() {
  if (!lastResult) return;
  const blob = new Blob([JSON.stringify(lastResult, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "blood-culture-analysis.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function loadSample() {
  document.getElementById("organism").value = "staphylococcus_aureus";
  document.getElementById("gramStain").value = "gram_positive_cocci_clusters";
  document.getElementById("ttp").value = "8.5";
  document.getElementById("positiveBottles").value = "2";
  document.getElementById("totalBottles").value = "2";
  document.getElementById("highRiskHost").checked = false;
  document.getElementById("analysisForm").requestSubmit();
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme || "light";
  setTheme(current === "dark" ? "light" : "dark");
}

const storedTheme = localStorage.getItem("theme");
if (storedTheme === "dark" || storedTheme === "light") {
  setTheme(storedTheme);
} else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
  document.documentElement.dataset.theme = "dark";
}

document.getElementById("analysisForm").addEventListener("submit", analyze);
document.getElementById("sampleButton").addEventListener("click", loadSample);
document.getElementById("exportButton").addEventListener("click", exportJson);
document.getElementById("themeToggle").addEventListener("click", toggleTheme);
