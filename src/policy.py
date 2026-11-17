import csv
import os


class Policy:
    key = ""
    cashValue = 0
    divDepo = 0
    loanBalance = 0
    automaticPremiumLoanBalance = 0
    totalSurrender = 0
    loanAvailable = 0
    cashValuePUA = 0
    premiumDepositFund = 0
    loanInterestCapitalized = 0
    totalAdjustedCostBasis = 0
    screenshotBase64 = ""

    def get_object_attributes(self):
        return [a for a in vars(self) if not a.startswith('__')]

    def header_csv(self):
        return self.get_object_attributes()

    def data_csv(self):
        return [str(getattr(self, a)) for a in self.get_object_attributes()]

    def csv_rows(self):
        return [self.header_csv(), self.data_csv()]


def write_policies_csv(policies, filename, output_folder=None):
    """Write one CSV row per policy, with a single shared header row."""
    policies = list(policies)
    folder = output_folder or os.environ.get('OUTPUT_FOLDER') or '.'
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    with open(path, 'w', newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        if policies:
            writer.writerow(policies[0].header_csv())
            for policy in policies:
                writer.writerow(policy.data_csv())
    return path


class PolicyValueCodes:
    CV_PUA = "Cash Value of Paid Up Additions"
    DIV_DEPO = "Dividends on Deposit"
    LOAN_BALANCE = "Loan Balance"
    AUTO_PREM_LB = "Automatic Premium Loan Balance"
    TOTAL_CSV = "Total Cash Surrender Value"
    LB_AVAIL = "Loan Available"
    GUAR_CASH_VALUE = "Guaranteed Cash Value"
    PREM_DEP_FUND = "Premium Deposit Fund"
    LOAN_INTEREST_CAP = "Loan Interest Capitalized on Loans"
    TOTAL_ACB = "Total Adjusted Cost Basis Amount"
