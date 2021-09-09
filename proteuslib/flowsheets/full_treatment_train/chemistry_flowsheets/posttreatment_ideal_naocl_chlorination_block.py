###############################################################################
# ProteusLib Copyright (c) 2021, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National
# Laboratory, National Renewable Energy Laboratory, and National Energy
# Technology Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/nawi-hub/proteuslib/"
#
###############################################################################

"""
    Ideal NaOCl Chlorination posttreatment process
    ----------------------------------------------
    This will build an ideal NaOCl pretreatment block as a combination of a
    Mixer (where NaOCl is added) and an EquilibriumReactor (where pH and free
    chlorine is calculated)

                    NaOCl stream
                        |
                        V
    inlet stream ---> [Mixer] --- outlet stream ---> [EquilibriumReactor] ---> exit stream (to distribution)
"""

# Importing the object for units from pyomo
from pyomo.environ import units as pyunits

# Imports from idaes core
from idaes.core import AqueousPhase
from idaes.core.components import Solvent, Solute, Cation, Anion
from idaes.core.phases import PhaseType as PT

# Imports from idaes generic models
import idaes.generic_models.properties.core.pure.Perrys as Perrys
from idaes.generic_models.properties.core.state_definitions import FTPx
from idaes.generic_models.properties.core.eos.ideal import Ideal

# Importing the enum for concentration unit basis used in the 'get_concentration_term' function
from idaes.generic_models.properties.core.generic.generic_reaction import ConcentrationForm

# Import the object/function for heat of reaction
from idaes.generic_models.properties.core.reactions.dh_rxn import constant_dh_rxn

# Import safe log power law equation
from idaes.generic_models.properties.core.reactions.equilibrium_forms import log_power_law_equil

# Import built-in van't Hoff function
from idaes.generic_models.properties.core.reactions.equilibrium_constant import van_t_hoff

# Import specific pyomo objects
from pyomo.environ import (ConcreteModel,
                           Var,
                           Constraint,
                           SolverStatus,
                           TerminationCondition,
                           value,
                           Suffix)

from idaes.core.util import scaling as iscale
from idaes.core.util.initialization import fix_state_vars, revert_state_vars

# Import pyomo methods to check the system units
from pyomo.util.check_units import assert_units_consistent


from proteuslib.flowsheets.full_treatment_train.util import solve_with_user_scaling, check_dof
from idaes.core.util import get_solver

# Import the idaes objects for Generic Properties and Reactions
from idaes.generic_models.properties.core.generic.generic_property import (
        GenericParameterBlock)
from idaes.generic_models.properties.core.generic.generic_reaction import (
        GenericReactionParameterBlock)

# Import the idaes object for the EquilibriumReactor unit model
from idaes.generic_models.unit_models.equilibrium_reactor import EquilibriumReactor

# Import th idaes object for the Mixer unit model
from idaes.generic_models.unit_models.mixer import Mixer

# Import the core idaes objects for Flowsheets and types of balances
from idaes.core import FlowsheetBlock

# Import log10 function from pyomo
from pyomo.environ import log10

import idaes.logger as idaeslog

# Grab the scaling utilities
from proteuslib.flowsheets.full_treatment_train.electrolyte_scaling_utils import (
    approximate_chemical_state_args,
    calculate_chemical_scaling_factors,
    calculate_chemical_scaling_factors_for_energy_balances)

from proteuslib.flowsheets.full_treatment_train.chemical_flowsheet_util import (
    set_H2O_molefraction, zero_out_non_H2O_molefractions, fix_all_molefractions )

__author__ = "Austin Ladshaw"

