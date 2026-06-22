"""Module to visualise with matplotlib."""

# python modules
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates
import pandas as pd
import seaborn as sns
from typing import Any, List, Optional, Tuple
import plotly.express as px


def plot_overlay_time_series_matplotlib(
    _df: pd.DataFrame,
    ylim: List[float],
    values: List[Tuple[str, str, str, float]],
    title: str,
    ref: str,
    list_dates_vertical_lines: List[str],
    list_horizontal_lines: Optional[List[float]] = None,
    list_horizontal_lines_2: Optional[List[float]] = None,
    do_show_ticks_every_tuesday: Optional[bool] = False,
    do_set_vertical_ticks: Optional[bool] = False,
    output_file_name: Optional[str] = None,
    do_printout: Optional[bool] = False,
) -> matplotlib.figure.Figure:
    """Plot overlay of any number of time series with matplotlib.

    ref is the column as reference to calculate correlation to.

    values: list of tuple of name, label_name, color, multiplier
    """

    df = _df.copy()

    # Set the figure size and create the plot
    fig, ax = plt.subplots(figsize=(40, 15))

    x = df.index

    # Set the tick locations and labels on the x-axis
    format = "%Y-%m-%d"
    date_form = matplotlib.dates.DateFormatter(format)
    ax.xaxis.set_major_formatter(date_form)
    if do_show_ticks_every_tuesday:
        # Set the locator to show ticks on every Tuesday
        ax.xaxis.set_major_locator(
            matplotlib.dates.WeekdayLocator(byweekday=1)
        )  # 1 corresponds to Tuesday
    ax.tick_params(axis="both", labelsize=25)
    plt.xticks(rotation=90)

    # Set vertical ticks
    if do_set_vertical_ticks:
        # Set vertical ticks based on horizontal line values
        vertical_ticks = (
            [-30, -20, -10, -5, 105, 110, 120, 130]
            + list_horizontal_lines
            + list_horizontal_lines_2
        )
        ax.set_yticks(vertical_ticks)

    for name, label_name, marker, marker_size, color, multiplier in values:
        s = df[name].map(lambda x: x)
        if ref is not None:
            correlation = s.corr(df[ref])
            label_name = f"{label_name}, corr={correlation:.3f}"
        plt.plot(
            x,
            s * multiplier,
            color=color,
            marker=marker,
            label=label_name,
            markersize=marker_size,
        )

    if list_dates_vertical_lines:
        # plot vertical lines
        for str_date in list_dates_vertical_lines:
            # Define the datetime value where you want to add the vertical line
            vertical_line_time = pd.to_datetime(str_date)
            # Add a vertical line at the specified x value
            plt.axvline(x=vertical_line_time, color="black", linestyle="--")
        # also get the first line as the start of the campain
        # assume we set the start and end of campaign at equal times
        # we want to calculate the nubmer of impresions and clicks and uplift from before to fter
        datetime_campaign_start = list_dates_vertical_lines[0]
        df_before = df[df.index < datetime_campaign_start]
        df_after = df[df.index >= datetime_campaign_start]
        # impressions
        num_impressions_before = df_before["impressions"].mean()
        num_impressions_after = df_after["impressions"].mean()
        uplift_impressions = round(
            (num_impressions_after / num_impressions_before - 1) * 100, 0
        )
        title += f", uplift impressions = {uplift_impressions}%"
        # clicks
        num_clicks_before = df_before["clicks"].mean()
        num_clicks_after = df_after["clicks"].mean()
        uplift_clicks = round((num_clicks_after / num_clicks_before - 1) * 100, 0)
        title += f", uplift clicks = {uplift_clicks}%"

    # Add horizontal lines
    if list_horizontal_lines:
        for y_value in list_horizontal_lines:
            ax.hlines(
                y=y_value,
                xmin=x.min(),
                xmax=x.max(),
                colors="black",
                linestyles="dashdot",
            )

    # Add horizontal lines _2
    # solid, dashed, dotted, dashdot
    if list_horizontal_lines_2:
        for y_value in list_horizontal_lines_2:
            ax.hlines(
                y=y_value,
                xmin=x.min(),
                xmax=x.max(),
                colors="darkgray",
                linestyles="dashed",
            )

    plt.ylim(ylim)
    plt.title(title, fontsize=25)
    plt.legend(loc="upper left", fontsize=25)

    # Show the plot
    # plt.show()

    if output_file_name:
        if do_printout:
            print(f"Saving plot to {output_file_name}")
        fig.savefig(output_file_name, bbox_inches="tight")

    plt.close()

    return fig


