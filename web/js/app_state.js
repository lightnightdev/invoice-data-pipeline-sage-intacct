class ApplicationState {
  constructor() {
    this.reset();
  }

  reset() {
    this.selected_teams = [];
    this.all_sageid = [];
    this.sageid_teamid = {};
    this.teamid_teamtype = {};
    this.teamid_teamname = {};
    this.loggedexpense_names = [];
    this.year = null;
    this.month = null;
    this.loggedexpense_options = {};
    this.loggedexpense_unselected = [];
    this.custom_rows = {};
    this.custom_rows_unselected = [];
  }
  setSelectedTeams(selectedTeams) {
    this.selected_teams = selectedTeams;
  }

  setPeriod(year, month) {
    this.year = Number(year);
    this.month = Number(month);
  }

  setSageIds(sageids) {
    this.all_sageid = sageids;
  }

  setTeamIds(sageid_teamid) {
    this.sageid_teamid = sageid_teamid;
  }

  setTeamNames(teamid_teamname) {
    this.teamid_teamname = teamid_teamname;
  }

  setTeamTypes(teamid_teamtype) {
    this.teamid_teamtype = teamid_teamtype;
  }

  setloggedexpenseSelections(selectedloggedexpenseRows) {
    this.loggedexpense_names = selectedloggedexpenseRows.map((r) => r.LoggedExpenseName);
    this.loggedexpense_options = selectedloggedexpenseRows;
  }

  setCustomRows(customRows) {
    this.custom_rows = customRows;
  }

  setloggedexpenseUnselected(unselectedloggedexpenseNames) {
    this.loggedexpense_unselected = unselectedloggedexpenseNames
  }

  setCustomRowsUnselected(unselectedCustomRows) {
    this.custom_rows_unselected = unselectedCustomRows
  }
}

// Singleton instance on window
window.AppState = new ApplicationState();
