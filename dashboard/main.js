/* ════════════════════════════════════════
   HoLo Dashboard — Main JavaScript
   The Truth-Led Booking Platform
   ════════════════════════════════════════ */

const API_BASE = window.location.protocol.startsWith('http') ? '' : "http://127.0.0.1:8000";
const REFRESH_INTERVAL = 15000; // 15 seconds

// ── State ──────────────────────────────────────────────────────────────────

let allHotels = [];
let activeFilter = "all";

// ── Utility ────────────────────────────────────────────────────────────────

function scoreColor(score) {
  if (score >= 85) return "var(--score-great)";
  if (score >= 70) return "var(--score-good)";
  if (score >= 55) return "var(--score-warn)";
  return "var(--score-bad)";
}

function scoreClass(score) {
  if (score >= 85) return "score-great";
  if (score >= 70) return "score-good";
  if (score >= 55) return "score-warn";
  return "score-bad";
}

function scoreEmoji(score) {
  if (score >= 85) return "✅";
  if (score >= 70) return "👍";
  if (score >= 55) return "⚠️";
  return "🚨";
}

function formatNaira(amount) {
  return `₦${amount.toLocaleString()}`;
}

function timeAgo(isoString) {
  const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function animateCounter(el, target, suffix = "") {
  const duration = 1200;
  const start = parseInt(el.textContent) || 0;
  const startTime = performance.now();

  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    el.textContent = Math.round(start + (target - start) * eased) + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

async function triggerDemoVote() {
  try {
    const res = await fetch(`${API_BASE}/admin/trigger-vote`, { method: "POST" });
    if (!res.ok) throw new Error('Backend unavailable');
    const data = await res.json();
    alert(`🚀 HoLo Broadcast: Sent to ${data.users_reached} active seekers!`);
  } catch (err) {
    // Demo fallback
    alert(`🚀 HoLo Demo: Broadcast simulated! 47 active seekers in your area would receive this.`);
  }
}

async function triggerLiveIntel() {
  const btn = document.getElementById("intel-scan-btn");
  const text = document.getElementById("intel-btn-text");
  
  if (btn.classList.contains("scanning")) return;
  
  btn.classList.add("scanning");
  text.textContent = "Crawling Google & Booking...";
  
  try {
    const res = await fetch(`${API_BASE}/dashboard/intelligence/update`, { method: "POST" });
    if (!res.ok) throw new Error('Backend unavailable');
    
    setTimeout(() => {
      text.textContent = "Scan Running in Background...";
      setTimeout(() => {
        btn.classList.remove("scanning");
        text.textContent = "Deep Intel Scan";
        alert("🔍 HoLo Intelligence: Deep crawl started. Truth Scores will update live as data comes in!");
      }, 3000);
    }, 2000);
    
  } catch (err) {
    // Demo mode fallback
    setTimeout(() => {
      text.textContent = "Scanning Lagos hotels...";
      setTimeout(() => {
        btn.classList.remove("scanning");
        text.textContent = "Deep Intel Scan";
        alert("🔍 HoLo Demo: Intel scan complete! 12 hotels scanned across Yaba, Lekki, VI, Ikeja, and Surulere. Truth Scores are up to date.");
      }, 3000);
    }, 2000);
  }
}

// ── Stats Section ──────────────────────────────────────────────────────────

async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/dashboard/stats`);
    const data = await res.json();

    animateCounter(document.getElementById("stat-num-hotels"), data.total_hotels);
    animateCounter(document.getElementById("stat-num-votes"), data.total_votes);
    animateCounter(document.getElementById("stat-num-avg"), Math.round(data.avg_truth_score));
    animateCounter(document.getElementById("stat-num-verified"), data.verified_hotels);

    renderAreaGrid(data.area_breakdown);
  } catch (err) {
    console.warn("Stats load failed — showing demo data", err);
    renderDemoStats();
  }
}

function renderDemoStats() {
  // Demo fallback when backend isn't running
  animateCounter(document.getElementById("stat-num-hotels"), 12);
  animateCounter(document.getElementById("stat-num-votes"), 367);
  animateCounter(document.getElementById("stat-num-avg"), 74);
  animateCounter(document.getElementById("stat-num-verified"), 7);

  const demoAreas = [
    { area: "Yaba", avg_truth_score: 68, hotel_count: 4, verified_count: 2 },
    { area: "Lekki", avg_truth_score: 81, hotel_count: 3, verified_count: 2 },
    { area: "Victoria Island", avg_truth_score: 89, hotel_count: 2, verified_count: 2 },
    { area: "Ikeja", avg_truth_score: 72, hotel_count: 2, verified_count: 1 },
    { area: "Surulere", avg_truth_score: 57, hotel_count: 1, verified_count: 0 },
  ];
  renderAreaGrid(demoAreas);
}

// ── Area Grid ──────────────────────────────────────────────────────────────

function renderAreaGrid(areas) {
  const grid = document.getElementById("area-grid");
  if (!areas || !areas.length) { grid.innerHTML = "<p>No area data yet.</p>"; return; }

  grid.innerHTML = areas.map(a => `
    <div class="area-card" style="--area-color: ${scoreColor(a.avg_truth_score)}" data-area="${a.area}">
      <div class="area-name">${a.area}</div>
      <div class="area-score ${scoreClass(a.avg_truth_score)}">${a.avg_truth_score}</div>
      <div class="area-meta">${a.hotel_count} hotels · ${a.verified_count} verified ≥80</div>
    </div>
  `).join("");
}

// ── Hotel Grid ──────────────────────────────────────────────────────────────

async function loadHotels() {
  const grid = document.getElementById("hotel-grid");
  try {
    const res = await fetch(`${API_BASE}/dashboard/hotels`);
    const data = await res.json();
    allHotels = data.hotels || [];
  } catch (err) {
    console.warn("Hotels load failed — using demo data", err);
    allHotels = getDemoHotels();
  }
  renderHotels();
}

function renderHotels() {
  const grid = document.getElementById("hotel-grid");
  const filtered = activeFilter === "all"
    ? allHotels
    : allHotels.filter(h => h.area === activeFilter);

  if (!filtered.length) {
    grid.innerHTML = `<div class="loading-spinner"><p>No hotels found for this area.</p></div>`;
    return;
  }

  grid.innerHTML = filtered.map(h => {
    const isLabaLaba = h.truth_score < 60 && h.total_votes > 10;
    
    return `
    <div class="hotel-card" id="hotel-card-${h.id}">
      <div class="hotel-card-header">
        <div style="flex:1">
          <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap">
            <div class="hotel-name">${h.name}</div>
            ${isLabaLaba ? `<span class="laba-alert">⚠️ Laba Laba Alert</span>` : ''}
          </div>
          <span class="hotel-area-tag">${h.area}</span>
        </div>
        <div class="truth-score-badge">
          <div class="truth-score-num ${scoreClass(h.truth_score)}">${h.truth_score}</div>
          <div class="truth-score-label">Truth Score</div>
        </div>
      </div>

      <div class="truth-badges-row">
        ${h.power_score >= 90 ? `<span class="truth-badge power">⚡ Verified Power</span>` : ''}
        ${h.wifi_score >= 85 ? `<span class="truth-badge wifi">📶 Fiber Wi-Fi</span>` : ''}
        ${h.security_score >= 90 ? `<span class="truth-badge security">🛡️ Secure Base</span>` : ''}
      </div>

      <div class="score-bars">
        ${scorebar("⚡", "Power", h.power_score, h.id, "power")}
        ${scorebar("📶", "Wi-Fi", h.wifi_score, h.id, "wifi")}
        ${scorebar("🛡️", "Security", h.security_score || 70, h.id, "security")}
        ${scorebar("🤝", "Staff", h.staff_score || 75, h.id, "staff")}
      </div>

      <div class="vibe-meter">
        <span class="vibe-pulse ${h.staff_score < 60 ? 'low' : h.staff_score < 80 ? 'mid' : ''}"></span>
        Staff Vibe: ${h.staff_score < 60 ? 'Avoid' : h.staff_score < 80 ? 'Functional' : 'Exceptional'}
      </div>

      <div class="hotel-summary">${h.review_summary || ""}</div>

      <div class="hotel-footer">
        <div class="hotel-price">${formatNaira(h.price_naira)} <span>/ night</span></div>
        <div class="hotel-votes">${h.total_votes} votes ${scoreEmoji(h.truth_score)}</div>
      </div>
    </div>
  `}).join("");

  // Animate score bars after render
  requestAnimationFrame(() => {
    document.querySelectorAll(".score-bar-fill[data-score]").forEach(bar => {
      const score = parseFloat(bar.dataset.score);
      bar.style.width = score + "%";
      bar.style.background = scoreColor(score);
    });
  });
}

function scorebar(icon, label, score, hotelId, type) {
  return `
    <div class="score-row">
      <span class="score-icon">${icon}</span>
      <span class="score-key">${label}</span>
      <div class="score-bar-track">
        <div class="score-bar-fill ${type}" data-score="${score}" data-hotel="${hotelId}"></div>
      </div>
      <span class="score-val">${score}</span>
    </div>
  `;
}

// ── Filter Pills ────────────────────────────────────────────────────────────

document.getElementById("filter-pills").addEventListener("click", (e) => {
  const pill = e.target.closest(".pill");
  if (!pill) return;
  document.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
  pill.classList.add("active");
  activeFilter = pill.dataset.area;
  renderHotels();
});

// ── Activity Feed ──────────────────────────────────────────────────────────

async function loadActivity() {
  const feed = document.getElementById("activity-feed");
  try {
    const res = await fetch(`${API_BASE}/dashboard/activity`);
    const data = await res.json();
    renderActivity(data.activity || []);
  } catch (err) {
    renderActivity(getDemoActivity());
  }
}

function renderActivity(items) {
  const feed = document.getElementById("activity-feed");
  if (!items.length) {
    feed.innerHTML = `<div class="loading-spinner"><p>No votes yet. Send a test SMS!</p></div>`;
    return;
  }

  feed.innerHTML = items.map(item => `
    <div class="activity-item">
      <div class="activity-icon">${item.power_ok ? "✅" : "❌"}</div>
      <div class="activity-text">
        <div class="activity-hotel">${item.hotel_name}</div>
        <div class="activity-label">${item.label}</div>
      </div>
      <div class="activity-time">${timeAgo(item.time)}</div>
    </div>
  `).join("");
}

// ── SMS Demo Animation ─────────────────────────────────────────────────────

function runSmsDemo() {
  const typing = document.getElementById("demo-typing");
  const reply = document.getElementById("demo-reply");

  // Show typing → then reply after 2.5s
  setTimeout(() => {
    typing.classList.add("hidden");
    reply.classList.remove("hidden");
    reply.style.animation = "fade-in-up 0.4s ease";
  }, 2800);

  // Reset and loop every 10 seconds
  setInterval(() => {
    typing.classList.remove("hidden");
    reply.classList.add("hidden");
    setTimeout(() => {
      typing.classList.add("hidden");
      reply.classList.remove("hidden");
    }, 2800);
  }, 10000);
}

// ── Scroll Reveal ─────────────────────────────────────────────────────────

function initReveal() {
  const reveals = document.querySelectorAll(".reveal");
  const observerOptions = {
    threshold: 0.15,
    rootMargin: "0px 0px -50px 0px"
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("active");
        // Once revealed, no need to observe anymore
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  reveals.forEach(reveal => observer.observe(reveal));
}

// ── Demo Fallback Data ──────────────────────────────────────────────────────

function getDemoHotels() {
  return [
    { id: 1, name: "Caritas Inn Yaba", area: "Yaba", price_naira: 19500, truth_score: 91, power_score: 95, wifi_score: 88, security_score: 92, staff_score: 90, total_votes: 42, review_summary: "HoLo Verified: Excellent power reliability. Fast Wi-Fi at 45Mbps. Top choice for Yaba tech professionals." },
    { id: 2, name: "The Hub Suites", area: "Yaba", price_naira: 14500, truth_score: 42, power_score: 35, wifi_score: 50, security_score: 48, staff_score: 45, total_votes: 28, review_summary: "HoLo Alert: Major 'Laba Laba' detected. Generator schedule is irregular despite 24/7 claims. Staff can be difficult." },
    { id: 3, name: "Lekki Pearl Suites", area: "Lekki", price_naira: 38000, truth_score: 93, power_score: 97, wifi_score: 92, security_score: 95, staff_score: 94, total_votes: 67, review_summary: "HoLo Verified ⭐: Near 24/7 power via solar + grid. 80Mbps fiber. Extremely polite and professional staff." },
    { id: 4, name: "VI Executive Residences", area: "Victoria Island", price_naira: 55000, truth_score: 96, power_score: 99, wifi_score: 95, security_score: 98, staff_score: 97, total_votes: 89, review_summary: "HoLo Verified ⭐⭐: Maximum security with gated access and armed guards. Premium service standards." },
    { id: 5, name: "Mainland Comfort Hotel", area: "Yaba", price_naira: 22000, truth_score: 78, power_score: 82, wifi_score: 74, security_score: 76, staff_score: 80, total_votes: 33, review_summary: "HoLo Approved: Solid inverter system. Wi-Fi average 30Mbps. Safe neighborhood feel." },
    { id: 6, name: "Airport View Hotel", area: "Ikeja", price_naira: 28000, truth_score: 75, power_score: 78, wifi_score: 72, security_score: 80, staff_score: 70, total_votes: 38, review_summary: "HoLo Approved: Gen kicks in fast. Airport security presence is a plus. Standard service." },
  ];
}

function getDemoActivity() {
  const now = new Date();
  return [
    { hotel_name: "Caritas Inn Yaba", label: "✅ Power OK", power_ok: true, time: new Date(now - 30000).toISOString() },
    { hotel_name: "The Hub Suites", label: "❌ Power Issues", power_ok: false, time: new Date(now - 120000).toISOString() },
    { hotel_name: "Lekki Pearl Suites", label: "✅ Power OK", power_ok: true, time: new Date(now - 300000).toISOString() },
    { hotel_name: "VI Executive Residences", label: "✅ Power OK", power_ok: true, time: new Date(now - 600000).toISOString() },
    { hotel_name: "Mainland Comfort Hotel", label: "✅ Power OK", power_ok: true, time: new Date(now - 900000).toISOString() },
  ];
}

// ── Refresh Loop ────────────────────────────────────────────────────────────

async function refreshAll() {
  await Promise.all([loadStats(), loadActivity()]);
  // Quietly refresh hotel scores too
  try {
    const res = await fetch(`${API_BASE}/dashboard/hotels`);
    const data = await res.json();
    if (data.hotels) {
      allHotels = data.hotels;
      renderHotels();
    }
  } catch (_) { /* silent fail */ }
}

// ── Mobile Menu ─────────────────────────────────────────────────────────────

function initMobileMenu() {
  const toggle = document.getElementById("menu-toggle");
  const menu = document.getElementById("mobile-menu");
  const links = document.querySelectorAll(".mobile-link");

  if (!toggle || !menu) return;

  toggle.addEventListener("click", () => {
    toggle.classList.toggle("active");
    menu.classList.toggle("active");
    document.body.style.overflow = menu.classList.contains("active") ? "hidden" : "";
  });

  links.forEach(link => {
    link.addEventListener("click", () => {
      toggle.classList.remove("active");
      menu.classList.remove("active");
      document.body.style.overflow = "";
    });
  });
}

// ── Init ────────────────────────────────────────────────────────────────────

async function init() {
  await Promise.all([loadStats(), loadHotels(), loadActivity()]);
  runSmsDemo();
  initReveal();
  initMobileMenu();

  // Auto-refresh every 15s
  setInterval(refreshAll, REFRESH_INTERVAL);
}

document.addEventListener("DOMContentLoaded", init);
