#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dialog to select sub-layer(s) from container-file or vector-layer-file

********************************************************************

* Date                 : 2026-11
* Copyright            : (C) 2026 by Ludwig Kniprath
* Email                : ludwig at kni-online dot de

********************************************************************

this program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

********************************************************************
"""

# Rev. 2026-11-21
from pathlib import Path

from osgeo import gdal, ogr

from qgis.PyQt.QtCore import Qt

from qgis.PyQt.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QListWidgetItem

)

from LayerLib.qt.MyQtWidgets import FlashingQLabel,MyQLWi


from qgis.PyQt.QtGui import QFont



from LayerLib.tools.MyConstants import MY_DICT,CONTAINER_EXTENSIONS

from LayerLib import LayerLib

from LayerLib.tools.MyTools import show_log_message,get_container_file_dom_doc


class SelectSubLayerDialog(QDialog):
    """Dialog for QGis-Plugin LayerLib: dialog to select sub-layer(s) from container-file or vector-layer-file"""
    # Rev. 2026-11-21

    def __init__(self, layer_lib: LayerLib, parent: QWidget = None):
        """Constructor

        Args:
            layer_lib (LayerLib): Back-Reference to Plugin
            parent (QWidget, optional): optional Qt-Parent-Element for Hierarchy. Defaults to None.
        """
        # Rev. 2026-11-21
        super().__init__(parent)

        self.layer_lib = layer_lib

        self.resize(600, 300)

        self.setWindowTitle(MY_DICT.tr("SelectSubLayerDialog_title"))
        self.setObjectName("LayerLibSelectSubLayerDialog")


        self.setLayout(QVBoxLayout())

        self.header_qlbl = QLabel("")
        self.layout().addWidget(self.header_qlbl)

        # Sub-Layer-Selection-List, which is a listwidget with prepended checkboxes
        self.sublayer_select_qlw = MyQLWi(self)
        # quicky to select single option and close dialog
        self.sublayer_select_qlw.itemDoubleClicked.connect(self.item_double_clicked)
        self.layout().addWidget(self.sublayer_select_qlw)


        self.import_selected_layers_qpb = QPushButton("Import selected...", self)
        self.import_selected_layers_qpb.setAutoDefault(False)
        self.import_selected_layers_qpb.pressed.connect(self.import_selected_layers)
        self.layout().addWidget(self.import_selected_layers_qpb)

        self.import_all_layers_qpb = QPushButton("Import all...", self)
        self.import_all_layers_qpb.setAutoDefault(False)
        self.import_all_layers_qpb.pressed.connect(self.import_all_layers)
        self.layout().addWidget(self.import_all_layers_qpb)

        self.import_no_layers_qpb = QPushButton("Cancel", self)
        self.import_no_layers_qpb.setAutoDefault(False)
        self.import_no_layers_qpb.pressed.connect(self.import_no_layers)
        self.layout().addWidget(self.import_no_layers_qpb)

        self.log_message_fqlbl = FlashingQLabel()
        self.layout().addWidget(self.log_message_fqlbl)

        self.reset_dlg()

    def import_selected_layers(self):
        """click on self.import_selected_layers_qpb "Import selected..."
        returns 1 to the function wich executed dialog.exec()
        """
        # Rev. 2026-11-21
        self.done(1)


    def item_double_clicked(self,item:QListWidgetItem):
        """convenience: check checkbox by double-click on item and close dialog (with other items keeping their check-state)

        Args:
            item (QListWidgetItem)
        """
        # Rev. 2026-11-21
        item.setData(Qt.ItemDataRole.CheckStateRole,Qt.CheckState.Checked)
        self.done(1)

    def import_all_layers(self):
        """click on self.import_all_layers_qpb "Import all..."
        checks all items and closes dialog returning 1 to the function wich executed dialog.exec()
        """
        # Rev. 2026-11-21
        for row_nbr in range(self.sublayer_select_qlw.model().rowCount()):
            idx = self.sublayer_select_qlw.model().index(row_nbr,0)
            item = self.sublayer_select_qlw.itemFromIndex(idx)
            item.setData(Qt.ItemDataRole.CheckStateRole,Qt.CheckState.Checked)

        self.done(1)


    def import_no_layers(self):
        """Click on self.import_no_layers_qpb => "Cancel"
        Un-check all items and close dialog returning 0 to the function wich executed dialog.exec()
        """
        for row_nbr in range(self.sublayer_select_qlw.model().rowCount()):
            idx = self.sublayer_select_qlw.model().index(row_nbr,0)
            item = self.sublayer_select_qlw.itemFromIndex(idx)
            item.setData(Qt.ItemDataRole.CheckStateRole,Qt.CheckState.Unchecked)

        self.done(0)


    def feed_container_file(self,file_path_abs:str):
        """use-case 3 (replacing feed_map_layers)
        feed sublayer_select_qlw with map-layer-nodes from container-file

        Args:
            file_path_abs (str): path to container-file
        """
        self.reset_dlg()
        self.header_qlbl.setText(MY_DICT.tr("SelectSubLayerDialog_container_header",file_path_abs))

        file_path_posix = Path(file_path_abs)
        if file_path_posix.is_file():
            # remove leading point .shp => shp
            file_suffix = str.lower(file_path_posix.suffix.lstrip("."))
            if file_suffix in CONTAINER_EXTENSIONS:
                try:
                    dom_doc = get_container_file_dom_doc(file_path_posix.as_posix())
                    maplayer_nodes = dom_doc.elementsByTagName("maplayer")

                    for maplayer_node in (
                        maplayer_nodes.at(i) for i in range(maplayer_nodes.size())
                    ):
                        maplayer_id = maplayer_node.namedItem("id").firstChild().toText().data()
                        maplayer_name = (
                            maplayer_node.namedItem("layername").firstChild().toText().data()
                        )

                        # force to lowercase, because sometimes "WFS" instead of "wfs"
                        provider = (
                            maplayer_node.namedItem("provider")
                            .firstChild()
                            .toText()
                            .data()
                            .lower()
                        )

                        datasource = (
                            maplayer_node.namedItem("datasource")
                            .firstChild()
                            .toText()
                            .data()
                        )

                        ttp = f"Provider: {provider}\nDatasource: {datasource}"
                        qlwi = QListWidgetItem()
                        qlwi.setData(Qt.ItemDataRole.DisplayRole, maplayer_name)
                        qlwi.setData(Qt.ItemDataRole.ToolTipRole, ttp)
                        qlwi.setData(Qt.ItemDataRole.UserRole, maplayer_id)
                        # prepends checkbox to QListWidgetItem
                        qlwi.setCheckState(Qt.CheckState.Unchecked)
                        self.sublayer_select_qlw.addItem(qlwi)


                except Exception as e:
                    show_log_message(
                        "WARNING",
                        MY_DICT.tr("error_parsing_container_file", file_path_abs, e),
                        self.log_message_fqlbl,
                        True,
                    )



            else:
                show_log_message(
                    "WARNING",
                    MY_DICT.tr(
                        "file_suffix_not_supported",
                        file_suffix,
                    ),
                    self.log_message_fqlbl,
                    True,
                )


    def feed_map_layers(self,all_map_layers:dict):
        """use-case 1:
        feed sublayer_select_qlw with map-layer-nodes (from current project/dom-doc...)
        not used anymore, see feed_container_file

        Args:
            all_map_layers (dict): key: layerid, value: list [layername, maplayer-node]
        """
        # Rev. 2026-11-21
        self.reset_dlg()

        self.header_qlbl.setText(MY_DICT.tr("SelectSubLayerDialog_domdoc_header"))

        for layerid,layer_metas in all_map_layers.items():
            qlwi = QListWidgetItem()
            layername = layer_metas[0]
            maplayer_node = layer_metas[1]
            # force to lowercase, because sometimes "WFS" instead of "wfs"
            provider = (
                maplayer_node.namedItem("provider")
                .firstChild()
                .toText()
                .data()
                .lower()
            )

            datasource = (
                maplayer_node.namedItem("datasource")
                .firstChild()
                .toText()
                .data()
            )

            ttp = f"Provider: {provider}\nDatasource: {datasource}"

            qlwi.setData(Qt.ItemDataRole.DisplayRole, layername)
            qlwi.setData(Qt.ItemDataRole.ToolTipRole, ttp)
            qlwi.setData(Qt.ItemDataRole.UserRole, layerid)
            # prepends checkbox to QListWidgetItem
            qlwi.setCheckState(Qt.CheckState.Unchecked)
            self.sublayer_select_qlw.addItem(qlwi)

    def feed_vector_layer_file(self,file_path_abs:str):
        """use-case 2:
        feed sublayer_select_qlw with sub-layers from vector-layer-file, f.e. gpkg

        Args:
            file_path (str): path to vector-layer-file
        """
        # Rev. 2026-11-21
        self.reset_dlg()

        self.header_qlbl.setText(MY_DICT.tr("SelectSubLayerDialog_vector_header",file_path_abs))

        file_path_posix = Path(file_path_abs)
        if file_path_posix.is_file():
            # remove leading point .shp => shp
            file_suffix = str.lower(file_path_posix.suffix.lstrip("."))
            if file_suffix in self.layer_lib.vector_extensions:
                try:
                    with ogr.Open(file_path_posix.as_posix(), gdal.GA_ReadOnly) as ds:
                        for lyr in ds:
                            qlwi = QListWidgetItem()
                            qlwi.setData(Qt.ItemDataRole.DisplayRole, lyr.GetName())
                            # so wird aus dem QListWidgetItem eine Check-Box!
                            qlwi.setCheckState(Qt.CheckState.Unchecked)
                            self.sublayer_select_qlw.addItem(qlwi)

                except Exception as e:
                    show_log_message(
                        "WARNING",
                        MY_DICT.tr(
                            "error_opening_vector_file",
                            file_path_posix.as_posix(),
                            e,
                        ),self.log_message_fqlbl,True
                    )
            else:
                show_log_message(
                    "WARNING",
                    MY_DICT.tr(
                        "file_not_found",
                        file_path_posix.as_posix(),
                    ),self.log_message_fqlbl,True
                )



    def reset_dlg(self):
        """resets complete dialog:
        remove contents from form-widgets
        hide functional-buttons for update/insert/delete
        reset self.datasource_path
        """
        # Rev. 2026-11-21
        self.sublayer_select_qlw.clear()
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

