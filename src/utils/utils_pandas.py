"""Module of functions utils for pandas."""

import ast
import numpy as np
import pandas as pd
from typing import Any
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO


def str_to_python_object(string: str) -> Any:
    """Convert pandas column from string to python object."""
    return ast.literal_eval(string)


def move_column_in_first_position(
    df: pd.DataFrame,
    column_to_move: str,
) -> pd.DataFrame:
    """Return a dataframe with a column moved in first position."""
    # Reorder columns to move 'C' to the first position
    new_order = [column_to_move] + [col for col in df if col != column_to_move]
    df = df[new_order]
    return df


def get_style_df_color_code_by_values(
    df: pd.DataFrame, title: str, vmin_values: float, vmax_values: float
):
    """Get a style df."""
    # df1 = df1.drop(["datetime", "asset", "norgate"], axis=1)
    styled_df = df.style.background_gradient(
        cmap="RdYlGn",
        vmin=vmin_values,
        vmax=vmax_values,
        subset=pd.IndexSlice[:, df.columns],
    )
    # Apply background gradient to each column separately
    # styled_df = pd.DataFrame()
    # for col in df.columns:
    #    styled_df[col] = df[col].style.background_gradient(
    #        cmap="RdYlGn", vmin=vmin_values[col], vmax=vmax_values[col]
    #    )

    # print(df.dtypes)
    # Define a formatting dictionary
    # format_dict = {col: "{:.1f}" for col, dtype in df.dtypes.items() if dtype == float}
    # Define a formatting dictionary
    format_dict = {}
    # Apply different formats based on column names
    for col, dtype in df.dtypes.items():

        if dtype == float:
            if col in [
                "Open",
                "High",
                "Low",
                "Close",
                "aco",
                "acc",
                "tEN",
                "tEX",
                "tPR",
                "tSL",
                "tNU",
                "tPLu",
                "tPLm",
                "tRI",
                "tRRu",
                "tRRm",
            ]:
                # closing price
                format_dict[col] = "{:.4f}"
            elif col == "Volume":
                # closing price
                format_dict[col] = "{:.0f}"
            elif col == "market":
                format_dict[col] = "{:.1f}"
            elif col.startswith("i"):
                # index
                format_dict[col] = "{:.0f}"
            elif col.startswith("pc"):
                # probability
                format_dict[col] = "{:.2f}"
            elif col.startswith("p"):
                # probability
                format_dict[col] = "{:.1f}"
            elif col.endswith("n"):
                # normalised positioning to OI, it will be fractional
                format_dict[col] = "{:.3f}"
            elif col.endswith("s"):
                # standard positioning, it will be integer
                format_dict[col] = "{:.0f}"
            elif col in ["OI", "s", "as"]:
                format_dict[col] = "{:.0f}"
            elif col.endswith("_i"):
                # index
                format_dict[col] = "{:.0f}"
            elif col.endswith("_p"):
                # probability
                format_dict[col] = "{:.1f}"
            elif col.endswith("_z"):
                # z-score
                format_dict[col] = "{:.2f}"
            elif (
                col.endswith("AM1")
                or col.endswith("AM2")
                or col.endswith("AM3")
                or col.endswith("AM4")
                or col.endswith("AM10")
                or col.endswith("AM20")
                or col.endswith("AM30")
                or col.endswith("AM40")
            ):
                # arithmetic or harmonic means
                format_dict[col] = "{:.1f}"
            elif col[2] == "i":
                # index
                format_dict[col] = "{:.0f}"
            elif col[-3] == "i":
                # index
                format_dict[col] = "{:.0f}"

            elif col[-3] == "p":
                # probabilities
                format_dict[col] = "{:.1f}"
            elif col[-3] == "z":
                # z-scores
                format_dict[col] = "{:.1f}"
            else:
                print(f"Column {col} will not be formatted.")
            # format_dict[col] = "{:.3f}"

    # Apply the formatting dictionary to the Styler
    styled_df = styled_df.format(format_dict)
    # add title
    styled_df.set_caption(title).set_table_styles(
        [
            {
                "selector": "caption",
                "props": [("font-size", "20px")],  # Change the font size to 20px
            }
        ]
    )

    # Increase font size for specific columns
    styled_df = styled_df.set_table_styles(
        [
            # Increase font size for index 5
            {
                "selector": "th.col5, td.col5",
                "props": [("font-weight", "bold")],
            },
            # then every 3
            {
                "selector": "th.col8, td.col8",
                "props": [("font-weight", "bold")],
            },
            {
                "selector": "th.col11, td.col11",
                "props": [("font-weight", "bold")],
            },
            {
                "selector": "th.col14, td.col14",
                "props": [("font-weight", "bold")],
            },
        ]
    )

    return styled_df

    # vertical lines below do not work, they are under the gradient color coding
    # Function to add vertical lines between columns
    def add_vertical_lines(df, columns):
        styles = []
        for col in df.columns:
            col_index = df.columns.get_loc(col)
            style = {
                "selector": f"th.col{col_index}",
                "props": [
                    ("border-right", "4px solid black"),  # Thicker border
                    ("padding", "8px"),  # Increase padding for better visibility
                ],
            }
            styles.append(style)
        return styles

    # Add vertical lines between columns
    styled_df = styled_df.set_table_styles(add_vertical_lines(df, df.columns))

    return styled_df


def screenshot_styled_df(styled_df, output_file_name: str) -> None:
    """Screenshot styled_df to create automatically an image.

    Not works with multindex
    """
    import imgkit

    # Render the styled DataFrame to HTML
    html = styled_df.to_html()

    # Save the HTML content to a file
    with open(output_file_name, "w") as f:
        f.write(html)

    # Convert HTML to image
    # imgkit.from_file("styled_dataframe.html", "styled_dataframe.png")
    return

    # Display the styled DataFrame
    plt.figure(figsize=(10, 6))  # Adjust the figure size as needed
    plt.imshow(styled_df.to_html(), interpolation="none")
    plt.axis("off")  # Turn off axis
    plt.tight_layout()

    # Save the figure as an image
    plt.savefig(output_file_name, bbox_inches="tight", pad_inches=0)

    # Display the styled DataFrame


# Assuming df is your DataFrame
def find_ndarray_columns(df: pd.DataFrame) -> list:
    """Find columns of type numpy array in a pandas dataframe."""
    # Filter columns with dtype 'object'
    object_columns = df.select_dtypes(include=["object"]).columns

    # Check if the first element in each object column is an np.ndarray
    ndarray_columns = [
        col for col in object_columns if isinstance(df[col].iloc[0], np.ndarray)
    ]

    return ndarray_columns
