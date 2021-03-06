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
"""
Tests for zero-order nanofiltration model
"""
import pytest
from io import StringIO

from pyomo.environ import (
    check_optimal_termination, ConcreteModel, Constraint, value, Var)
from pyomo.util.check_units import assert_units_consistent

from idaes.core import FlowsheetBlock
from idaes.core.util import get_solver
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.testing import initialization_tester

from watertap.unit_models.zero_order import NanofiltrationZO
from watertap.core.wt_database import Database
from watertap.core.zero_order_properties import WaterParameterBlock

solver = get_solver()


class TestNFZO:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.db = Database()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(
            default={"solute_list": ["sulfur", "toc", "tss"]})

        m.fs.unit = NanofiltrationZO(default={
            "property_package": m.fs.params,
            "database": m.db})

        m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(10000)
        m.fs.unit.inlet.flow_mass_comp[0, "sulfur"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "toc"].fix(2)
        m.fs.unit.inlet.flow_mass_comp[0, "tss"].fix(3)

        return m

    @pytest.mark.unit
    def test_build(self, model):
        assert model.fs.unit.config.database == model.db

        assert isinstance(model.fs.unit.electricity, Var)
        assert isinstance(model.fs.unit.energy_electric_flow_vol_inlet, Var)

        assert isinstance(model.fs.unit.electricity_consumption, Constraint)

    @pytest.mark.component
    def test_load_parameters(self, model):
        data = model.db.get_unit_operation_parameters("nanofiltration")

        model.fs.unit.load_parameters_from_database()

        assert model.fs.unit.recovery_frac_mass_H2O[0].fixed
        assert model.fs.unit.recovery_frac_mass_H2O[0].value == \
            data["recovery_frac_mass_H2O"]["value"]

        for (t, j), v in model.fs.unit.removal_frac_mass_solute.items():
            assert v.fixed
            assert v.value == data["removal_frac_mass_solute"][j]["value"]

        assert model.fs.unit.energy_electric_flow_vol_inlet.fixed
        assert model.fs.unit.energy_electric_flow_vol_inlet.value == data[
            "energy_electric_flow_vol_inlet"]["value"]

    @pytest.mark.component
    def test_degrees_of_freedom(self, model):
        assert degrees_of_freedom(model.fs.unit) == 0

    @pytest.mark.component
    def test_unit_consistency(self, model):
        assert_units_consistent(model.fs.unit)

    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert check_optimal_termination(results)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert (pytest.approx(8.50062, rel=1e-5) ==
                value(model.fs.unit.properties_treated[0].flow_vol))
        assert (pytest.approx(0.00352915, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["sulfur"]))
        assert (pytest.approx(0.0588192, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["toc"]))
        assert (pytest.approx(0.0105875, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["tss"]))

        assert (pytest.approx(1.50538, rel=1e-5) ==
                value(model.fs.unit.properties_byproduct[0].flow_vol))
        assert (pytest.approx(0.644356, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["sulfur"]))
        assert (pytest.approx(0.996426, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["toc"]))
        assert (pytest.approx(1.93307, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["tss"]))

        assert (pytest.approx(8333.42, rel=1e-5) ==
                value(model.fs.unit.electricity[0]))

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        for j in model.fs.params.component_list:
            assert 1e-6 >= abs(value(
                model.fs.unit.inlet.flow_mass_comp[0, j] -
                model.fs.unit.treated.flow_mass_comp[0, j] -
                model.fs.unit.byproduct.flow_mass_comp[0, j]))


