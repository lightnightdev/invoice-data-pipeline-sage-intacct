async function setup_invoice_preview() {
  try {
    setupInvoicePreviewUI();
    console.log(window.AppState);

    const invoiceData = await window.pywebview.api.generate_invoices_to_preview(
      window.AppState.sageid_teamid,
      window.AppState.teamid_teamtype,
      window.AppState.teamid_teamname,
      window.AppState.loggedexpense_names,
      window.AppState.year,
      window.AppState.month,
      window.AppState.loggedexpense_options, // loggedexpense_keys
      window.AppState.loggedexpense_unselected,
      window.AppState.custom_rows,
      window.AppState.custom_rows_unselected,
      true
    );

    console.log(invoiceData);

    const sageTable = renderSageTable(invoiceData);
    window.wizard.setActiveTable(sageTable); // Encapsulate

    const btnWrapper = document.getElementById("button-wrapper");
    if (!btnWrapper) return;

    btnWrapper.replaceChildren();
    btnWrapper.append(
      createDownloadCsvButton(
        sageTable,
        window.AppState.year,
        window.AppState.month,
      ),
    );
  } catch (error) {
    console.error("Failed to generate invoice preview:", error);
  }
}

function renderSageTable(data) {
  const sageTable = new Tabulator("#invoice-table", {
    data: data,
    headerSort: false,
    layout: "fitDataFill",
    pagination: true,
    paginationSize: 15,
    paginationSizeSelector: true,
    paginationSizeSelector: [10, 50, 500, true],
    columns: [
      {
        title: "TRANSACTIONTYPE",
        field: "TRANSACTIONTYPE",
        editor: "textarea",
      },
      { title: "DATE", field: "DATE", editor: "textarea" },
      { title: "GLPOSTINGDATE", field: "GLPOSTINGDATE", editor: "textarea" },
      { title: "CUSTOMER_ID", field: "CUSTOMER_ID", editor: "textarea" },
      { title: "TERM_NAME", field: "TERM_NAME", editor: "textarea" },
      { title: "DATEDUE", field: "DATEDUE", editor: "textarea" },
      { title: "STATE", field: "STATE", editor: "textarea" },
      { title: "LINE", field: "LINE", editor: "number" },
      { title: "ITEMID", field: "ITEMID", editor: "textarea" },
      {
        title: "QUANTITY",
        field: "QUANTITY",
        sorter: "number",
        editor: "number",
        editorParams: {
          verticalNavigation: "table",
        },
      },
      { title: "UNIT", field: "UNIT", editor: "textarea" },
      {
        title: "PRICE",
        field: "PRICE",
        formatter: "money",
        editor: "number",
        editorParams: {
          min: 0,
          step: 0.01,
          verticalNavigation: "table",
        },
      },
      {
        title: "LOCATIONID ID",
        field: "LOCATIONID",
        editor: "number",
        editorParams: {
          min: 0,
          step: 0.01,
          verticalNavigation: "table",
        },
      },
      {
        title: "SODOCUMENTENTRY_CLASSID",
        field: "SODOCUMENTENTRY_CLASSID",

        editor: "number",
        editorParams: {
          min: 0,
          step: 0.01,
          verticalNavigation: "table",
        },
      },
      {
        title: "SODOCUMENTENTRY_CUSTOMERID",
        field: "SODOCUMENTENTRY_CUSTOMERID",
        editor: "textarea",
      },
      { title: "MEMO", field: "MEMO", editor: "textarea" },
      { title: "TO_DELETE_TeamName", field: "TO_DELETE_TeamName" },
      { title: "TO_DELETE_TeamId", field: "TO_DELETE_TeamId" },
    ],
  });

  return sageTable;
}

function createDownloadCsvButton(tableInstance, year, month) {
  const btn = document.createElement("button");
  btn.id = "download-csv-btn";
  btn.className = "btn btn-primary";
  btn.textContent = "Download CSV";

  // Dynamic filename based on selected period
  const now = new Date();
  const formattedDate = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false, // Forces 24-hour format
  })
    .format(now)
    .replace(", ", " ");

  const filename = `sage_invoice_import_${year}_${month}_${formattedDate}.csv`;

  // Attach click listener directly to the created DOM element
  btn.addEventListener("click", () => {
    console.log("clicked", tableInstance);
    if (tableInstance) {
      tableInstance.download("csv", filename);
    }
  });

  return btn;
}

async function setupInvoicePreviewUI() {
  const main_header = document.getElementById("main-header");
  main_header.innerText = "Sage Invoice Sheet Preview";

  const contBtn = document.getElementById("continue-btn");

  const backBtn = document.getElementById("back-btn");

  if (contBtn) {
    contBtn.disabled = true;
  }

  if (backBtn) {
    backBtn.disabled = false;
    backBtn.onclick = () => window.wizard.back();
  }

  const teamsTable = document.getElementById("invoice-table");
  teamsTable?.replaceChildren();
}