def create_bar_chart(
    df: pd.DataFrame,
    category_column: str,
    value_column: str,
    title: str,
    output_file_name: Optional[str] = None,
) -> plt.Figure:
    """
    Create a bar chart comparing categories with their corresponding values.

    Args:
    df (pd.DataFrame): The input DataFrame.
    category_column (str): The name of the column containing categories.
    value_column (str): The name of the column containing values to plot.
    title (str): The title of the plot.
    output_file_name (Optional[str]): If provided, save the plot to this file.

    Returns:
    plt.Figure: The matplotlib Figure object.
    """
    # Set the style for the plot
    sns.set_style("whitegrid")

    # Create the figure and axis objects
    fig, ax = plt.subplots(figsize=(8, 6))

    # Create the bar plot
    sns.barplot(data=df, x=category_column, y=value_column, ax=ax)

    # Set the title and labels
    ax.set_title(title, fontsize=20)
    ax.set_xlabel(category_column, fontsize=16)
    ax.set_ylabel(value_column, fontsize=16)

    # Increase tick label size
    ax.tick_params(axis="both", which="major", labelsize=14)

    # Rotate x-axis labels if they are long
    plt.xticks(rotation=45, ha="right")

    # Add value labels on top of each bar
    for i in ax.containers:
        ax.bar_label(i, fmt="%.2f", padding=3, fontsize=12)

    # Adjust layout to prevent label cutoff
    plt.tight_layout()

    # Save the plot if output_file_name is provided
    if output_file_name:
        plt.savefig(output_file_name, dpi=300, bbox_inches="tight")

    return fig


def create_schedule_demand_figure(
    df_demand: pd.DataFrame,
):
    """Create a basic schedule visualization showing 24 hours per day.

    And color the cells with the (forecasted) demand for that hour.

    Args:
        df_demand (pd.DataFrame): DataFrame with datetime index and columns [demand, date, hour]
    """
    # Get staff IDs from df_staff and date range from demand
    start_date = df_demand.index.min().date()
    end_date = df_demand.index.max().date()
    # print(staff_ids)
    # print(start_date, end_date)

    # Create hourly blocks for each staff and day
    all_blocks = []
    # For each day
    current_date = start_date
    while current_date <= end_date:
        # For each hour in the day
        for hour in range(24):
            hour_start = pd.Timestamp(current_date) + pd.Timedelta(hours=hour)
            hour_end = hour_start + pd.Timedelta(hours=1)
            # print(hour_start, hour_end)

            all_blocks.append(
                {
                    "Demand": "Staff needed",
                    "Start": hour_start,
                    "End": hour_end,
                    "demand": df_demand.loc[hour_start, "demand"],
                }
            )
        current_date += pd.Timedelta(days=1)

    df_hourly = pd.DataFrame(all_blocks)

    # Create the figure
    fig = px.timeline(
        df_hourly,
        x_start="Start",
        x_end="End",
        y="Demand",
        color="demand",
        color_continuous_scale="Viridis",  # Choose a color scale
        category_orders={"Demand": ["Staff needed"]},
    )

    # Update layout
    fig.update_layout(
        title="Demand Schedule",
        xaxis_title="Date",
        yaxis_title="Demand",
        height=300,
        width=1000,
        showlegend=True,
        # Ensure the plot is visible
        xaxis_range=[start_date, end_date + pd.Timedelta(days=1)],
        yaxis={"visible": True},
    )

    # Add vertical lines for day boundaries
    current_date = start_date
    while current_date <= end_date:
        fig.add_vline(
            x=pd.Timestamp(current_date),
            line_width=1,
            line_color="black",
            line_dash="solid",
        )
        current_date += pd.Timedelta(days=1)

    # Make sure the blocks are visible
    fig.update_traces(marker_line_color="black", marker_line_width=1, opacity=0.8)
    # # Update xaxis to show date and hour
    # fig.update_xaxes(
    #     tickformat="%Y-%m-%d %H:%M",
    #     dtick=3600000,  # Show every hour
    #     rangeslider_visible=True,  # Add a range slider
    # )
    # Update xaxis to show date and hour every 6 hours
    fig.update_xaxes(
        tickformat="%Y-%m-%d %H:%M",
        dtick=12 * 3600000,  # Show every 12 hours (12 * 3600000 milliseconds)
        # tickfont=dict(color="black"),  # Add black color to tick labels
        # rangeslider_visible=True,  # Add a range slider
    )

    return fig, df_hourly


