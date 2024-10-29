import logging
import pandas as pd
import plotly.graph_objects as go
from model import Model


def main():
    log = logging.getLogger("OPT_LOGGER")

    # load your profiles (e.g. get them from ENTSO-E Transparency Platform)
    df_profiles = pd.DataFrame()  # replace with meaningful data

    log.info("Initialize model")
    germany_model = Model(
        df_profiles,
        load=750_000_000,
        pv_p_inst=215_000,
        wind_on_p_inst=115_000,
        wind_off_p_inst=30_000,
        bio_p_inst=5_200,
        hydro_p_inst=2_100,
        batteries_p_inst=25_000,
        batteries_duration=4,
        charge_efficiency=0.90,
        discharge_efficiency=1.0,
        marginal_cost_residual=100,
        capital_cost_residual=1_000,
        min_installed_cap_residual=0,
    )

    log.info("Run optimization")
    opt_state = germany_model.optimize()
    if opt_state[0] == "ok":
        log.info("Optimization successful")
        df_result = germany_model.get_results()
        log.info(
            f'Installed backup power plant capacity: {df_result.loc[df_result["residual_load"] > 0, "residual_load"].max() / 1000:.0f} GW'
        )
        log.info(
            f'Electrical energy from backup power plants: {df_result.loc[df_result["residual_load"] > 0, "residual_load"].sum() / 1000_000:.0f} TWh/a'
        )
        log.info(f'Curtailed Renewables: {df_result["curtailed_re"].sum() / 1000_000:.0f} TWh/a')
        fig = plot_results(df_result / 1000)
        fig.write_html("result_plot.html")

    else:
        log.error("Optimization not successful")


def plot_results(df_plot):
    """Returns a plotly figure object with traces for electricity generation and load"""

    round_digits = 2
    fig = go.Figure()
    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["hydro"],
        name="hydro",
        fill="tonexty",
        line_width=0,
        line_color="#102B41",
        stackgroup="ee",
    )
    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["biomass"],
        name="biomass",
        fill="tonexty",
        line_width=0,
        line_color="#4d8165",
        stackgroup="ee",
    )
    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["wind_off"],
        name="wind offshore",
        fill="tonexty",
        line_width=0,
        line_color="rgb(119, 146, 171)",
        stackgroup="ee",
    )
    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["wind_on"],
        name="wind onshore",
        fill="tonexty",
        line_width=0,
        line_color="rgb(131, 170, 200)",
        stackgroup="ee",
    )
    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["pv"],
        name="pv",
        fill="tonexty",
        line_width=0,
        line_color="rgb(240, 210, 79)",
        stackgroup="ee",
    )

    residual_load = df_plot["residual_load"].copy()
    residual_load.loc[residual_load < 0] = 0
    fig.add_scatter(
        x=df_plot.index,
        y=residual_load.round(round_digits),
        name="residual load",
        fill="tonexty",
        fillpattern={"shape": "/", "size": 6, "solidity": 0.1},
        line_width=0,
        line_color="red",
        stackgroup="ee",
    )

    df_plot["charge"] = df_plot.loc[df_plot["batteries"] <= 0, "batteries"]
    df_plot["discharge"] = df_plot.loc[df_plot["batteries"] > 0, "batteries"]
    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["charge"],
        name="batteries (charge)",
        fill="tonexty",
        fillpattern={"shape": "x", "size": 4, "solidity": 0.7},
        line_width=0,
        line_color="rgb(160, 153, 188)",
        stackgroup="ee",
    )
    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["discharge"],
        name="batteries (discharge)",
        fill="tonexty",
        line_width=0,
        line_color="rgb(160, 153, 188)",
        stackgroup="ee",
    )

    fig.add_scatter(
        x=df_plot.index,
        y=df_plot.round(round_digits)["load"],
        name="load",
        line_color="gray",
    )

    fig.update_yaxes(title="Power [GW]", fixedrange=True)
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 50, "b": 30},
        hovermode="x",
        paper_bgcolor="#f7f7fa",
        plot_bgcolor="#f7f7fa",
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
    )

    return fig


if __name__ == "__main__":
    main()
