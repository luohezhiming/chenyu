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
This module contains a zero-order representation of a pump unit
operation.
"""

from idaes.core import declare_process_block_class

from watertap.core.zero_order_base import ZeroOrderBaseData
from watertap.core.zero_order_pt import build_pt
from watertap.core.zero_order_electricity import constant_intensity

# Some more inforation about this module
__author__ = "Andrew Lee"


@declare_process_block_class("PumpZO")
class PumpZOData(ZeroOrderBaseData):
    """
    Zero-Order model for a pump unit operation.
    """

    CONFIG = ZeroOrderBaseData.CONFIG()

    def build(self):
        super().build()

        self._tech_type = "pump"

        build_pt(self)
        constant_intensity(self)