def create_schedule_solution_figure(
    df_demand: pd.DataFrame,
    df_staff: pd.DataFrame,
    df_schedule: pd.DataFrame,
):
    """Create a basic schedule visualization showing 24 hours per day.

    Args:
        df_demand (pd.DataFrame): DataFrame with datetime index and columns [demand, date, hour]
        df_staff (pd.DataFrame): DataFrame with columns [staff_id, role, hourly_wage, overtime_hourly_wage, ratio_overtime]
        df_schedule (pd.DataFrame): DataFrame with columns staff_id, start_date_time, end_date_time
    """
    # Get staff IDs from df_staff and date range from demand
    staff_ids = sorted(df_staff["staff_id"].unique())
    start_date = df_demand.index.min().date()
    end_date = df_demand.index.max().date()
    # print(staff_ids)
    # print(start_date, end_date)

    # Create hourly blocks for each staff and day
    all_blocks = []

    for staff in staff_ids:
        # find the role of the staff
        staff_role = df_staff.loc[df_staff["staff_id"] == staff, "role"].iloc[0]
        regular_hourly_wage = df_staff.loc[
            df_staff["staff_id"] == staff, "hourly_wage"
        ].iloc[0]
        overtime_hourly_wage = df_staff.loc[
            df_staff["staff_id"] == staff, "overtime_hourly_wage"
        ].iloc[0]
        # For each day
        current_date = start_date
        while current_date <= end_date:
            # For each hour in the day
            for hour in range(24):
                hour_start = pd.Timestamp(current_date) + pd.Timedelta(hours=hour)
                hour_end = hour_start + pd.Timedelta(hours=1)
                # print(hour_start, hour_end)

                all_blocks.append(
                    {
                        "Staff ID": f"{staff}",
                        "Staff": f"{staff} - {staff_role}",
                        "Start": hour_start,
                        "End": hour_end,
                        "Status": "Off",  # Initially all blocks are "Off"
                        "Status_Num": 0,  # Initially all blocks are 0
                        "Status_Overtime": 0,  # Initially all blocks are 0
                        "regular_hourly_wage": regular_hourly_wage,
                        "overtime_hourly_wage": overtime_hourly_wage,
                        "actual_hourly_wage": 0.0,  # Initially all blocks are 0.0
                    }
                )
            current_date += pd.Timedelta(days=1)

    df_hourly = pd.DataFrame(all_blocks)

    if df_schedule is not None:
        # Update the status based on df_schedule
        for _, shift in df_schedule.iterrows():
            staff_id = str(shift["staff_id"])
            shift_start = pd.Timestamp(shift["start_date_time"])
            shift_end = pd.Timestamp(shift["end_date_time"])

            # Calculate regular shift end (9 hours after start)
            regular_shift_end = shift_start + pd.Timedelta(hours=9)

            # Update regular shift hours (first 9 hours)
            regular_mask = (
                (df_hourly["Staff ID"] == staff_id)
                & (df_hourly["Start"] >= shift_start)
                & (df_hourly["Start"] < min(regular_shift_end, shift_end))
            )
            df_hourly.loc[regular_mask, "Status"] = "On Shift"
            df_hourly.loc[regular_mask, "Status_Num"] = 1
            df_hourly.loc[regular_mask, "Status_Overtime"] = 0
            df_hourly.loc[regular_mask, "actual_hourly_wage"] = df_hourly[
                "regular_hourly_wage"
            ]

            # Update overtime hours (after 9 hours)
            if shift_end > regular_shift_end:
                overtime_mask = (
                    (df_hourly["Staff ID"] == staff_id)
                    & (df_hourly["Start"] >= regular_shift_end)
                    & (df_hourly["Start"] < shift_end)
                )
                df_hourly.loc[overtime_mask, "Status"] = "Overtime"
                df_hourly.loc[overtime_mask, "Status_Num"] = 1
                df_hourly.loc[overtime_mask, "Status_Overtime"] = 1
                df_hourly.loc[overtime_mask, "actual_hourly_wage"] = df_hourly[
                    "overtime_hourly_wage"
                ]

            # Update all blocks that fall within this shift
            # mask = (
            #     (df_hourly["Staff ID"] == staff_id)
            #     & (df_hourly["Start"] >= shift_start)
            #     & (df_hourly["Start"] < shift_end)
            # )
            # df_hourly.loc[mask, "Status"] = "On Shift"
            # df_hourly.loc[mask, "Status_Num"] = 1

    # Create the figure
    fig = px.timeline(
        df_hourly,
        x_start="Start",
        x_end="End",
        y="Staff",
        color="Status",
        color_discrete_map={
            "Off": "lightgray",
            "On Shift": "#50C878",  # Emerald green - lighter than regular green
            "Overtime": "darkgreen",
        },
        category_orders={
            "Staff": [
                f"{staff} - {df_staff.loc[df_staff['staff_id'] == staff, 'role'].iloc[0]}"
                for staff in staff_ids
            ]
        },
    )

    # Update layout
    fig.update_layout(
        title="Staff Scheduling Calendar",
        xaxis_title="Date",
        yaxis_title="Staff ID",
        height=600,  # Increased height
        width=1000,  # Explicit width
        showlegend=True,
        # Ensure the plot is visible
        xaxis_range=[start_date, end_date + pd.Timedelta(days=1)],
        yaxis={"visible": True},
        # Position legend at the top, with horizontal orientation
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )

    # Add vertical lines for day boundaries
    current_date = start_date
    while current_date <= end_date:
        fig.add_vline(
            x=pd.Timestamp(current_date),
            line_width=1,
            line_color="black",
            line_dash="solid",
        )
        current_date += pd.Timedelta(days=1)

    # Make sure the blocks are visible
    fig.update_traces(marker_line_color="black", marker_line_width=1, opacity=0.8)
    # # Update xaxis to show date and hour
    # fig.update_xaxes(
    #     tickformat="%Y-%m-%d %H:%M",
    #     dtick=3600000,  # Show every hour
    #     rangeslider_visible=True,  # Add a range slider
    # )

    return fig, df_hourly


