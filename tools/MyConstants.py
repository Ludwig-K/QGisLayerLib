#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Some constants used for multiple occasions

********************************************************************

* Date                 : 2026-08-19
* Copyright            : (C) 2026 by Ludwig Kniprath
* Email                : ludwig at kni-online dot de

********************************************************************

this program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

********************************************************************
"""
# Rev. 2026-11-23

import os

from pathlib import Path

from enum import IntEnum

from LayerLib.i18n.snip_dict import SnipDict


# QT_ROLES
# used for storing data in QStandardItemModel, f.e. MyQComboBox, QTreeView...
# RESOURCE_ID: used inside MyStandardItem, linked to layers-dictionary containing Metadata for stored layers
# FOLDER_ID: used inside MyStandardItem, linked to folders-dictionary containing Metadata for stored folder
# CUSTOM_SORT: used inside MyStandardItem, used for combined sorting auf layers and folders in QTreeView, default order: folders before layers, achieved by prepending "a_"/"z_" to DisplayRole-value
# EDITABLE: used inside MyStandardItem for toggle icons depending on tool_mode-setting, see dlg_show_tool_mode
# ENABLED: flag for valid layers
# STYLE: "folder" or "resource", used by LeftSideIconsDelegateFolderLayer
QT_ROLES = IntEnum(
    "QT_ROLES",
    ["RESOURCE_ID", "FOLDER_ID", "ENABLED", "CUSTOM_SORT","EDITABLE","STYLE"],
    start=257,
)

# path to icons used in dialog and QGis-GUI
ICON_DIR = Path(os.path.dirname(__file__)).parent / "icons"

# global variable, translations de_DE and en_US
MY_DICT = SnipDict()

# supported extensions for resource-files
# combined with gdal/ogr vector/raster-extensions
CONTAINER_EXTENSIONS = {
    "qlr": "maplayers",
    "qgs": "projectlayers",
    "qgz": "projectlayers",
}