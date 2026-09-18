let customRowsTable = null;

async function setup_custom_rows() {
  const sage_ids = window.AppState.all_sageid;
  const custom_rows =
    await window.pywebview.api.custom_rows_from_sageids(sage_ids);

  window.AppState.setCustomRows(custom_rows);

  if (custom_rows && custom_rows.length > 0) {
    setup_custom_rows_ui(custom_rows);
  } else {
    window.wizard.next();
  }
}

async function setup_custom_rows_ui(customRows) {
  // clear previous UI
  clean_step2_ui()
  const main_header = document.getElementById("main-header");
  main_header.innerText = "Custom Rows";

  const btnWrapper = document.getElementById("button-wrapper");
  if (btnWrapper) {
    btnWrapper.append(
      createBackButton(),
      createSelectCustomRowsButton());
  }
  // Instantiate Tabulator Table
  const customRowsTable = new Tabulator("#custom-rows-table", {
    data: customRows,
    layout: "fitDataFill",
    pagination: true,
    paginationSize: 15,
    paginationButtonCount: 10, // Displays up to 20 page numbers at once
    paginationCounter: "pages",
    columns: [
      {
        formatter: "rowSelection",
        titleFormatter: "rowSelection",
        hozAlign: "center",
        headerSort: false,
      },
      { title: "User Note", field: "UserNote" },
      { title: "Sage ID", field: "SageId" },
      { title: "Amount", field: "Amount", editor: "number" },
      { title: "Item ID", field: "ItemId" },
      { title: "Memo", field: "Memo", editor: "input" },
      {
        title: "SoDocumentEntryClassId",
        field: "SoDocumentEntryClassId",
        editor: "number",
      },
      { title: "Location", field: "Location", editor: "number" },
      { title: "Repeating", field: "Repeating", editor: "tickCross" },
    ],
  });
  window.wizard.setActiveTable(customRowsTable);
  customRowsTable.on("tableBuilt", () => {
    customRowsTable.getRows().forEach((row) => {
      if (row.getData().selected) {
        row.select();
      }
    });
  });
}

function createSelectCustomRowsButton() {
  // Check if button exists; create a new one if it doesn't
  const btn =
    document.getElementById("continue-btn") || document.createElement("button");

  btn.id = "continue-btn";
  btn.textContent = "> Continue";
  btn.className = "btn btn-primary";
  btn.onclick = () => {
    select_custom_rows();
  };

  return btn;
}

async function select_custom_rows() {
  const customRowsTable = window.wizard.activeTable;
  if (customRowsTable) {
    const selectedRows = customRowsTable.getSelectedData();
    const allRows = customRowsTable.getData();

    const selloggedexpense = selectedRows.map((x) => x["CustomRowId"]);
    const allloggedexpense = allRows.map((x) => x["CustomRowId"]);
    const unselectedCustomRows = allloggedexpense.filter((loggedexpense) => !selloggedexpense.includes(loggedexpense));

    window.AppState.setCustomRowsUnselected(unselectedCustomRows);
    window.AppState.setCustomRows(selectedRows);
    window.wizard.next(); // Advances safely to Step 5
  } else {
    console.error("No custom rows table");
  }
}