# Configuration dictionary
ideal_naocl_thermo_config = {
    "components": {
        'H2O': {"type": Solvent,
              # Define the methods used to calculate the following properties
              "dens_mol_liq_comp": Perrys,
              "enth_mol_liq_comp": Perrys,
              "cp_mol_liq_comp": Perrys,
              "entr_mol_liq_comp": Perrys,
              # Parameter data is always associated with the methods defined above
              "parameter_data": {
                    "mw": (18.0153, pyunits.g/pyunits.mol),
                    "pressure_crit": (220.64E5, pyunits.Pa),
                    "temperature_crit": (647, pyunits.K),
                    # Comes from Perry's Handbook:  p. 2-98
                    "dens_mol_liq_comp_coeff": {
                        '1': (5.459, pyunits.kmol*pyunits.m**-3),
                        '2': (0.30542, pyunits.dimensionless),
                        '3': (647.13, pyunits.K),
                        '4': (0.081, pyunits.dimensionless)},
                    "enth_mol_form_liq_comp_ref": (-285.830, pyunits.kJ/pyunits.mol),
                    "enth_mol_form_vap_comp_ref": (0, pyunits.kJ/pyunits.mol),
                    # Comes from Perry's Handbook:  p. 2-174
                    "cp_mol_liq_comp_coeff": {
                        '1': (2.7637E5, pyunits.J/pyunits.kmol/pyunits.K),
                        '2': (-2.0901E3, pyunits.J/pyunits.kmol/pyunits.K**2),
                        '3': (8.125, pyunits.J/pyunits.kmol/pyunits.K**3),
                        '4': (-1.4116E-2, pyunits.J/pyunits.kmol/pyunits.K**4),
                        '5': (9.3701E-6, pyunits.J/pyunits.kmol/pyunits.K**5)},
                    "cp_mol_ig_comp_coeff": {
                        'A': (30.09200, pyunits.J/pyunits.mol/pyunits.K),
                        'B': (6.832514, pyunits.J*pyunits.mol**-1*pyunits.K**-1*pyunits.kiloK**-1),
                        'C': (6.793435, pyunits.J*pyunits.mol**-1*pyunits.K**-1*pyunits.kiloK**-2),
                        'D': (-2.534480, pyunits.J*pyunits.mol**-1*pyunits.K**-1*pyunits.kiloK**-3),
                        'E': (0.082139, pyunits.J*pyunits.mol**-1*pyunits.K**-1*pyunits.kiloK**2),
                        'F': (-250.8810, pyunits.kJ/pyunits.mol),
                        'G': (223.3967, pyunits.J/pyunits.mol/pyunits.K),
                        'H': (0, pyunits.kJ/pyunits.mol)},
                    "entr_mol_form_liq_comp_ref": (69.95, pyunits.J/pyunits.K/pyunits.mol),
                    "pressure_sat_comp_coeff": {
                        'A': (4.6543, None),  # [1], temperature range 255.9 K - 373 K
                        'B': (1435.264, pyunits.K),
                        'C': (-64.848, pyunits.K)}
                                },
                    # End parameter_data
                    },
        'H_+': {"type": Cation, "charge": 1,
              # Define the methods used to calculate the following properties
              "dens_mol_liq_comp": Perrys,
              "enth_mol_liq_comp": Perrys,
              "cp_mol_liq_comp": Perrys,
              "entr_mol_liq_comp": Perrys,
              # Parameter data is always associated with the methods defined above
              "parameter_data": {
                    "mw": (1.00784, pyunits.g/pyunits.mol),
                    "dens_mol_liq_comp_coeff": {
                        '1': (5.459, pyunits.kmol*pyunits.m**-3),
                        '2': (0.30542, pyunits.dimensionless),
                        '3': (647.13, pyunits.K),
                        '4': (0.081, pyunits.dimensionless)},
                    "enth_mol_form_liq_comp_ref": (-230.000, pyunits.kJ/pyunits.mol),
                    "cp_mol_liq_comp_coeff": {
                        '1': (2.7637E5, pyunits.J/pyunits.kmol/pyunits.K),
                        '2': (-2.0901E3, pyunits.J/pyunits.kmol/pyunits.K**2),
                        '3': (8.125, pyunits.J/pyunits.kmol/pyunits.K**3),
                        '4': (-1.4116E-2, pyunits.J/pyunits.kmol/pyunits.K**4),
                        '5': (9.3701E-6, pyunits.J/pyunits.kmol/pyunits.K**5)},
                    "entr_mol_form_liq_comp_ref": (-10.75, pyunits.J/pyunits.K/pyunits.mol)
                                },
                    # End parameter_data
                    },
        'Na_+': {"type": Cation, "charge": 1,
              # Define the methods used to calculate the following properties
              "dens_mol_liq_comp": Perrys,
              "enth_mol_liq_comp": Perrys,
              "cp_mol_liq_comp": Perrys,
              "entr_mol_liq_comp": Perrys,
              # Parameter data is always associated with the methods defined above
              "parameter_data": {
                    "mw": (22.989769, pyunits.g/pyunits.mol),
                    "dens_mol_liq_comp_coeff": {
                        '1': (5.252, pyunits.kmol*pyunits.m**-3),
                        '2': (0.347, pyunits.dimensionless),
                        '3': (1595.8, pyunits.K),
                        '4': (0.6598, pyunits.dimensionless)},
                    "enth_mol_form_liq_comp_ref": (-240.1, pyunits.J/pyunits.mol),
                    "cp_mol_liq_comp_coeff": {
                        '1': (167039, pyunits.J/pyunits.kmol/pyunits.K),
                        '2': (0, pyunits.J/pyunits.kmol/pyunits.K**2),
                        '3': (0, pyunits.J/pyunits.kmol/pyunits.K**3),
                        '4': (0, pyunits.J/pyunits.kmol/pyunits.K**4),
                        '5': (0, pyunits.J/pyunits.kmol/pyunits.K**5)},
                    "entr_mol_form_liq_comp_ref": (59, pyunits.J/pyunits.K/pyunits.mol)
                                },
                    # End parameter_data
                    },
        'Cl_-': {"type": Anion, "charge": -1,
              # Define the methods used to calculate the following properties
              "dens_mol_liq_comp": Perrys,
              "enth_mol_liq_comp": Perrys,
              "cp_mol_liq_comp": Perrys,
              "entr_mol_liq_comp": Perrys,
              # Parameter data is always associated with the methods defined above
              "parameter_data": {
                    "mw": (35.453, pyunits.g/pyunits.mol),
                    "dens_mol_liq_comp_coeff": {
                        '1': (4.985, pyunits.kmol*pyunits.m**-3),
                        '2': (0.36, pyunits.dimensionless),
                        '3': (1464.06, pyunits.K),
                        '4': (0.739, pyunits.dimensionless)},
                    "enth_mol_form_liq_comp_ref": (-167.2, pyunits.kJ/pyunits.mol),
                    "cp_mol_liq_comp_coeff": {
                        '1': (83993.8, pyunits.J/pyunits.kmol/pyunits.K),
                        '2': (0, pyunits.J/pyunits.kmol/pyunits.K**2),
                        '3': (0, pyunits.J/pyunits.kmol/pyunits.K**3),
                        '4': (0, pyunits.J/pyunits.kmol/pyunits.K**4),
                        '5': (0, pyunits.J/pyunits.kmol/pyunits.K**5)},
                    "entr_mol_form_liq_comp_ref": (56.5, pyunits.J/pyunits.K/pyunits.mol)
                                },
                    # End parameter_data
                    },
        'OH_-': {"type": Anion,
                "charge": -1,
              # Define the methods used to calculate the following properties
              "dens_mol_liq_comp": Perrys,
              "enth_mol_liq_comp": Perrys,
              "cp_mol_liq_comp": Perrys,
              "entr_mol_liq_comp": Perrys,
              # Parameter data is always associated with the methods defined above
              "parameter_data": {
                    "mw": (17.008, pyunits.g/pyunits.mol),
                    "dens_mol_liq_comp_coeff": {
                        '1': (5.459, pyunits.kmol*pyunits.m**-3),
                        '2': (0.30542, pyunits.dimensionless),
                        '3': (647.13, pyunits.K),
                        '4': (0.081, pyunits.dimensionless)},
                    "enth_mol_form_liq_comp_ref": (-230.000, pyunits.kJ/pyunits.mol),
                    "cp_mol_liq_comp_coeff": {
                        '1': (2.7637E5, pyunits.J/pyunits.kmol/pyunits.K),
                        '2': (-2.0901E3, pyunits.J/pyunits.kmol/pyunits.K**2),
                        '3': (8.125, pyunits.J/pyunits.kmol/pyunits.K**3),
                        '4': (-1.4116E-2, pyunits.J/pyunits.kmol/pyunits.K**4),
                        '5': (9.3701E-6, pyunits.J/pyunits.kmol/pyunits.K**5)},
                    "entr_mol_form_liq_comp_ref": (-10.75, pyunits.J/pyunits.K/pyunits.mol)
                                },
                    # End parameter_data
                    },
        'HOCl': {"type": Solute, "valid_phase_types": PT.aqueousPhase,
              # Define the methods used to calculate the following properties
              "dens_mol_liq_comp": Perrys,
              "enth_mol_liq_comp": Perrys,
              "cp_mol_liq_comp": Perrys,
              "entr_mol_liq_comp": Perrys,
              # Parameter data is always associated with the methods defined above
              "parameter_data": {
                    "mw": (52.46, pyunits.g/pyunits.mol),
                    "dens_mol_liq_comp_coeff": {
                        '1': (4.985, pyunits.kmol*pyunits.m**-3),
                        '2': (0.36, pyunits.dimensionless),
                        '3': (1464.06, pyunits.K),
                        '4': (0.739, pyunits.dimensionless)},
                    "enth_mol_form_liq_comp_ref": (-120.9, pyunits.kJ/pyunits.mol),
                    "cp_mol_liq_comp_coeff": {
                        '1': (83993.8, pyunits.J/pyunits.kmol/pyunits.K),
                        '2': (0, pyunits.J/pyunits.kmol/pyunits.K**2),
                        '3': (0, pyunits.J/pyunits.kmol/pyunits.K**3),
                        '4': (0, pyunits.J/pyunits.kmol/pyunits.K**4),
                        '5': (0, pyunits.J/pyunits.kmol/pyunits.K**5)},
                    "entr_mol_form_liq_comp_ref": (142, pyunits.J/pyunits.K/pyunits.mol)
                                },
                    # End parameter_data
                    },
        'OCl_-': {"type": Anion, "charge": -1,
              # Define the methods used to calculate the following properties
              "dens_mol_liq_comp": Perrys,
              "enth_mol_liq_comp": Perrys,
              "cp_mol_liq_comp": Perrys,
              "entr_mol_liq_comp": Perrys,
              # Parameter data is always associated with the methods defined above
              "parameter_data": {
                    "mw": (51.46, pyunits.g/pyunits.mol),
                    "dens_mol_liq_comp_coeff": {
                        '1': (4.985, pyunits.kmol*pyunits.m**-3),
                        '2': (0.36, pyunits.dimensionless),
                        '3': (1464.06, pyunits.K),
                        '4': (0.739, pyunits.dimensionless)},
                    "enth_mol_form_liq_comp_ref": (-107.1, pyunits.kJ/pyunits.mol),
                    "cp_mol_liq_comp_coeff": {
                        '1': (83993.8, pyunits.J/pyunits.kmol/pyunits.K),
                        '2': (0, pyunits.J/pyunits.kmol/pyunits.K**2),
                        '3': (0, pyunits.J/pyunits.kmol/pyunits.K**3),
                        '4': (0, pyunits.J/pyunits.kmol/pyunits.K**4),
                        '5': (0, pyunits.J/pyunits.kmol/pyunits.K**5)},
                    "entr_mol_form_liq_comp_ref": (42, pyunits.J/pyunits.K/pyunits.mol)
                                },
                    # End parameter_data
                    }
              },
              # End Component list
        "phases":  {'Liq': {"type": AqueousPhase,
                            "equation_of_state": Ideal},
                    },

        "state_definition": FTPx,
        "state_bounds": {"flow_mol": (0, 50, 100),
                         "temperature": (273.15, 300, 650),
                         "pressure": (5e4, 1e5, 1e6)
                        },

        "pressure_ref": 1e5,
        "temperature_ref": 300,
        "base_units": {"time": pyunits.s,
                       "length": pyunits.m,
                       "mass": pyunits.kg,
                       "amount": pyunits.mol,
                       "temperature": pyunits.K},

    }
    # End simple_naocl_thermo_config definition

