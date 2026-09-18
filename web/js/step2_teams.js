// --- Main Orchestrator ---

function enableTeamButtons(parsedData, sheetName) {
  const btnWrapper = document.getElementById("button-wrapper");
  if (!btnWrapper) return;

  btnWrapper.replaceChildren();

  // const dateNeededSelect = createDateNeededSelect(parsedData);

  btnWrapper.append(
    createBackButton(),
    createRefreshButton(sheetName),
    newCreateDateNeededSelect(parsedData),
    // dateNeededSelect,
    // createDateSelectButton(() => dateNeededSelect.value),
    // createDebugButton(),
    createGenerateInvoicesButton(),
  );
}



function createBackButton() {
  const btn = document.createElement("button");
  btn.id = "back-btn";
  btn.textContent = "↩ Back";
  btn.className = "btn btn-secondary";
  btn.onclick = () => window.wizard.back();
  return btn;
}
// Loads the data from the chosen YearMonth of the Google Sheet
async function load_chosen_sheet(sheetName, cache_check = true) {
  console.log("Load Chosen Sheet ran", sheetName);

  const dateInput = document.getElementById("input-yearmonth");
  if (dateInput) {
    // Standardizes formats like "Jan 2026" or "2026-3" to "2026-01" / "2026-03"
    dateInput.value = formatToYearMonth(sheetName);
  }

  const mainHeader = document.getElementById("main-header");
  if (mainHeader) {
    mainHeader.textContent = `Sheet: ${sheetName}`;
  }

  reset_sheet_table(`Loading Sheet ${sheetName}...`);

  let parsedData = null;

  // 1. Attempt to load cached sheet data first
  if (cache_check) {
    console.log("[DEBUG] Checking cache called inside load_chosen_sheet");
    try {
      const cachedData =
        await window.pywebview.api.get_cached_customer_data(sheetName);
      if (cachedData) {
        console.log(`Loaded ${sheetName} from local cache.`);
        parsedData = validate_customerdata(cachedData);
      }
    } catch (err) {
      console.warn(
        "Cache fetch failed or missing, falling back to network load:",
        err,
      );
    }
  }

  // 2. Fetch fresh data if cache missed or was invalid
  if (!parsedData) {
    console.log(`Fetching fresh data for ${sheetName}...`);
    const raw_data = await window.pywebview.api.load_customer_data(sheetName);
    parsedData = validate_customerdata(raw_data);
  }

  // 3. Render table if valid
  if (parsedData) {
    console.log("sheet data validation success");
    setup_customer_data_table(parsedData);

    // Safely update instructions text element
    const infoEl = document.getElementById("info-message");
    if (infoEl) {
      infoEl.textContent = "Hold shift to select multiple teams. Click headers";
    }

    if (typeof enableTeamButtons === "function") {
      enableTeamButtons(parsedData, sheetName);
    }

    const msgEl = document.getElementById("main-message");
    msgEl.innerHTML = "Shift+click+drag to select multiple rows at once.";
  } else {
    reset_sheet_table("Failed to load valid customer data.");
  }
}

function setup_customer_data_table(customer_data) {
  // Transform dict-of-arrays into array-of-objects
  const customers = customer_data.columns.customers || [];
  const sageids = customer_data.columns.sageid || [];
  const type = customer_data.columns.type || [];
  const dateneeded = customer_data.columns.dateneeded || [];
  const lockedshared = customer_data.columns.lockedshared || [];
  const invoicesent = customer_data.columns.invoicesent || [];

  console.log("Array Lengths:", {
    customers: customers.length,
    sageids: sageids.length,
    type: type.length,
    dateneeded: dateneeded.length,
    lockedshared: lockedshared.length,
    invoicesent: invoicesent.length,
  });

  console.log("First 5 values:", {
    customers: customers.slice(0, 5),
    sageids: sageids.slice(0, 5),
    type: type.slice(0, 5),
    dateneeded: dateneeded.slice(0, 5),
    lockedshared: lockedshared.slice(0, 5),
    invoicesent: invoicesent.slice(0, 5),
  });

  const tableData = customers.map((cust, i) => {
    const rawLocked = lockedshared[i];
    const rawInvoice = invoicesent[i];
    const toBool = (val) =>
      typeof val === "boolean"
        ? val
        : String(val).trim().toLowerCase() === "true";

    return {
      customer: cust,
      sageid: sageids[i] || "",
      type: type[i] || "",
      dateneeded: dateneeded[i] || "",
      lockedsharedstatus: toBool(lockedshared[i]),
      invoicesentstatus: toBool(invoicesent[i]),
    };
  });

  // Modern initialization
  const instance = new Tabulator("#teams-table", {
    data: tableData,
    layout: "fitDataFill",
    initialSort: [{ column: "dateneeded", dir: "asc" }],
    pagination: true,
    paginationSize: 15,
    paginationButtonCount: 10, // Displays up to 20 page numbers at once
    paginationCounter: "pages",
    selectableRows: true,
    columns: [
      {
        formatter: "rowSelection",
        titleFormatter: "rowSelection",
        hozAlign: "center",
        headerSort: false,
        width: 40,
      },
      {
        title: "Customer Name",
        field: "customer",
        headerFilter: "input",
        sorter: "string",
      },
      {
        title: "Sage ID",
        field: "sageid",
        headerFilter: "input",
        sorter: "number",
      },
      {
        title: "Type",
        field: "type",
        headerFilter: "input",
        sorter: "string",
      },
      {
        title: "Date Needed",
        field: "dateneeded",
        headerFilter: "input",
        sorter: "string",
      },
      {
        title: "Locked/Shared",
        field: "lockedsharedstatus",
        hozAlign: "center",
        formatter: (cell) => (cell.getValue() ? "\u2705" : ""),
        headerFilter: "tickCross",
        headerFilterParams: { tristate: true },
        sorter: "boolean",
      },
      {
        title: "Invoice Sent",
        field: "invoicesentstatus",
        hozAlign: "center",
        formatter: (cell) => (cell.getValue() ? "\u2705" : ""),
        headerFilter: "tickCross",
        headerFilterParams: { tristate: true },
        sorter: "boolean",
      },
    ],
  });

  window.wizard.setActiveTable(instance);

  // Handle post-build actions via lifecycle callback
  instance.on("tableBuilt", function () {
    if (!instance) return;

    // Perform initial row selection cleanly after table is built
    instance.getRows().forEach((row) => {
      if (!row.getData().invoicesentstatus) {
        row.select();
      }
    });
  });
}

function reset_sheet_table(message) {
  window.wizard.destroyActiveTable();

  const txtEl = document.getElementById("main-message");
  if (txtEl) txtEl.innerHTML = message;

  const sheetEl = document.getElementById("sheet-table");
  if (sheetEl) sheetEl.innerHTML = "";

  const dateContainer = document.getElementById("date-controls-container");
  if (dateContainer) dateContainer.innerHTML = "";
}