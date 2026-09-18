// --- Component Builders ---

function createRefreshButton(sheetName) {
  const btn = document.createElement("button");
  btn.textContent = "🔄 Refresh From GSheet";
  btn.className = "btn btn-secondary";
  btn.onclick = () => {
    if (sheetName) load_chosen_sheet(sheetName, false);
  };
  return btn;
}

function createSelectMultipleDates() {
  //   <details class="dropdown">
  //   <summary class="btn">Actions ▾</summary>
  //   <div class="menu">
  //     <button onclick="console.log('Edit')">Edit Item</button>
  //     <button onclick="console.log('Duplicate')">Duplicate</button>
  //     <button onclick="console.log('Delete')">Delete</button>
  //   </div>
  // </details>
}

function createDateNeededSelect(parsedData) {
  const select = document.createElement("select");
  select.id = "date-needed-select";
  select.className = "form-select";

  const rawDates = parsedData?.columns?.dateneeded || [];
  const uniqueDates = [...new Set(rawDates)].filter(Boolean).sort();

  select.add(new Option("-- Select Date Needed --", ""));
  uniqueDates.forEach((dateStr) => select.add(new Option(dateStr, dateStr)));

  return select;
}

function createDateSelectButton(getSelectedDate) {
  const btn = document.createElement("button");
  btn.textContent = "Select by Date";
  btn.className = "btn btn-outline-primary";
  btn.onclick = () => handleDateToggle(getSelectedDate());
  return btn;
}

function createGenerateInvoicesButton() {
  const btn = document.createElement("button");
  btn.id = "btn-generate-selected";
  btn.textContent = "🚀 Generate Import File";
  btn.className = "btn btn-success";
  btn.onclick = () => handleGenerateInvoices(btn);
  return btn;
}

function handleDateToggle(selectedDate) {
  const customerTable = window.wizard.getActiveTable("teams-table");
  if (!selectedDate || !customerTable) return;

  const matchingRows = customerTable
    .getRows()
    .filter((row) => row.getData().dateneeded === selectedDate);

  if (matchingRows.length === 0) return;

  const allMatchingAreSelected = matchingRows.every((row) => row.isSelected());
  matchingRows.forEach((row) =>
    allMatchingAreSelected ? row.deselect() : row.select(),
  );

  const firstMatch = matchingRows[0];
  const rowIndex = customerTable.getRows("active").indexOf(firstMatch);

  if (rowIndex !== -1) {
    const pageSize = customerTable.getPageSize();
    customerTable.setPage(Math.floor(rowIndex / pageSize) + 1);
  }
}

async function handleGenerateInvoices(btn) {
  const customerTable = window.wizard.getActiveTable("teams-table");
  if (!customerTable) return;

  const selectedRows = customerTable.getSelectedData();
  const selectedRowDetails = selectedRows
    .map((row) => ({ name: row.customer, sageid: row.sageid, type: row.type }))
    .filter((item) => item.sageid);

  if (selectedRowDetails.length === 0) {
    alert("Please select at least one customer row with a valid Sage ID.");
    return;
  }

  setupInvoiceGenUI();
  window.AppState.setSelectedTeams(selectedRowDetails);

  try {
    const success = await processSelectedTeams();
    if (!success) {
      btn.disabled = false;
      btn.textContent = "🚀 Generate Import File";
    }
  } catch (err) {
    console.error("Error processing selected teams:", err);
    btn.disabled = false;
    btn.textContent = "🚀 Generate Import File";
  }
}

// Majo

function validate_customerdata(raw_data) {
  try {
    const data = typeof raw_data === "string" ? JSON.parse(raw_data) : raw_data;

    if (!data || typeof data !== "object" || !data.columns) {
      console.error("Invalid data format.");
      return null;
    }

    const { customers, sageid, dateneeded, lockedshared, invoicesent } =
      data.columns;

    if (
      !Array.isArray(customers) ||
      !Array.isArray(sageid) ||
      !Array.isArray(dateneeded) ||
      !Array.isArray(lockedshared) ||
      !Array.isArray(invoicesent)
    ) {
      console.error("Expected customer data arrays to be present.");
      return null;
    }

    return data;
  } catch (err) {
    console.error("JSON parsing error in validate_customerdata:", err);
    return null;
  }
}

async function processSelectedTeams() {
  const namesSageIdsTypes = window.AppState.selected_teams;
  if (!namesSageIdsTypes || namesSageIdsTypes.length === 0) {
    alert("No teams selected.");
    return false;
  }

  const sageids = namesSageIdsTypes.map((row) => row.sageid);
  window.AppState.setSageIds(sageids);

  // 1. Validate Sage IDs
  const validateSageResp =
    await window.pywebview.api.validate_sageids(namesSageIdsTypes);
  if (validateSageResp.summary !== "ok" || !validateSageResp.sageids_teamids) {
    alert("Failure to run validate_sageids. Check logs.");
    return false;
  }

  const sageids_teamids = validateSageResp.sageids_teamids;
  const teamids_teamtypes = validateSageResp.teamids_teamtypes;

  // 2. Validate Team Names
  const validateNamesResp = await window.pywebview.api.validate_teamnames(
    namesSageIdsTypes,
    sageids_teamids,
  );

  window.AppState.setTeamIds(sageids_teamids);
  window.AppState.setTeamNames(validateNamesResp.teamids_teamnames);
  window.AppState.setTeamTypes(teamids_teamtypes);

  // 3. Extract Period & Fetch Logged Expenses
  const teamIds = Object.values(sageids_teamids);
  const [year, month] = getSelectedDate(); // AppState is already updated inside

  const loggedexpenseOutput = await window.pywebview.api.get_loggedexpense_to_select(
    teamIds,
    year,
    month,
  );

  if (loggedexpenseOutput.summary !== "ok") {
    console.error("Error in get_loggedexpense_to_select output:", loggedexpenseOutput);
    return false;
  }

  // 4. Branch Step Routing
  if (!loggedexpenseOutput.loggedexpense_options || loggedexpenseOutput.loggedexpense_options.length < 1) {
    window.AppState.loggedexpense_names = [];
    window.wizard.goToStep(3); // Jump to Step 4 (Custom Rows)
  } else {
    window.AppState.loggedexpense_options = loggedexpenseOutput.loggedexpense_options;
    window.AppState.all_options = loggedexpenseOutput.all_options || [];
    window.wizard.goToStep(2); // Advance to Step 3 (loggedexpense)
  }

  return true;
}