# This config is REQUIRED to use EquilibriumReactor even if we have no equilibrium reactions
ideal_naocl_reaction_config = {
    "base_units": {"time": pyunits.s,
                   "length": pyunits.m,
                   "mass": pyunits.kg,
                   "amount": pyunits.mol,
                   "temperature": pyunits.K},
    "equilibrium_reactions": {
        "H2O_Kw": {
                "stoichiometry": {("Liq", "H2O"): -1,
                                 ("Liq", "H_+"): 1,
                                 ("Liq", "OH_-"): 1},
               "heat_of_reaction": constant_dh_rxn,
               "equilibrium_constant": van_t_hoff,
               "equilibrium_form": log_power_law_equil,
               "concentration_form": ConcentrationForm.moleFraction,
               "parameter_data": {
                   "dh_rxn_ref": (55.830, pyunits.J/pyunits.mol),
                   "k_eq_ref": (10**-14/55.2/55.2, pyunits.dimensionless),
                   "T_eq_ref": (298, pyunits.K),

                   # By default, reaction orders follow stoichiometry
                   #    manually set reaction order here to override
                   "reaction_order": {("Liq", "H2O"): 0,
                                    ("Liq", "H_+"): 1,
                                    ("Liq", "OH_-"): 1}
                    }
                    # End parameter_data
               },
        "HOCl_Ka": {
                "stoichiometry": {("Liq", "HOCl"): -1,
                                 ("Liq", "H_+"): 1,
                                 ("Liq", "OCl_-"): 1},
               "heat_of_reaction": constant_dh_rxn,
               "equilibrium_constant": van_t_hoff,
               "equilibrium_form": log_power_law_equil,
               "concentration_form": ConcentrationForm.moleFraction,
               "parameter_data": {
                   "dh_rxn_ref": (13.8, pyunits.J/pyunits.mol),
                   "k_eq_ref": (10**-7.6422/55.2, pyunits.dimensionless),
                   "T_eq_ref": (298, pyunits.K),

                   # By default, reaction orders follow stoichiometry
                   #    manually set reaction order here to override
                   "reaction_order": {("Liq", "HOCl"): -1,
                                    ("Liq", "H_+"): 1,
                                    ("Liq", "OCl_-"): 1}
                    }
                    # End parameter_data
               }
               # End R2
         }
         # End equilibrium_reactions
    }
    # End reaction_config definition

