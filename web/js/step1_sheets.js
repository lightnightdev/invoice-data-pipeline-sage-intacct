async function load_cached_sheet_table() {
  try {
    reset_sheet_table("Checking for cached sheets...");

    console.log('Getting response (get_cached_sheets)...');
    const response = await window.pywebview.api.get_cached_sheets();

    if (!response || !response.success) {
      const errorMsg = response?.error || "No cached sheets found.";
      console.error("Failed to load cached sheets:", errorMsg);
      reset_sheet_table(`Unable to load cached sheets: ${errorMsg}`);
      return;
    }

    // Success path: pass the inner sheets array to render
    render_sheet_table(response.sheets);
  } catch (err) {
    console.error("Error loading cached sheets:", err);
    reset_sheet_table("An unexpected error occurred while checking cache.");
  }
}

// Shared UI rendering logic for sheet names
function render_sheet_table(sheetNames) {

  const validSheetNames = validateSheetNames(sheetNames)

  const txtEl = document.getElementById("sheet-table");
  const tblEl = makeChoiceTable(txtEl, (sheetName) => {
    window.wizard.selectSheet(sheetName);
  });
  for (const sheetName of validSheetNames) {
    addChoiceTableRow(tblEl, sheetName, sheetName);
  }
}

function validateSheetNames(sheetNames) {
  const isYear = (s) => /^\d{4}$/.test(s);
  const isMonth = (s) => {
    const m = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
    return m.includes(s.toLowerCase().slice(0, 3)) || (/^\d{1,2}$/.test(s) && s >= 1 && s <= 12);
  };

  const isValid = (str) => {
    const p = str.trim().split(/[- ]+/);
    return p.length === 2 && ((isYear(p[0]) && isMonth(p[1])) || (isMonth(p[0]) && isYear(p[1])));
  };

  return (Array.isArray(sheetNames) ? sheetNames : [sheetNames])
    .filter((name) => typeof name === "string" && isValid(name))
    .map((name) => name.trim());
}

// Loads the sheet/tabs directly from the Google Sheet with invoices Google Sheet
async function load_sheet_table() {
  const btn = document.getElementById("load-sheets-btn");

  try {
    if (btn) btn.hidden = true;
    reset_sheet_table("Loading sheets from Google Sheet with invoices...");

    const response = await window.pywebview.api.load_sheets();

    if (!response || !response.success) {
      const errorMsg = response?.error || "Unknown error occurred loading sheets.";
      console.error("Failed to load sheets:", errorMsg);
      
      reset_sheet_table(`Failed to load sheets: ${errorMsg}`);
      if (btn) btn.hidden = false;
      return;
    }

    // Success path: pass the sheet array to your rendering function
    render_sheet_table(response.sheets);

  } catch (err) {
    console.error("Error Loading Sheets from GSheet:", err);
    reset_sheet_table("An unexpected error occurred. Check console for details.");
    if (btn) btn.hidden = false;
  }
}
