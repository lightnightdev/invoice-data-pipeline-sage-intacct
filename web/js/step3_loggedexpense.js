function clean_step2_ui() {
  const sageid_direct = document.getElementById("sageid-direct");
  sageid_direct?.remove();

  const year_month_el = document.getElementById("input-yearmonth");
  year_month_el.disabled = true;

  const btnWrapper = document.getElementById("button-wrapper");
  if (btnWrapper) {
    btnWrapper.replaceChildren();
    btnWrapper.style.display = "flex";
    btnWrapper.style.justifyContent = "space-between";
  }
}

function setup_loggedexpense_ui(loggedexpense_options, loggedexpense_sage_options) {
  clean_step2_ui()
  const main_header = document.getElementById("main-header");
  main_header.innerText = "Select Logged Expenses to Include";

  const btnWrapper = document.getElementById("button-wrapper");
  if (btnWrapper) {
    btnWrapper.replaceChildren();
    btnWrapper.style.display = "flex";
    btnWrapper.style.justifyContent = "space-between";
    btnWrapper.append(createBackButton(), createContinueButton());
  }

  const teamsTable = document.getElementById("teams-table");
  teamsTable?.replaceChildren();

  const loggedexpenseTable = setupTabulator(loggedexpense_options, loggedexpense_sage_options);
  window.wizard.setActiveTable(loggedexpenseTable);
}

function createContinueButton() {
  const btn = document.createElement("button");
  btn.id = "continue-loggedexpense-btn";
  btn.textContent = "▶️ Continue";
  btn.className = "btn btn-primary";
  btn.onclick = () => {
    continueloggedexpense();
  };
  return btn;
}

function continueloggedexpense() {
  const loggedexpenseTable = window.wizard.getActiveTable("loggedexpense-table");
  if (!loggedexpenseTable) return;

  const selectedRows = loggedexpenseTable.getSelectedData();
  // Validate that every selected row has a valid ItemId
  const invalidRows = selectedRows.filter(
    (row) => !row.ItemId || String(row.ItemId).trim() === "",
  );

  if (invalidRows.length > 0) {
    const invalidNames = invalidRows.map(
      (row) => row.LoggedExpenseName || "Unknown Expense",
    );
    alert(
      `Please select a valid Sage Item ID for the following item(s) before continuing:\n\n - ${invalidNames.join("\n - ")}`,
    );
    return;
  }

  const allRows = loggedexpenseTable.getData();

  const selloggedexpense = selectedRows.map((x) => x.LoggedExpenseName);
  const allloggedexpense = allRows.map((x) => x.LoggedExpenseName);
  const unselectedloggedexpense = allloggedexpense.filter((loggedexpense) => !selloggedexpense.includes(loggedexpense));
  console.log("sel, all", selloggedexpense, allloggedexpense);
  console.log("selectedRows, unselectedloggedexpense", selectedRows, unselectedloggedexpense);

  window.AppState.setloggedexpenseSelections(selectedRows);
  window.AppState.setloggedexpenseUnselected(unselectedloggedexpense);

  window.wizard.next();
}

function setupTabulator(loggedexpense_options, loggedexpense_sage_options) {
  const getUniqueKeys = (arr, key) => [
    ...new Set(arr.map((item) => item[key]).filter((val) => val != null)),
  ];

  const itemIds = getUniqueKeys(loggedexpense_sage_options, "ItemId");
  const memos = getUniqueKeys(loggedexpense_sage_options, "Memo");
  const soDocumentEntryClassIds = getUniqueKeys(
    loggedexpense_sage_options,
    "SoDocumentEntryClassId",
  );
  const locations = getUniqueKeys(loggedexpense_sage_options, "Location");

  const loggedexpenseTable = new Tabulator("#loggedexpense-table", {
    data: loggedexpense_options,
    layout: "fitDataFill",
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
      { title: "Expense Name", field: "LoggedExpenseName" },
      { title: "Count", field: "TotalCount", hozAlign: "right" },
      {
        title: "Total Amount",
        field: "TotalAmt",
        hozAlign: "right",
        formatter: "money",
        formatterParams: { symbol: "$" },
      },
      { title: "SampleTeams", field: "SampleTeamNames", width: 150 },
      {
        title: "SageItemId",
        field: "ItemId",
        editor: "list",
        editorParams: { freetext: true, autocomplete: true, values: itemIds },
      },
      {
        title: "SageMemo",
        field: "Memo",
        editor: "list",
        editorParams: { freetext: true, autocomplete: true, values: memos },
      },
      {
        title: "SageSODECId",
        field: "SoDocumentEntryClassId",
        editor: "list",
        editorParams: {
          freetext: true,
          autocomplete: true,
          values: soDocumentEntryClassIds,
        },
      },
      {
        title: "SageLocation",
        field: "Location",
        editor: "list",
        editorParams: { freetext: true, autocomplete: true, values: locations },
      },
    ],
  });

  // Automatically select rows where SageItemId is populated
  loggedexpenseTable.on("tableBuilt", function () {
    loggedexpenseTable.getRows().forEach((row) => {
      if (row.getData().ItemId) {
        row.select();
      }
    });
  });

  return loggedexpenseTable;
}