# Get default solver for testing
solver = get_solver()

def build_ideal_naocl_prop(model):
    model.fs.ideal_naocl_thermo_params = GenericParameterBlock(default=ideal_naocl_thermo_config)
    model.fs.ideal_naocl_rxn_params = GenericReactionParameterBlock(
            default={"property_package": model.fs.ideal_naocl_thermo_params, **ideal_naocl_reaction_config})

def build_ideal_naocl_mixer_unit(model):
    model.fs.ideal_naocl_mixer_unit = Mixer(default={
            "property_package": model.fs.ideal_naocl_thermo_params,
            "inlet_list": ["inlet_stream", "naocl_stream"]})

    # add new constraint for dosing rate (deactivate constraint for OCl_-)
    dr = model.fs.ideal_naocl_mixer_unit.naocl_stream.flow_mol[0].value* \
            model.fs.ideal_naocl_mixer_unit.naocl_stream.mole_frac_comp[0, "OCl_-"].value
    dr = dr*74.44*1000
    model.fs.ideal_naocl_mixer_unit.dosing_rate = Var(initialize=dr)

    def _dosing_rate_cons(blk):
        return blk.dosing_rate == blk.naocl_stream.flow_mol[0]*blk.naocl_stream.mole_frac_comp[0, "OCl_-"]*74.44*1000

    model.fs.ideal_naocl_mixer_unit.dosing_cons = Constraint( rule=_dosing_rate_cons )