//

async function setupInvoiceGenUI() {
  const generateSelectedInvoicesBtn = document.getElementById(
    "btn-generate-selected",
  );

  const generateDirectInvoicesBtn =
    document.getElementById("sageid-direct-btn");

  if (generateSelectedInvoicesBtn) {
    generateSelectedInvoicesBtn.disabled = true;
    generateSelectedInvoicesBtn.textContent = "Generating...";
  }

  if (generateDirectInvoicesBtn) {
    generateDirectInvoicesBtn.disabled = true;
    generateDirectInvoicesBtn.textContent = "Generating...";
  }

  const btnWrapper = document.getElementById("button-wrapper");
  const btnChildren = btnWrapper.querySelectorAll("*");
  btnChildren.forEach((element) => {
    element.disabled = true;
  });

  const year_month_el = document.getElementById("input-yearmonth");
  year_month_el.disabled = true;
}

function formatToYearMonth(sheetName) {
  const parts = sheetName.trim().split(/[- ]+/);
  if (parts.length !== 2) return "";

  const months = [
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
  ];
  const isYear = (s) => /^\d{4}$/.test(s);

  let year = "";
  let month = "";

  parts.forEach((p) => {
    if (isYear(p)) {
      year = p;
    } else {
      // Check for month name (e.g., "Jan")
      const monthIdx = months.indexOf(p.toLowerCase().slice(0, 3));
      if (monthIdx !== -1) {
        month = String(monthIdx + 1).padStart(2, "0");
      } else if (/^\d{1,2}$/.test(p)) {
        // Handle numeric months (e.g., "3" or "03")
        month = String(parseInt(p, 10)).padStart(2, "0");
      }
    }
  });

  return year && month ? `${year}-${month}` : "";
}

function getSelectedDate() {
  const dateVal = document.getElementById("input-yearmonth")?.value;
  let year, month;

  if (dateVal && /^\d{4}-\d{2}$/.test(dateVal)) {
    [year, month] = dateVal.split("-").map(Number);
  } else {
    let dateObj = new Date(dateVal);
    if (isNaN(dateObj.getTime())) {
      dateObj = new Date();
    }
    year = dateObj.getUTCFullYear();
    month = dateObj.getUTCMonth() + 1;
  }

  window.AppState.setPeriod(year, month);

  return [year, month];
}

function newCreateDateNeededSelect(parsedData) {
  const details = document.createElement("details");
  details.id = "date-needed-select";
  details.className = "dropdown";

  const summary = document.createElement("summary");
  summary.className = "btn";
  summary.textContent = "Select Date Needed ▾";
  details.appendChild(summary);

  const menu = document.createElement("div");
  menu.className = "menu";

  const rawDates = parsedData?.columns?.dateneeded || [];
  const uniqueDates = [...new Set(rawDates)].filter(Boolean).sort();

  uniqueDates.forEach((dateStr) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = dateStr;
    btn.dataset.date = dateStr;

    btn.addEventListener("click", () => {
      handleDateToggle(dateStr);
      updateDateButtonStyles(menu);
    });

    menu.appendChild(btn);
  });

  details.appendChild(menu);

  // close menu when clicking away from it
  document.addEventListener("click", (e) => {
    if (details.open && !details.contains(e.target)) {
      details.open = false;
    }
  });

  // Recalculate colors whenever the dropdown menu opens
  details.addEventListener("toggle", () => {
    if (details.open) {
      updateDateButtonStyles(menu);
    }
  });

  return details;
}

function updateDateButtonStyles(menuElement) {
  const customerTable = window.wizard?.getActiveTable("teams-table");
  if (!customerTable) return;

  const allRows = customerTable.getRows();
  const buttons = menuElement.querySelectorAll("button[data-date]");

  buttons.forEach((btn) => {
    const dateStr = btn.dataset.date;
    const matchingRows = allRows.filter(
      (row) => row.getData().dateneeded === dateStr,
    );

    if (matchingRows.length === 0) {
      btn.style.backgroundColor = "white";
      btn.style.color = "black";
      return;
    }

    const selectedCount = matchingRows.filter((row) => row.isSelected()).length;

    if (selectedCount === 0) {
      // No matching rows selected
      btn.style.backgroundColor = "white";
      btn.style.color = "black";
    } else if (selectedCount === matchingRows.length) {
      // All matching rows selected
      btn.style.backgroundColor = "#28a745"; // Green
      btn.style.color = "white";
    } else {
      // Some matching rows selected
      btn.style.backgroundColor = "#ffc107"; // Yellow
      btn.style.color = "black";
    }
  });
}
