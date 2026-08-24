// Telegram WebApp Initialization
if (window.Telegram && window.Telegram.WebApp) {
  const tg = window.Telegram.WebApp;
  tg.ready();
  tg.expand();
}

let salesChartInstance = null;
let currentLots = [];

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupModal();
  setupSettingsToggles();
  loadAllData();

  document.getElementById("refreshBtn").addEventListener("click", () => {
    loadAllData();
  });
});

function setupTabs() {
  const tabBtns = document.querySelectorAll(".nav-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
    });
  });
}

function setupModal() {
  const modal = document.getElementById("stockModal");
  const openBtn = document.getElementById("addStockModalBtn");
  const closeBtn = document.getElementById("closeModalBtn");
  const submitBtn = document.getElementById("submitStockBtn");

  openBtn.addEventListener("click", () => {
    modal.classList.remove("hidden");
  });

  closeBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
  });

  submitBtn.addEventListener("click", async () => {
    const lotId = document.getElementById("modalLotSelect").value;
    const text = document.getElementById("modalStockText").value;
    const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);

    if (!lotId || lines.length === 0) {
      alert("Пожалуйста, выберите товар и введите хотя бы одну строку товара.");
      return;
    }

    submitBtn.innerText = "Загрузка...";
    submitBtn.disabled = true;

    try {
      const res = await fetch("/api/stock/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lot_id: lotId, items: lines }),
      });
      const data = await res.json();
      if (data.success) {
        alert(`✅ Успешно добавлено ${data.added} шт. на склад!`);
        document.getElementById("modalStockText").value = "";
        modal.classList.add("hidden");
        loadLots();
        loadStats();
      } else {
        alert("Ошибка: " + (data.error || "Не удалось пополнить склад"));
      }
    } catch (e) {
      alert("Ошибка сети: " + e.message);
    } finally {
      submitBtn.innerText = "Загрузить на склад";
      submitBtn.disabled = false;
    }
  });
}

async function loadAllData() {
  await Promise.all([loadStats(), loadLots(), loadOrders(), loadSettings()]);
}

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();

    if (data.account) {
      document.getElementById("accountUsername").innerText = data.account.username || "Artiba4548";
      document.getElementById("accountBalance").innerText = (data.account.balance || 0).toLocaleString("ru-RU", { minimumFractionDigits: 2 }) + " ₽";
    }

    if (data.stats) {
      const w = data.stats.week || {};
      const t = data.stats.today || {};
      const a = data.stats.all || {};

      document.getElementById("metricWeekRevenue").innerText = (w.total_revenue || 0).toLocaleString("ru-RU", { minimumFractionDigits: 2 }) + " ₽";
      document.getElementById("metricTodayRevenue").innerText = `Сегодня: ${(t.total_revenue || 0).toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₽`;
      document.getElementById("metricDeliveredOrders").innerText = a.delivered_orders || 0;
      document.getElementById("metricTotalOrders").innerText = `Всего в базе: ${a.total_orders || 0}`;
      document.getElementById("metricAvgCheck").innerText = (a.avg_check || 0).toLocaleString("ru-RU", { minimumFractionDigits: 2 }) + " ₽";
    }

    renderChart(data.stats);
    renderTopProducts(data.top_products || []);
  } catch (e) {
    console.error("Error loading stats:", e);
  }
}

function renderChart(stats) {
  const ctx = document.getElementById("salesChart");
  if (!ctx) return;

  if (salesChartInstance) {
    salesChartInstance.destroy();
  }

  const labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
  const rev = (stats && stats.week && stats.week.total_revenue) ? stats.week.total_revenue : 500;
  const dataPoints = [rev * 0.1, rev * 0.15, rev * 0.12, rev * 0.2, rev * 0.18, rev * 0.25, rev];

  salesChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Выручка (₽)",
        data: dataPoints,
        borderColor: "#6366f1",
        backgroundColor: "rgba(99, 102, 241, 0.15)",
        fill: true,
        tension: 0.4,
        borderWidth: 3,
        pointBackgroundColor: "#a855f7",
        pointBorderColor: "#fff",
        pointRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94a3b8", font: { size: 10 } }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94a3b8", font: { size: 10 } }
        }
      }
    }
  });
}

