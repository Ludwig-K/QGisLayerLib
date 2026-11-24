# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* initializes and returns the plugin

********************************************************************

* Date                 : November 2026
* Copyright            : (C) 2023 by Ludwig Kniprath
* Email                : ludwig at kni minus online dot de

********************************************************************

this program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

********************************************************************
"""
# Rev. 2026-11-19


from qgis._gui import QgisInterface
from .LayerLib import LayerLib


def classFactory(iface:QgisInterface)->LayerLib:
    """reimplemented function for initialization of the plugin

    Args:
        iface (QgisInterface): accessing running application

    Returns:
        LayerLib: Plugin-Instance
    """
    return LayerLib(iface)
