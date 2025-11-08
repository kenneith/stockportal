
const TABS = ["M0","M1","M2","M3","M4","M5","M6","M7","M8"];
let currentTab = "M0";
let allStocks = [];
let selectedTicker = null;

function el(tag, cls, text){
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function showError(msg){
  console.error("[M-View]", msg);
}

async function fetchJSON(url){
  const r = await fetch(url);
  if (r.status === 401){
    // 未登入：顯示登入畫面，隱藏主畫面
    const lw = document.querySelector('.page--login'); if (lw) lw.style.display = 'block';
    const mv = document.getElementById('mviewCard'); if (mv) mv.style.display = 'none';
    throw new Error('401 unauth — ' + url);
  }
  if (!r.ok){
    const t = await r.text();
    throw new Error(r.status + " " + r.statusText + " — " + url + "\n" + t);
  }
  return r.json();
}

async function initTabs(){
  const nav = document.getElementById("mv-tabs");
  if (!nav) return;
  nav.innerHTML = "";
  let counts = {};
  try{
    const data = await fetchJSON("/api/mview/tabs");
    counts = data.counts || {};
  }catch(e){
    showError(e);
  }
  TABS.forEach(function(t){
    const btn = el("button","tab mv-tab" + (t===currentTab?" active":""), t + " (" + (counts[t]||0) + ")");
    btn.addEventListener("click", function(){
      currentTab = t;
      document.querySelectorAll(".mv-tab").forEach(function(b){ b.classList.remove("active"); });
      btn.classList.add("active");
      loadList();
    });
    nav.appendChild(btn);
  });
}

function renderList(){
  const ul = document.getElementById("mv-stock-list");
  const empty = document.getElementById("mv-empty");
  const kw = (document.getElementById("mv-filter").value || "").trim();
  ul.innerHTML = "";

  const rows = !kw ? allStocks : allStocks.filter(function(r){
    return (r.ticker||"").includes(kw) || (r.name||"").includes(kw);
  });

  if (!rows.length){
    if (empty) empty.style.display = "block";
    return;
  }
  if (empty) empty.style.display = "none";

  rows.forEach(function(r){
    const li = el("li","mv-item list-item");
    const box = el("div");
    box.appendChild(el("div","mv-name", (r.name||"") + " (" + (r.ticker||"") + ")"));
    box.appendChild(el("div","mv-meta", r.industry || ""));
    li.appendChild(box);

    const action = (r.action || "觀望").trim();
    const tag = el("span","tag " + (action==="買進"?"tag-positive":"tag-neutral"), action);
    li.appendChild(tag);

    li.addEventListener("click", function(){
      selectedTicker = r.ticker;
      loadDetail();
    });

    ul.appendChild(li);
  });
}

async function loadList(){
  try{
    const data = await fetchJSON("/api/mview/stocks?tab=" + encodeURIComponent(currentTab));
    allStocks = data;
    renderList();
    if (!selectedTicker && allStocks.length){
      selectedTicker = allStocks[0].ticker;
      loadDetail();
    }
  }catch(e){
    showError(e);
  }
}

function colorClass(c){
  if (c === "red" || c === "green" || c === "gray") return c;
  return "gray";
}

function renderIndicators(targetId, arr){
  const host = document.getElementById(targetId);
  if (!host) return;
  host.innerHTML = "";
  (arr || []).forEach(function(it){
    const row = el("div","kv");
    row.appendChild(el("div","k", it.name || ""));
    const val = (it.value === null || it.value === undefined || it.value === "") ? "—" : it.value;
    const v = el("div","v " + colorClass(it.color), String(val));
    row.appendChild(v);
    host.appendChild(row);
  });
}


async function loadDetail(){
  if (!selectedTicker) return;
  try{
    const det = await fetchJSON("/api/mview/stock/" + encodeURIComponent(selectedTicker));

    // 更新圖表上方資訊
    const codeEl = document.getElementById("mv-stock-code");
    const nameEl = document.getElementById("mv-stock-name");
    const priceEl = document.getElementById("mv-stock-latest-price");
    const dateEl = document.getElementById("mv-stock-latest-date");
    const summaryEl = document.getElementById("mv-stock-summary");

    if (codeEl) codeEl.textContent = det.ticker || selectedTicker || "";
    if (nameEl) nameEl.textContent = det.name || "";
    if (priceEl){
      const p = det.last_price;
      priceEl.textContent = (p === null || p === undefined || p === "")
        ? ""
        : ("最新價：" + p);
    }
    if (dateEl){
      dateEl.textContent = det.trade_date ? ("(" + det.trade_date + ")") : "";
    }
    if (summaryEl){
      summaryEl.textContent = det.summary || "";
    }

    // 指標內容
    renderIndicators("mv-daily", det.daily);
    renderIndicators("mv-monthly", det.monthly);

    // 繪製走勢
    drawSeries(det.ticker || selectedTicker);
  }catch(e){
    showError(e);
  }
}


async function drawSeries(ticker){
  const div = document.getElementById("mv-chart");
  if (!div) return;
  // 清空圖表內容，避免顯示載入中文字
  div.textContent = "";

  try{
    const data = await fetchJSON("/api/series/" + encodeURIComponent(ticker) + "?days=120");
    if (!Array.isArray(data) || !data.length){
      div.textContent = "暫無走勢資料。";
      return;
    }

    const dates = data.map(function(d){return d.date;});
    const o = data.map(function(d){return d.open;});
    const h = data.map(function(d){return d.max;});
    const l = data.map(function(d){return d.min;});
    const c = data.map(function(d){return d.close;});
    const v = data.map(function(d){return d.volume_lots;});

    const k = {
      x: dates,
      open: o,
      high: h,
      low: l,
      close: c,
      type: "candlestick",
      name: "K",
      increasing: { line: { color: "#52c41a" }, fillcolor: "#52c41a" },
      decreasing: { line: { color: "#f97373" }, fillcolor: "#f97373" }
    };

    const line = {
      x: dates,
      y: c,
      type: "scatter",
      name: "收盤價",
      line: { color: "#f59e0b", width: 1.4 }
    };

    const vol = {
      x: dates,
      y: v,
      type: "bar",
      name: "成交量(張)",
      xaxis: "x2",
      yaxis: "y2",
      marker: { color: "#7aa2f7" },
      opacity: 0.6
    };

    const layout = {
      font: { color: "#e6eef7" },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      hovermode: "x unified",
      hoverdistance: 50,
      spikedistance: -1,
      margin: { l: 40, r: 40, t: 40, b: 30 },
      // 上方主圖（價格/K）
      xaxis: {
        domain: [0, 1],
        rangeslider: { visible: false },
        showspikes: true,
        spikesnap: "cursor",
        spikemode: "across",
        spikethickness: 1,
        spikecolor: "#9CA3AF"
      },
      yaxis: {
        domain: [0.32, 1],
        title: { text: "價格", standoff: 10 },
        automargin: true
      },
      // 下方副圖（成交量）
      xaxis2: {
        domain: [0, 1],
        matches: "x",
        showticklabels: false,
        showspikes: true,
        spikesnap: "cursor",
        spikethickness: 1,
        spikecolor: "#9CA3AF"
      },
      yaxis2: {
        domain: [0, 0.25],
        title: { text: "量", standoff: 10 },
        automargin: true,
        showgrid: false
      },
      bargap: 0.1,
      legend: {
        orientation: "h",
        x: 0,
        y: 1.05,
        xanchor: "left",
        yanchor: "bottom",
        bgcolor: "rgba(0,0,0,0)"
      }
    };

    Plotly.purge(div);
    Plotly.newPlot(div, [k, line, vol], layout, { displayModeBar: false, responsive: true });

  }catch(e){
    showError(e);
    div.textContent = "無法載入走勢資料。";
  }
}


function bindKpiTabs(){
  const tabs = document.querySelector(".mv-kpi-tabs");
  if (!tabs) return;
  tabs.addEventListener("click", function(ev){
    const btn = ev.target.closest("[data-kpi-tab]");
    if (!btn) return;
    const target = btn.getAttribute("data-kpi-tab");
    tabs.querySelectorAll("[data-kpi-tab]").forEach(function(b){
      b.classList.toggle("active", b === btn);
    });
    const daily = document.getElementById("mv-daily");
    const monthly = document.getElementById("mv-monthly");
    if (!daily || !monthly) return;
    if (target === "monthly"){
      daily.style.display = "none";
      monthly.style.display = "";
    }else{
      daily.style.display = "";
      monthly.style.display = "none";
    }
  });
}
function bindFilter(){
  const input = document.getElementById("mv-filter");
  if (!input) return;
  input.addEventListener("input", renderList);
}

window.initMView = async function(){
  bindFilter();
  bindKpiTabs();
  await initTabs();
  await loadList();
};
