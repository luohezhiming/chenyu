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

from pyomo.environ import (
    Block, Constraint, Expression, Var, Param, units as pyunits)
from idaes.core.util.exceptions import ConfigurationError
import proteuslib.flowsheets.full_treatment_train.example_flowsheets.financials as financials
from proteuslib.flowsheets.full_treatment_train.example_flowsheets.flowsheet_limited import *

def build_costing(m, module=financials, **kwargs):
    '''
    Add costing to a given flowsheet. This function will
        1) call the get_costing method for each unit model (note: unit model must have a get_costing method
        to be detected), and
        2) call get_system_costing which will tally up all capex and opex for each process
    m : model
    module : financials module
    '''

    # call get_costing for each unit model
    #get_costing_sweep(m.fs, module=financials)
    #TODO: add in other components as they become available

    # Nanofiltration
    if kwargs['NF_type'] == 'ZO':
        m.fs.NF.get_costing(module=module)
    elif kwargs['NF_type'] == 'Sep':
        raise NotImplementedError("get_costing is not implemented yet for the NF separator model.")
    # Reverse Osmosis
    if kwargs['RO_type'] == '0D':
        m.fs.RO.get_costing(module=module)
    elif kwargs['RO_type'] == 'Sep':
        raise NotImplementedError
    # Pump
    m.fs.pump_RO.get_costing(module=module, pump_type="High pressure")
    if kwargs['is_twostage']:
        m.fs.pump_RO2.get_costing(module=module, pump_type="High pressure")
        m.fs.RO2.get_costing(module=module)

    # call get_system_costing for whole flowsheet
    module.get_system_costing(m.fs)

#def get_costing_sweep(self, **kwargs):
    ## Initial attempt to do a general sweep across unit models and call get_costing
    # for b_unit in self.component_objects(Block, descend_into=True):
    #     # print(b_unit)
    #     if hasattr(b_unit, 'get_costing') and callable(b_unit.get_costing):
    #         name = getattr(b_unit, 'local_name')
    #         # if getattr(b_unit, '__class__') == 'idaes.core.process_block._ScalarPump':
    #         if isinstance(b_unit, PumpData):
    #             print(f"We got ourselves a pump called {name}!")
    #         else:
    #             print(f"We got ourselves a {name}!")
    #             # b_unit.get_costing(module=module)


def display_costing(m, **kwargs):
    #TODO: add to this
    print(f'LCOW = ${round(m.fs.costing.LCOW.value,3)}/m3')
    pump_RO_spec_opex= m.fs.pump_RO.costing.operating_cost.value/m.fs.annual_water_production.expr()
    print(f'RO Pump 1 specific Opex = ${round(pump_RO_spec_opex,3)}/m3')
    if kwargs['is_twostage']:
        pump_RO2_spec_opex= m.fs.pump_RO2.costing.operating_cost.value/m.fs.annual_water_production.expr()
        print(f'RO Pump 2 specific Opex = ${round(pump_RO2_spec_opex,3)}/m3')


if __name__ == "__main__":
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    kwargs_flowsheet= {'has_bypass': True,
                       'has_desal_feed': False,
                       'is_twostage': True,
                       'NF_type': 'ZO',
                       'NF_base': 'ion',
                       'RO_type': '0D',
                       'RO_base': 'TDS',
                       'RO_level': 'simple'
                       }
    m = solve_optimization(system_recovery=0.78, max_conc_factor=3, **kwargs_flowsheet)