def generate_rainbow_colors(num_colors: int = 12) -> List[Tuple[float, float, float]]:
    """Generate a list of rainbow colors."""
    # Define the colors of the rainbow
    rainbow_colors = [
        (1.0, 0.0, 0.0),  # Red
        (1.0, 0.5, 0.0),  # Orange
        (1.0, 1.0, 0.0),  # Yellow
        (0.0, 1.0, 0.0),  # Green
        (0.0, 0.0, 1.0),  # Blue
        (0.5, 0.0, 1.0),  # Indigo
        (0.5, 0.0, 0.5),  # Violet
    ]

    # reverse
    # rainbow_colors = rainbow_colors[::-1]

    # # Interpolate to get the desired number of colors
    # colors = []
    # for i in range(num_colors):
    #     ratio = i / (num_colors - 1)
    #     index = int(ratio * (len(rainbow_colors) - 1))
    #     next_index = min(index + 1, len(rainbow_colors) - 1)
    #     color = tuple(
    #         rainbow_colors[index][j] * (1 - ratio % 1)
    #         + rainbow_colors[next_index][j] * (ratio % 1)
    #         for j in range(3)
    #     )
    #     colors.append(color)

    # Calculate the number of segments between each color
    num_segments = len(rainbow_colors) - 1
    colors_per_segment = num_colors // num_segments
    remainder = num_colors % num_segments

    # Interpolate to get the desired number of colors
    colors = []
    for i in range(num_segments):
        start_color = np.array(rainbow_colors[i])
        end_color = np.array(rainbow_colors[i + 1])
        for j in range(colors_per_segment + (1 if i < remainder else 0)):
            ratio = j / (colors_per_segment + (1 if i < remainder else 0))
            color = start_color * (1 - ratio) + end_color * ratio
            colors.append(tuple(color))

    return colors
