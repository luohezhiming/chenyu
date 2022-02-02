###############################################################################
# WaterTAP Copyright (c) 2021, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National
# Laboratory, National Renewable Energy Laboratory, and National Energy
# Technology Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#
###############################################################################
from pyomo.environ import (ConcreteModel,
                           SolverFactory,
                           assert_optimal_termination)
from pyomo.util.check_units import assert_units_consistent
from idaes.core import FlowsheetBlock
from idaes.core.util import get_solver
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.generic_models.unit_models.heat_exchanger import (HeatExchanger,
                                                             HeatExchangerFlowPattern)

import idaes.core.util.scaling as iscale

from watertap.examples.flowsheets.mvc.components.lmtd_chen_callback import delta_temperature_chen_callback
import watertap.property_models.seawater_prop_pack as props


def main():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={'dynamic': False})
    m.fs.properties = props.SeawaterParameterBlock()
    m.fs.unit = HeatExchanger(default={
        "hot_side_name": "hot",
        "cold_side_name": "cold",
        "hot": {"property_package": m.fs.properties},
        "cold": {"property_package": m.fs.properties},
        "delta_temperature_callback": delta_temperature_chen_callback,
        "flow_pattern": HeatExchangerFlowPattern.countercurrent})

    # scaling
    m.fs.properties.set_default_scaling('flow_mass_phase_comp', 1, index=('Liq', 'H2O'))
    m.fs.properties.set_default_scaling('flow_mass_phase_comp', 1e2, index=('Liq', 'TDS'))
    iscale.set_scaling_factor(m.fs.unit.hot.heat, 1e-3)
    iscale.set_scaling_factor(m.fs.unit.cold.heat, 1e-3)
    iscale.set_scaling_factor(m.fs.unit.overall_heat_transfer_coefficient, 1e-3)
    iscale.set_scaling_factor(m.fs.unit.area, 1)
    iscale.calculate_scaling_factors(m)

    # ---specifications---
    # state variables
    m.fs.unit.hot_inlet.flow_mass_phase_comp[0, 'Liq', 'H2O'].fix(1)
    m.fs.unit.hot_inlet.flow_mass_phase_comp[0, 'Liq', 'TDS'].fix(0.01)
    m.fs.unit.hot_inlet.temperature[0].fix(350)
    m.fs.unit.hot_inlet.pressure[0].fix(2e5)

    m.fs.unit.cold_inlet.flow_mass_phase_comp[0, 'Liq', 'H2O'].fix(0.5)
    m.fs.unit.cold_inlet.flow_mass_phase_comp[0, 'Liq', 'TDS'].fix(0.01)
    m.fs.unit.cold_inlet.temperature[0].fix(298)
    m.fs.unit.cold_inlet.pressure[0].fix(2e5)

    m.fs.unit.area.fix(5)
    m.fs.unit.overall_heat_transfer_coefficient.fix(1000)

    # solving
    assert_units_consistent(m)
    degrees_of_freedom(m)

    m.fs.unit.initialize()

    solver = get_solver()
    results = solver.solve(m, tee=False)
    assert_optimal_termination(results)

    m.fs.unit.report()

    return m

if __name__ == "__main__":
    m = main()