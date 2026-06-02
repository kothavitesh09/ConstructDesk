(function () {
  const shell = document.getElementById("appShell");
  document.getElementById("sidebarToggle")?.addEventListener("click", () => shell.classList.toggle("collapsed"));
  document.getElementById("mobileMenu")?.addEventListener("click", () => shell.classList.toggle("mobile-open"));

  document.querySelectorAll(".data-table").forEach((table) => {
    if (window.DataTable) new DataTable(table, { pageLength: 25, lengthMenu: [10, 25, 50, 100], order: [] });
  });

  const addRow = document.getElementById("addPatternRow");
  addRow?.addEventListener("click", () => {
    const tbody = document.querySelector("#patternTable tbody");
    tbody.insertAdjacentHTML("beforeend", `<tr><td><input name="flat_no[]" class="form-control form-control-sm" placeholder="A103"></td><td><input name="sft[]" type="number" class="form-control form-control-sm"></td><td><input name="facing[]" class="form-control form-control-sm"></td><td><button type="button" class="icon-btn remove-row"><i class="bi bi-trash"></i></button></td></tr>`);
  });
  document.getElementById("addTowerRow")?.addEventListener("click", () => {
    const tbody = document.querySelector("#towerTable tbody");
    tbody?.insertAdjacentHTML("beforeend", `<tr><td><input name="tower_name[]" class="form-control form-control-sm" placeholder="B"></td><td><input name="tower_floors[]" type="number" min="1" class="form-control form-control-sm" placeholder="10"></td><td><button type="button" class="icon-btn remove-row"><i class="bi bi-trash"></i></button></td></tr>`);
  });
  document.getElementById("addPaymentScheduleRow")?.addEventListener("click", () => {
    const tbody = document.querySelector("#paymentScheduleTable tbody");
    tbody?.insertAdjacentHTML("beforeend", `<tr><td><input name="stage[]" class="form-control form-control-sm" placeholder="Milestone"></td><td><input name="percentage[]" type="number" step="0.01" class="form-control form-control-sm" placeholder="0.00"></td><td><button type="button" class="icon-btn remove-row"><i class="bi bi-trash"></i></button></td></tr>`);
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest(".remove-row")) event.target.closest("tr")?.remove();
  });

  const search = document.getElementById("globalSearch");
  const results = document.getElementById("searchResults");
  let timer;
  search?.addEventListener("input", () => {
    clearTimeout(timer);
    const q = search.value.trim();
    if (q.length < 2) {
      results.style.display = "none";
      return;
    }
    timer = setTimeout(async () => {
      const response = await fetch(`/api/global-search?q=${encodeURIComponent(q)}`);
      const data = await response.json();
      results.innerHTML = data.map(item => `<a href="${item.url}"><span>${item.label}</span><small>${item.type}</small></a>`).join("") || `<a href="#"><span>No results</span><small></small></a>`;
      results.style.display = "block";
    }, 220);
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".global-search") && results) results.style.display = "none";
  });

  const receiptPaymentMode = document.getElementById("receiptPaymentMode");
  const refreshReceiptPaymentFields = () => {
    const mode = receiptPaymentMode?.value || "";
    receiptPaymentMode?.closest("form")?.querySelectorAll(".payment-fields").forEach((group) => {
      const modes = (group.dataset.paymentFields || "").split(",").map((item) => item.trim());
      const active = modes.includes(mode);
      group.hidden = !active;
      group.querySelectorAll("input, select, textarea").forEach((field) => {
        field.disabled = !active;
      });
    });
  };
  receiptPaymentMode?.addEventListener("change", refreshReceiptPaymentFields);
  refreshReceiptPaymentFields();

  const refreshModalPaymentFields = (modal) => {
    const mode = modal.querySelector(".receipt-modal-payment-mode")?.value || "";
    modal.querySelectorAll(".modal-payment-fields").forEach((group) => {
      const modes = (group.dataset.paymentFields || "").split(",").map((item) => item.trim());
      const active = modes.includes(mode);
      group.hidden = !active;
      group.querySelectorAll("input, select, textarea").forEach((field) => {
        field.disabled = !active;
      });
    });
  };

  document.querySelectorAll(".receipt-details-modal").forEach((modal) => {
    const setEditMode = (editing) => {
      modal.querySelectorAll(".receipt-view-mode").forEach((item) => item.classList.toggle("d-none", editing));
      modal.querySelector(".receipt-edit-mode")?.classList.toggle("d-none", !editing);
      if (editing) refreshModalPaymentFields(modal);
    };
    modal.querySelector(".receipt-edit-start")?.addEventListener("click", () => setEditMode(true));
    modal.querySelector(".receipt-edit-cancel")?.addEventListener("click", () => {
      modal.querySelector(".receipt-edit-mode")?.reset();
      setEditMode(false);
    });
    modal.querySelector(".receipt-modal-payment-mode")?.addEventListener("change", () => refreshModalPaymentFields(modal));
    modal.querySelector(".receipt-modal-print")?.addEventListener("click", () => {
      window.print();
    });
    modal.addEventListener("hidden.bs.modal", () => {
      modal.querySelector(".receipt-edit-mode")?.reset();
      setEditMode(false);
    });
    refreshModalPaymentFields(modal);
  });

  const flatSelect = document.getElementById("flatSelect");
  const projectSelect = document.getElementById("bookingProject");
  const costModeInputs = document.querySelectorAll("input[name='cost_mode']");
  const setCostField = (name, value) => {
    const input = document.querySelector(`[name="${name}"]`);
    if (input) input.value = Number(value || 0).toFixed(2);
  };
  const refreshCostPreview = async () => {
    const flatId = flatSelect?.value;
    if (!flatId) return;
    const option = flatSelect.selectedOptions[0];
    document.getElementById("flatSftDisplay")?.replaceChildren(document.createTextNode(option?.dataset.sft || "-"));
    if (document.querySelector("input[name='cost_mode']:checked")?.value !== "auto") return;
    const response = await fetch(`/api/flat/${flatId}/cost-preview`);
    const data = await response.json();
    ["rate_per_sft", "base_price", "floor_rise", "parking", "clubhouse", "facing_charges", "corpus_fund", "gst_percent", "gst", "gross_amount"].forEach((key) => setCostField(key, data[key]));
  };
  projectSelect?.addEventListener("change", () => {
    const projectId = projectSelect.value;
    flatSelect?.querySelectorAll("option[data-project]").forEach((option) => {
      option.hidden = Boolean(projectId) && option.dataset.project !== projectId;
    });
    if (flatSelect?.selectedOptions[0]?.hidden) flatSelect.value = "";
  });
  flatSelect?.addEventListener("change", refreshCostPreview);
  costModeInputs.forEach((input) => input.addEventListener("change", refreshCostPreview));
  refreshCostPreview();

  if (window.Chart && document.getElementById("inventoryChart")) {
    const inventory = window.erpDashboard || { available: 0, sold: 0, mortgage: 0 };
    Chart.defaults.font.family = "Inter, sans-serif";
    Chart.defaults.color = "#64748B";
    const chartGrid = "rgba(226,232,240,.72)";
    const collectionCanvas = document.getElementById("collectionChart");
    const collectionGradient = collectionCanvas.getContext("2d").createLinearGradient(0, 0, 0, 220);
    collectionGradient.addColorStop(0, "rgba(37,99,235,.24)");
    collectionGradient.addColorStop(1, "rgba(37,99,235,0)");
    new Chart(document.getElementById("inventoryChart"), {
      type: "doughnut",
      data: { labels: ["Available", "Sold", "Mortgage"], datasets: [{ data: [inventory.available, inventory.sold, inventory.mortgage], backgroundColor: ["#22C55E", "#2563EB", "#F59E0B"], borderWidth: 0, hoverOffset: 8 }] },
      options: { plugins: { legend: { position: "bottom", labels: { boxWidth: 10, usePointStyle: true, padding: 18 } } }, cutout: "70%" }
    });
    new Chart(document.getElementById("salesChart"), {
      type: "bar",
      data: { labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"], datasets: [{ label: "Sales", data: [4, 7, 5, 8, 10, 9], backgroundColor: "#2563EB", borderRadius: 12, maxBarThickness: 34 }] },
      options: { plugins: { legend: { display: false }, tooltip: { backgroundColor: "#0F172A", padding: 12, cornerRadius: 12 } }, scales: { y: { border: { display: false }, grid: { color: chartGrid } }, x: { border: { display: false }, grid: { display: false } } } }
    });
    new Chart(collectionCanvas, {
      type: "line",
      data: { labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"], datasets: [{ label: "Collections", data: [12, 18, 15, 24, 28, 31], borderColor: "#2563EB", backgroundColor: collectionGradient, pointBackgroundColor: "#FFFFFF", pointBorderColor: "#2563EB", pointBorderWidth: 3, pointRadius: 4, fill: true, tension: .42 }] },
      options: { plugins: { legend: { display: false }, tooltip: { backgroundColor: "#0F172A", padding: 12, cornerRadius: 12 } }, scales: { y: { border: { display: false }, grid: { color: chartGrid } }, x: { border: { display: false }, grid: { display: false } } } }
    });
  }

  if (window.Chart && window.erpCommandCenter) {
    Chart.defaults.font.family = "Inter, sans-serif";
    Chart.defaults.color = "#64748B";
    const data = window.erpCommandCenter;
    const grid = "rgba(226,232,240,.8)";
    const chart = (id, config) => {
      const canvas = document.getElementById(id);
      if (canvas) new Chart(canvas, config);
    };
    chart("salesTrendChart", {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [
          { label: "Sales", data: data.sales, borderColor: "#2563EB", backgroundColor: "rgba(37,99,235,.12)", fill: true, tension: .38 },
          { label: "Bookings", data: data.bookings, borderColor: "#0F766E", backgroundColor: "rgba(15,118,110,.08)", tension: .38 },
          { label: "Registrations", data: data.registrations, borderColor: "#7C3AED", backgroundColor: "rgba(124,58,237,.08)", tension: .38 }
        ]
      },
      options: { responsive: true, plugins: { tooltip: { backgroundColor: "#0F172A", padding: 12 }, legend: { position: "bottom" } }, scales: { y: { grid: { color: grid } }, x: { grid: { display: false } } } }
    });
    chart("collectionTrendChart", {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          { label: "Collections", data: data.collections, backgroundColor: "#2563EB", borderRadius: 8 },
          { label: "Due Collections", data: data.dues, backgroundColor: "#F59E0B", borderRadius: 8 },
          { label: "Outstanding", data: data.outstanding, backgroundColor: "#CBD5E1", borderRadius: 8 }
        ]
      },
      options: { responsive: true, plugins: { tooltip: { backgroundColor: "#0F172A", padding: 12 }, legend: { position: "bottom" } }, scales: { y: { grid: { color: grid } }, x: { grid: { display: false } } } }
    });
    chart("commandInventoryChart", {
      type: "doughnut",
      data: { labels: ["Available", "Booked", "Sold", "Registered"], datasets: [{ data: data.inventory, backgroundColor: ["#2563EB", "#F59E0B", "#22C55E", "#7C3AED"], borderWidth: 0, hoverOffset: 8 }] },
      options: { cutout: "68%", plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 9 } } } }
    });
    chart("healthGaugeChart", {
      type: "doughnut",
      data: { labels: ["Score", "Gap"], datasets: [{ data: [data.health, Math.max(100 - data.health, 0)], backgroundColor: ["#2563EB", "#E2E8F0"], borderWidth: 0 }] },
      options: { circumference: 180, rotation: 270, cutout: "72%", plugins: { legend: { display: false }, tooltip: { enabled: false } } }
    });
    chart("cashflowChart", {
      type: "line",
      data: { labels: ["7 Days", "15 Days", "30 Days"], datasets: [{ label: "Expected Collection", data: data.cashflow, borderColor: "#0F766E", backgroundColor: "rgba(15,118,110,.12)", fill: true, tension: .35 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: grid } }, x: { grid: { display: false } } } }
    });
    chart("customerGrowthChart", {
      type: "bar",
      data: { labels: data.labels, datasets: [{ label: "Customer Growth", data: data.customer_growth, backgroundColor: "#2563EB", borderRadius: 8 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: grid } }, x: { grid: { display: false } } } }
    });
  }

  if (window.Chart && window.erpCompactDashboard) {
    Chart.defaults.font.family = "Inter, sans-serif";
    Chart.defaults.color = "#64748B";
    const canvas = document.getElementById("compactInventoryChart");
    if (canvas) {
      new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: ["Available", "Booked", "Sold", "Registered"],
          datasets: [{
            data: window.erpCompactDashboard.inventory,
            backgroundColor: ["#2563EB", "#F59E0B", "#22C55E", "#7C3AED"],
            borderWidth: 0,
            hoverOffset: 5
          }]
        },
        options: {
          cutout: "70%",
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { backgroundColor: "#0F172A", padding: 10 }
          }
        }
      });
    }
  }
})();
