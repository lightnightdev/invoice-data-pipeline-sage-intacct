function makeChoiceTable(targetEl, onSelectCallback) {
  const table = document.createElement("table");
  table.className = "choice-table";

  table.addEventListener('click', (e) => {
    const row = e.target.closest('.choice-row');
    if (row && typeof onSelectCallback === 'function') {
      onSelectCallback(row.dataset.param);
    }
  });

  if (targetEl && targetEl.parentNode) {
    table.id = targetEl.id;
    targetEl.parentNode.replaceChild(table, targetEl);
  } else if (targetEl) {
    targetEl.appendChild(table);
  }
  return table;
}

function addChoiceTableRow(tableEl, displayText, callbackParam) {
  const tr = document.createElement("tr");
  tr.className = "choice-row";
  tr.dataset.param = callbackParam; // Store parameter in dataset

  const td = document.createElement("td");
  td.className = "choice-cell";
  td.textContent = displayText;

  tr.appendChild(td);
  tableEl.appendChild(tr);
  return tr;
}