def set_ideal_naocl_mixer_inlets(model, dosing_rate_of_NaOCl_mg_per_s = 0.4,
                                        inlet_water_density_kg_per_L = 1,
                                        inlet_temperature_K = 298,
                                        inlet_pressure_Pa = 101325,
                                        inlet_flow_mol_per_s = 10):

    #inlet stream
    model.fs.ideal_naocl_mixer_unit.inlet_stream.flow_mol[0].set_value(inlet_flow_mol_per_s)
    model.fs.ideal_naocl_mixer_unit.inlet_stream.pressure[0].set_value(inlet_pressure_Pa)
    model.fs.ideal_naocl_mixer_unit.inlet_stream.temperature[0].set_value(inlet_temperature_K)

    zero_out_non_H2O_molefractions(model.fs.ideal_naocl_mixer_unit.inlet_stream)
    set_H2O_molefraction(model.fs.ideal_naocl_mixer_unit.inlet_stream)

    #naocl stream
    model.fs.ideal_naocl_mixer_unit.naocl_stream.pressure[0].set_value(inlet_pressure_Pa)
    model.fs.ideal_naocl_mixer_unit.naocl_stream.temperature[0].set_value(inlet_temperature_K)
    # Use given dosing rate value to estimate OCl_- molefraction and flow rate for naocl stream
    zero_out_non_H2O_molefractions(model.fs.ideal_naocl_mixer_unit.naocl_stream)
    model.fs.ideal_naocl_mixer_unit.naocl_stream.mole_frac_comp[0, "OCl_-"].set_value(0.5)
    model.fs.ideal_naocl_mixer_unit.naocl_stream.mole_frac_comp[0, "Na_+"].set_value(0.5)
    set_H2O_molefraction(model.fs.ideal_naocl_mixer_unit.naocl_stream)
    flow_of_naocl = dosing_rate_of_NaOCl_mg_per_s/ \
                model.fs.ideal_naocl_mixer_unit.naocl_stream.mole_frac_comp[0, "OCl_-"].value/ \
                74.44/1000
    model.fs.ideal_naocl_mixer_unit.naocl_stream.flow_mol[0].set_value(flow_of_naocl)

    model.fs.ideal_naocl_mixer_unit.dosing_rate.set_value(dosing_rate_of_NaOCl_mg_per_s)