class TestNFZO_w_default_removal:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.db = Database()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(
            default={"solute_list": ["sulfur", "toc", "tss", "foo"]})

        m.fs.unit = NanofiltrationZO(default={
            "property_package": m.fs.params,
            "database": m.db})

        m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(10000)
        m.fs.unit.inlet.flow_mass_comp[0, "sulfur"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "toc"].fix(2)
        m.fs.unit.inlet.flow_mass_comp[0, "tss"].fix(3)
        m.fs.unit.inlet.flow_mass_comp[0, "foo"].fix(4)

        return m

    @pytest.mark.unit
    def test_build(self, model):
        assert model.fs.unit.config.database == model.db

        assert isinstance(model.fs.unit.electricity, Var)
        assert isinstance(model.fs.unit.energy_electric_flow_vol_inlet, Var)

        assert isinstance(model.fs.unit.electricity_consumption, Constraint)

    @pytest.mark.component
    def test_load_parameters(self, model):
        data = model.db.get_unit_operation_parameters("nanofiltration")

        model.fs.unit.load_parameters_from_database(use_default_removal=True)

        assert model.fs.unit.recovery_frac_mass_H2O[0].fixed
        assert model.fs.unit.recovery_frac_mass_H2O[0].value == \
            data["recovery_frac_mass_H2O"]["value"]

        for (t, j), v in model.fs.unit.removal_frac_mass_solute.items():
            assert v.fixed
            if j == "foo":
                assert v.value == data["default_removal_frac_mass_solute"]["value"]
            else:
                assert v.value == data["removal_frac_mass_solute"][j]["value"]

        assert model.fs.unit.energy_electric_flow_vol_inlet.fixed
        assert model.fs.unit.energy_electric_flow_vol_inlet.value == data[
            "energy_electric_flow_vol_inlet"]["value"]

    @pytest.mark.component
    def test_degrees_of_freedom(self, model):
        assert degrees_of_freedom(model.fs.unit) == 0

    @pytest.mark.component
    def test_unit_consistency(self, model):
        assert_units_consistent(model.fs.unit)

    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert check_optimal_termination(results)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert (pytest.approx(8.50462, rel=1e-5) ==
                value(model.fs.unit.properties_treated[0].flow_vol))
        assert (pytest.approx(0.00352749, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["sulfur"]))
        assert (pytest.approx(0.0587916, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["toc"]))
        assert (pytest.approx(0.0105825, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["tss"]))
        assert (pytest.approx(0.470333, rel=1e-5) == value(
            model.fs.unit.properties_treated[0].conc_mass_comp["foo"]))

        assert (pytest.approx(1.50538, rel=1e-5) ==
                value(model.fs.unit.properties_byproduct[0].flow_vol))
        assert (pytest.approx(0.644356, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["sulfur"]))
        assert (pytest.approx(0.996426, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["toc"]))
        assert (pytest.approx(1.93306, rel=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["tss"]))
        assert (pytest.approx(0, abs=1e-5) == value(
            model.fs.unit.properties_byproduct[0].conc_mass_comp["foo"]))

        assert (pytest.approx(8336.75, rel=1e-5) ==
                value(model.fs.unit.electricity[0]))

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        for j in model.fs.params.component_list:
            assert 1e-5 >= abs(value(
                model.fs.unit.inlet.flow_mass_comp[0, j] -
                model.fs.unit.treated.flow_mass_comp[0, j] -
                model.fs.unit.byproduct.flow_mass_comp[0, j]))

    @pytest.mark.component
    def test_report(self, model):
        stream = StringIO()

        model.fs.unit.report(ostream=stream)

        output = """
====================================================================================
Unit : fs.unit                                                             Time: 0.0
------------------------------------------------------------------------------------
    Unit Performance

    Variables: 

    Key                     : Value   : Fixed : Bounds
         Electricity Demand :  8336.7 : False : (None, None)
      Electricity Intensity : 0.23134 :  True : (None, None)
       Solute Removal [foo] :  0.0000 :  True : (0, None)
    Solute Removal [sulfur] : 0.97000 :  True : (0, None)
       Solute Removal [toc] : 0.75000 :  True : (0, None)
       Solute Removal [tss] : 0.97000 :  True : (0, None)
             Water Recovery : 0.85000 :  True : (1e-08, 1.0000001)

------------------------------------------------------------------------------------
    Stream Table
                                Inlet    Treated  Byproduct
    Volumetric Flowrate         10.010    8.5046     1.5054
    Mass Concentration H2O      999.00    999.46     996.43
    Mass Concentration sulfur 0.099900 0.0035275    0.64436
    Mass Concentration toc     0.19980  0.058792    0.99643
    Mass Concentration tss     0.29970  0.010582     1.9331
    Mass Concentration foo     0.39960   0.47033 6.6428e-09
====================================================================================
"""

        assert output in stream.getvalue()