function renderTopProducts(products) {
  const tbody = document.querySelector("#topProductsTable tbody");
  if (!tbody) return;

  if (products.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Пока нет завершенных продаж</td></tr>';
    return;
  }

  tbody.innerHTML = products.map((p, i) => `
    <tr>
      <td><b>#${i + 1}</b></td>
      <td>${p.title.length > 35 ? p.title.substring(0, 35) + "..." : p.title}</td>
      <td><span class="tag-badge">${p.count} шт.</span></td>
      <td><b>${p.revenue.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₽</b></td>
    </tr>
  `).join("");
}

async function loadLots() {
  try {
    const res = await fetch("/api/lots");
    const data = await res.json();
    currentLots = data.lots || [];

    const container = document.getElementById("lotsContainer");
    const select = document.getElementById("modalLotSelect");

    if (currentLots.length === 0) {
      container.innerHTML = '<div class="text-center text-muted p-4">Нет активных лотов.</div>';
      return;
    }

    select.innerHTML = currentLots.map(l => `<option value="${l.id}">${l.title} (${l.price} ₽)</option>`).join("");

    container.innerHTML = currentLots.map(l => {
      const inStock = l.stock_count > 0;
      return `
        <div class="glass-card lot-card">
          <div class="lot-left">
            <h4 class="lot-title">${l.title}</h4>
            <div class="lot-meta">
              <span>💰 ${l.price.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₽</span>
              <span>📁 ${l.category || "Разное"}</span>
            </div>
          </div>
          <div class="lot-right">
            <span class="stock-badge ${inStock ? 'in-stock' : 'out-of-stock'}">
              ${inStock ? '🟢 ' + l.stock_count + ' шт.' : '🔴 0 шт.'}
            </span>
          </div>
        </div>
      `;
    }).join("");
  } catch (e) {
    console.error("Error loading lots:", e);
  }
}

async function loadOrders() {
  try {
    const res = await fetch("/api/orders");
    const data = await res.json();
    const orders = data.orders || [];

    const container = document.getElementById("ordersContainer");
    if (orders.length === 0) {
      container.innerHTML = '<div class="text-center text-muted p-4">Нет недавних заказов.</div>';
      return;
    }

    const statusMap = {
      closed: { label: "Закрыт", class: "in-stock", icon: "✅" },
      paid: { label: "Оплачен", class: "tag-badge", icon: "⏳" },
      refunded: { label: "Возврат", class: "out-of-stock", icon: "↩️" },
    };

    container.innerHTML = orders.map(o => {
      const st = statusMap[o.status] || { label: o.status, class: "tag-badge", icon: "📦" };
      return `
        <div class="glass-card order-item">
          <div class="order-left">
            <h4 class="lot-title"><code>#${o.order_id}</code> | ${o.title.substring(0, 32)}...</h4>
            <div class="lot-meta">
              <span>👤 ${o.buyer_username}</span>
              <span>💰 ${o.price.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₽</span>
            </div>
          </div>
          <div class="order-right">
            <span class="stock-badge ${st.class}">${st.icon} ${st.label}</span>
          </div>
        </div>
      `;
    }).join("");
  } catch (e) {
    console.error("Error loading orders:", e);
  }
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();

    document.getElementById("set_auto_delivery").checked = !!data.auto_delivery;
    document.getElementById("set_auto_raise").checked = !!data.auto_raise;
    document.getElementById("set_ai_support").checked = !!data.ai_support;
    document.getElementById("set_smart_pricing").checked = !!data.smart_pricing;
    document.getElementById("set_night_surge").checked = !!data.night_surge;
    document.getElementById("set_upsell").checked = !!data.upsell;
  } catch (e) {
    console.error("Error loading settings:", e);
  }
}

function setupSettingsToggles() {
  const ids = ["set_auto_delivery", "set_auto_raise", "set_ai_support", "set_smart_pricing", "set_night_surge", "set_upsell"];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("change", async () => {
        const key = id.replace("set_", "");
        const payload = {};
        payload[key] = el.checked;

        await fetch("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      });
    }
  });
}