def fix_ideal_naocl_mixer_inlets(model):
    model.fs.ideal_naocl_mixer_unit.inlet_stream.flow_mol[0].fix()
    model.fs.ideal_naocl_mixer_unit.inlet_stream.pressure[0].fix()
    model.fs.ideal_naocl_mixer_unit.inlet_stream.temperature[0].fix()
    fix_all_molefractions(model.fs.ideal_naocl_mixer_unit.inlet_stream)

    model.fs.ideal_naocl_mixer_unit.naocl_stream.flow_mol[0].fix()
    model.fs.ideal_naocl_mixer_unit.naocl_stream.pressure[0].fix()
    model.fs.ideal_naocl_mixer_unit.naocl_stream.temperature[0].fix()
    fix_all_molefractions(model.fs.ideal_naocl_mixer_unit.naocl_stream)

# basic jacobian scaling for this unit
def scale_ideal_naocl_mixer(unit):
    iscale.constraint_autoscale_large_jac(unit)

def initialize_ideal_naocl_mixer(unit, debug_out=False):
    solver.options['bound_push'] = 1e-10
    solver.options['mu_init'] = 1e-6
    solver.options["nlp_scaling_method"] = "user-scaling"
    was_fixed = False
    if unit.naocl_stream.flow_mol[0].is_fixed() == False:
        unit.naocl_stream.flow_mol[0].fix()
        was_fixed = True
    if debug_out == True:
        unit.initialize(optarg=solver.options, outlvl=idaeslog.DEBUG)
    else:
        unit.initialize(optarg=solver.options)
    if was_fixed == True:
        unit.naocl_stream.flow_mol[0].unfix()

def display_results_of_ideal_naocl_mixer(unit):
    print()
    print("=========== Ideal NaOCl Mixer Results ============")
    print("Outlet Temperature:       \t" + str(unit.outlet.temperature[0].value))
    print("Outlet Pressure:          \t" + str(unit.outlet.pressure[0].value))
    print("Outlet FlowMole:          \t" + str(unit.outlet.flow_mol[0].value))
    print()
    total_molar_density = 55.6
    total_salt = value(unit.outlet.mole_frac_comp[0, "Na_+"])*total_molar_density*23
    total_salt += value(unit.outlet.mole_frac_comp[0, "Cl_-"])*total_molar_density*35.4
    psu = total_salt/(total_molar_density*18)*1000
    print("STP Salinity (PSU):           \t" + str(psu))
    print("NaOCl Dosing Rate (mg/s): \t" + str(unit.dosing_rate.value))
    print()
    unit.outlet.mole_frac_comp.pprint()
    print("-------------------------------------------------")
    print()

def build_ideal_naocl_chlorination_block(model):

    # Add properties to model
    build_ideal_naocl_prop(model)

    # Add mixer to the model
    build_ideal_naocl_mixer_unit(model)


def run_ideal_naocl_mixer_example(fixed_dosage=False):
    model = ConcreteModel()
    model.fs = FlowsheetBlock(default={"dynamic": False})

    # Add properties to model
    build_ideal_naocl_prop(model)

    # Add mixer to the model
    build_ideal_naocl_mixer_unit(model)

    # Set some inlet values
    set_ideal_naocl_mixer_inlets(model)

    # Fix the inlets for a solve
    fix_ideal_naocl_mixer_inlets(model)

    # unfix the flow_mol for the naocl_stream and fix dosing rate (alt form)
    if fixed_dosage == True:
        model.fs.ideal_naocl_mixer_unit.naocl_stream.flow_mol[0].unfix()
        model.fs.ideal_naocl_mixer_unit.dosing_rate.fix()

    check_dof(model)

    # scale the mixer
    scale_ideal_naocl_mixer(model.fs.ideal_naocl_mixer_unit)

    # initializer mixer
    initialize_ideal_naocl_mixer(model.fs.ideal_naocl_mixer_unit)

    # solve with user scaling
    solve_with_user_scaling(model, tee=True, bound_push=1e-10, mu_init=1e-6)

    display_results_of_ideal_naocl_mixer(model.fs.ideal_naocl_mixer_unit)


    return model

def run_chlorination_block_example():
    model = ConcreteModel()
    model.fs = FlowsheetBlock(default={"dynamic": False})

    build_ideal_naocl_chlorination_block(model)

    return model

if __name__ == "__main__":
    model = run_ideal_naocl_mixer_example()