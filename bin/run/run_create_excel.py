"""A Python script to create an Excel file with several sheets.

And in each sheet to generate some random numbers with a rule.
"""

import pandas as pd
from datetime import datetime, timedelta


class ExcelSheetFiller:
    def __init__(self, list_sheet_name, output_path):
        self.list_sheet_name = list_sheet_name
        self.output_path = output_path
        self.sheets_data = {}

    def fill_sheet1(self):
        # Custom logic for Sheet1
        df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
        # Create the header row as specified
        header_row = ["Identifier", "Leg Number", "Attributes"] + [0] * 3 + [1] * 9
        # Pad header_row to match the number of columns if needed
        n_cols = max(len(df.columns), len(header_row))
        while len(df.columns) < n_cols:
            df[f"Extra{len(df.columns)+1}"] = [None] * len(df)
        if len(header_row) < n_cols:
            header_row += [""] * (n_cols - len(header_row))

        # Create the date row
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2025, 1, 1)
        num_dates = n_cols - 3
        date_list = []
        current_date = start_date
        while len(date_list) < num_dates and current_date <= end_date:
            date_list.append(current_date.strftime("%b-%d"))
            current_date += timedelta(days=1)
        date_row = ["", "", ""] + date_list
        if len(date_row) < n_cols:
            date_row += [""] * (n_cols - len(date_row))
        elif len(date_row) > n_cols:
            date_row = date_row[:n_cols]

        # Insert the header and date rows at the top
        header_df = pd.DataFrame([header_row, date_row], columns=df.columns)
        df = header_df.append(df, ignore_index=True)
        self.sheets_data["Sheet1"] = df

    def fill_sheet2(self):
        # Custom logic for Sheet2
        df = pd.DataFrame({"X": [7, 8, 9], "Y": [10, 11, 12]})
        self.sheets_data["Sheet2"] = df

    def fill_sheet3(self):
        # Custom logic for Sheet3
        df = pd.DataFrame({"M": [13, 14, 15], "N": [16, 17, 18]})
        self.sheets_data["Sheet3"] = df

    def fit(self):
        # Call fill methods for each sheet
        for sheet in self.list_sheet_name:
            method_name = f"fill_{sheet.lower()}"
            if hasattr(self, method_name):
                getattr(self, method_name)()
            else:
                # Default dummy DataFrame if no custom method
                self.sheets_data[sheet] = pd.DataFrame({"A": [0], "B": [0]})
        # Write all sheets to Excel
        with pd.ExcelWriter(self.output_path) as writer:
            for sheet, df in self.sheets_data.items():
                df.to_excel(writer, sheet_name=sheet, index=False, header=False)


# Config variable: list of sheet names
list_sheet_name = [
    "Sheet1",
    "Sheet2",
    "Sheet3",
]

# Usage example
if __name__ == "__main__":
    excel_filler = ExcelSheetFiller(list_sheet_name, "output.xlsx")
    excel_filler.fit()
