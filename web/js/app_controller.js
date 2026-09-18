class AppController {
  constructor() {
    this.currentStepIndex = 0;
    this.activeTable = null; // Encapsulates customerTable, loggedexpenseTable, customRowsTable
    this.selectedSheet = null;

    this.steps = [
      { id: "sheets", render: () => load_cached_sheet_table() },
      { id: "teams", render: () => load_chosen_sheet(this.selectedSheet) },
      {
        id: "loggedexpense",
        render: () =>
          setup_loggedexpense_ui(
            window.AppState.loggedexpense_options,
            window.AppState.all_options,
          ),
      },
      { id: "customRows", render: () => setup_custom_rows() },
      { id: "preview", render: () => setup_invoice_preview() },
    ];
  }

  // App startup entry point
  init() {
    this.setupDateInput();
    this.bindEvents();

    // Defer initial render until PyWebview's JS bridge is ready
    if (window.pywebview) {
      this.goToStep(0);
    } else {
      window.addEventListener("pywebviewready", () => this.goToStep(0));
    }
  }

  setupDateInput() {
    const dateInput = document.getElementById("input-yearmonth");
    if (dateInput) {
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, "0");
      dateInput.value = `${year}-${month}`;
    }
  }

  bindEvents() {
    document
      .getElementById("load-sheets-btn")
      ?.addEventListener("click", () => {
        load_sheet_table();
      });

    document
      .getElementById("sageid-direct-btn")
      ?.addEventListener("click", () => {
        if (typeof checkDirectSage === "function") checkDirectSage();
      });

    document
      .getElementById("clear-cache-btn")
      ?.addEventListener("click", () => {
        this.clearCache();
      });
  }

  async clearCache() {
    const userApproved = window.confirm(
      "Clear local cache to get fresh data from Google Sheets and DB-C DB",
    );
    if (userApproved) {
      await window.pywebview.api.clear_cache();
      alert("Cache cleared");
      window.location.reload();
    }
  }

  parseUserSageIdInput(inputStr) {
    if (!inputStr) return [];
    return inputStr
      .replace(/(?<!\s)C-/g, " C-")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  selectSheet(sheetName) {
    this.selectedSheet = sheetName;
    this.next(); // Advances to Step 2 (Teams)
  }

  goToStep(index) {
    if (index >= 0 && index < this.steps.length) {
      this.destroyActiveTable();
      this.currentStepIndex = index;
      this.steps[this.currentStepIndex].render();
    }
  }

  next() {
    this.goToStep(this.currentStepIndex + 1);
  }

  back() {
    this.goToStep(this.currentStepIndex - 1);
  }

  // Encapsulated Tabulator management
  getActiveTable(expectedElementId) {
    if (!this.activeTable) return null;

    // Tabulator exposes its root element via table.element
    if (
      expectedElementId &&
      this.activeTable.element?.id !== expectedElementId
    ) {
      console.warn(
        `Table mismatch: expected #${expectedElementId}, but found #${this.activeTable.element?.id}`,
      );
      return null;
    }

    return this.activeTable;
  }

  setActiveTable(tableInstance) {
    this.destroyActiveTable();
    this.activeTable = tableInstance;
  }

  destroyActiveTable() {
    if (this.activeTable) {
      if (typeof this.activeTable.destroy === "function") {
        this.activeTable.destroy();
      }
      this.activeTable = null;
    }
  }
}

// Instantiate globally on load
window.wizard = new AppController();

document.addEventListener("DOMContentLoaded", () => {
  window.wizard.init();
});
