import pandas as pd
import pypsa


class Model:
    def __init__(
        self,
        df_profiles,
        load,
        pv_p_inst,
        wind_on_p_inst,
        wind_off_p_inst,
        bio_p_inst,
        hydro_p_inst,
        batteries_p_inst,
        batteries_duration,
        charge_efficiency,
        discharge_efficiency,
        marginal_cost_residual,
        capital_cost_residual,
        min_installed_cap_residual,
    ) -> None:
        """Initializes a power system model

        Args:
            df_profiles (ps.DataFrame): DataFrame with renewable profiles (normalized to installed power, [0,1]) and load profile [0,1] normalized to annual sum.
                                        The DateFrame must contain the columns: "pv_profile", "wind_on_profile", wind_off_profile", "biomass_profile",
                                        "hydro_profile" and "load_profile"
            load (float): sum of electrical load in [MWh/a]
            pv_p_inst (float): installed power pv [MW]
            wind_on_p_inst (float): installed power wind onshore [MW]
            wind_off_p_inst (float): installed power wind offshore [MW]
            bio_p_inst (float): installed power biomass [MW]
            hydro_p_inst (float): installed power hydro [MW]
            batteries_p_inst (float): installed power batteries [MW]
            batteries_duration (float): batteries duration in hours relative to installed power [MW]
            charge_efficiency (float): batteries charge efficiency [0,1]
            discharge_efficiency (float): batteries discharge efficiency [0,1]
            marginal_cost_residual (float): marginal cost of residual power plant [EUR/MWh]
            capital_cost_residual (float): capital cost of residual power plant [EUR/MW]
            min_installed_cap_residual (float): min. installed power of residual power plants [MW]
        """

        self.df_profiles = df_profiles
        self.installed_capacities = {
            "pv": pv_p_inst,
            "wind_on": wind_on_p_inst,
            "wind_off": wind_off_p_inst,
            "biomass": bio_p_inst,
            "hydro": hydro_p_inst,
            "batteries_p_inst": batteries_p_inst,
            "batteries_duration": batteries_duration,
        }
        self.charge_efficiency = charge_efficiency
        self.discharge_efficiency = discharge_efficiency
        self.marginal_cost_residual = marginal_cost_residual
        self.capital_cost_residual = capital_cost_residual
        self.min_installed_cap_residual = min_installed_cap_residual

        self.setup_network()
        self.add_generators()
        self.network.add(
            "Load",
            "load",
            bus="DE",
            p_set=self.df_profiles["load_profile"] * load,
        )
        self.network.add(
            "StorageUnit",
            "batteries",
            bus="DE",
            p_nom=self.installed_capacities["batteries_p_inst"],
            max_hours=self.installed_capacities["batteries_duration"],
            cyclic_state_of_charge=True,
            efficiency_store=self.charge_efficiency,
            efficiency_dispatch=self.discharge_efficiency,
            standing_loss=0.0001,
        )

    def setup_network(self):
        """Sets up the PyPSA network and sets the time steps"""

        self.network = pypsa.Network()
        self.network.set_snapshots(self.df_profiles.index)
        self.network.add("Bus", "DE")

    def add_generators(self):
        """Adds power generator units to the network"""

        self.network.add(
            "Generator",
            "pv",
            bus="DE",
            p_nom=self.installed_capacities["pv"],
            marginal_cost=0.1,
            p_max_pu=(self.df_profiles["pv_profile"]),
        )

        self.network.add(
            "Generator",
            "wind_on",
            bus="DE",
            p_nom=self.installed_capacities["wind_on"],
            marginal_cost=0.1,
            p_max_pu=self.df_profiles["wind_on_profile"],
        )

        self.network.add(
            "Generator",
            "wind_off",
            bus="DE",
            p_nom=self.installed_capacities["wind_off"],
            marginal_cost=0.1,
            p_max_pu=self.df_profiles["wind_off_profile"],
        )

        self.network.add(
            "Generator",
            "biomass",
            bus="DE",
            p_nom=self.installed_capacities["biomass"],
            marginal_cost=0.1,
            p_max_pu=self.df_profiles["biomass_profile"],
        )

        self.network.add(
            "Generator",
            "hydro",
            bus="DE",
            p_nom=self.installed_capacities["hydro"],
            marginal_cost=0.1,
            p_max_pu=self.df_profiles["hydro_profile"],
        )

        self.network.add(
            "Generator",
            "residual_load",
            bus="DE",
            marginal_cost=self.marginal_cost_residual,
            capital_cost=self.capital_cost_residual,
            p_nom_min=self.min_installed_cap_residual,
            p_nom_extendable=True,
        )

    def optimize(self):
        """Runs the otimization and returns the status"""
        self.m = self.network.optimize.create_model()

        self.opt_state = self.network.optimize.solve_model(solver_name="highs")

        return self.opt_state

    def get_results(self):
        """Extracts relevant results from network variable and puts them into one DataFrame"""

        df_power_availability = self.network.generators_t.p_max_pu * self.network.generators.p_nom
        df_power_availability["re_power_availability"] = (
            df_power_availability["pv"]
            + df_power_availability["wind_on"]
            + df_power_availability["wind_off"]
            + df_power_availability["biomass"]
            + df_power_availability["hydro"]
        )

        df_actual_generation = self.network.generators_t.p
        df_actual_generation["actual_re_generation"] = (
            df_actual_generation["pv"]
            + df_actual_generation["wind_on"]
            + df_actual_generation["wind_off"]
            + df_actual_generation["biomass"]
            + df_actual_generation["hydro"]
        )

        df_result = pd.DataFrame()
        df_result["pv"] = df_power_availability["pv"]
        df_result["wind_on"] = df_power_availability["wind_on"]
        df_result["wind_off"] = df_power_availability["wind_off"]
        df_result["biomass"] = df_power_availability["biomass"]
        df_result["hydro"] = df_power_availability["hydro"]
        df_result["batteries"] = self.network.storage_units_t.p["batteries"]
        df_result["load"] = self.network.loads_t.p["load"]
        df_result["curtailed_re"] = (
            df_power_availability["re_power_availability"] - df_actual_generation["actual_re_generation"]
        )
        df_result["residual_load"] = (
            df_result["load"] - df_power_availability["re_power_availability"] - df_result["batteries"]
        )
        df_result.index.name = "time"

        return df_result
