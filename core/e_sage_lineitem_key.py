from enum import Enum


class sage_lineitem_key(Enum):
    MAIN_PLATFORM_EXPORT = "_MAIN_platform_export"
    MONTHLYFEE_A = "_MonthlyFee_A"
    MONTHLYFEE_B = "_MonthlyFee_B"
    MONTHLYFEE_OTHER = "_MonthlyFee_other"
    FEECREDIT_PLATFORM_EXPORT = "_FeeCredit_platform_export"
    CUSTOM_ROW_ONETIME = "_custom_row_onetime"
    CUSTOM_ROW_REPEAT = "_custom_row_repeat"
    CUSTOM_ROW_ERROR = "_custom_row_error"
    BLANK_loggedexpense = "_loggedexpense" # currently not being used