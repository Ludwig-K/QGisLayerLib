#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dialog to show datasources in maplayers of container-files (qlr/qgs/qgz)
* Depending on provider the datasource-attribute can be edited
* knowing, that there are much more settings in a maplayer

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

# Rev. 2026-11-19
import os

from pathlib import Path

from osgeo import gdal, ogr

from qgis.PyQt.QtCore import (
    Qt,
    QSignalBlocker,
)

from qgis.PyQt.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHBoxLayout,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QPlainTextEdit,
    QTabWidget,
)

from LayerLib.qt.MyQtWidgets import (
    FlashingBorderQLineEdit,
    FlashingQLabel,
    ClickableQLabel,
)


from qgis.PyQt.QtGui import QFont, QIcon


from LayerLib.tools.MyTools import (
    debug_print,
    #debug_print_dom_node,
    get_container_file_dom_doc,
    get_maplayer_node,
    get_valid_file,
    get_absolute_path,
    show_log_message,
    extract_map_layers,
    get_maplayer_node,
    save_container_file_dom_doc,
)

from LayerLib.tools.MyConstants import MY_DICT, ICON_DIR, CONTAINER_EXTENSIONS

from LayerLib import LayerLib

from qgis.core import QgsProject


class DataSourcesDialog(QDialog):
    """Dialog for QGis-Plugin LayerLib: dialog to show and edit Datasources inside container-file"""
    # Rev. 2026-11-21

    def __init__(self, layer_lib: LayerLib, parent: QWidget = None):
        """Constructor

        Args:
            layer_lib (LayerLib): Back-Refernce to Plugin
            parent (QWidget, optional): optional Qt-Parent-Element for Hierarchy. Defaults to None.
        """
        # Rev. 2026-11-21
        super().__init__(parent)

        self.layer_lib = layer_lib

        # Path to container-file, see enable_update
        self.container_path = None

        # QGis-Layer-ID of selected maplayer in container-file
        self.ed_maplayer_id = None

        # provider of selected maplayer
        self.ed_provider = None

        # data-source-parts (datasource splitted by |) selected maplayer
        # datasource may contain more than the path, f.e. "|layername=unternehmensbereiche_gewsser" or filter expression, seperated by pipe '|' or database-crentials or...
        # self.ed_datasource_parts[0] initially original path
        self.ed_datasource_parts = []

        # absolute path inside (some) datasources
        self.ed_datasource_path_abs = None

        self.resize(800, 400)

        self.setWindowTitle(MY_DICT.tr("DataSourcesDialog_title"))
        self.setObjectName("LayerLibDataSourcesDialog")

        self.setLayout(QVBoxLayout())

        header_qlbl = QLabel(MY_DICT.tr("DataSourcesDialog_header"))
        my_font = header_qlbl.font()
        my_font.setPointSize(10)
        my_font.setWeight(QFont.Weight.Bold)
        header_qlbl.setFont(my_font)
        self.layout().addWidget(header_qlbl)

        sub_wdg = QWidget(self)
        sub_wdg.setLayout(QHBoxLayout())

        sub_wdg.layout().addWidget(QLabel(MY_DICT.tr("container_file_path_txt")))
        self.file_path_fqle = FlashingBorderQLineEdit(self)
        self.file_path_fqle.setReadOnly(True)
        sub_wdg.layout().addWidget(self.file_path_fqle)

        self.select_container_file_qpb = QPushButton(
            QIcon(f"{ICON_DIR}/mActionFileOpen.svg"),
            "",
        )
        # else will be triggered by any enter on the dialog
        self.select_container_file_qpb.setAutoDefault(False)
        sub_wdg.layout().addWidget(self.select_container_file_qpb)

        self.select_container_file_qpb.pressed.connect(self.st_select_container_file)
        self.layout().addWidget(sub_wdg)


        self.content_qtw = QTabWidget(self)

        # two tabs: Overview and Details
        ov_tab_wdg = QWidget()
        ov_tab_wdg.setLayout(QVBoxLayout())


        self.maplayer_qtw = QTableWidget(self)

        #self.maplayer_qtw.itemSelectionChanged.connect(self.st_item_selection_changed)

        self.maplayer_qtw.setToolTip(MY_DICT.tr("maplayer_qtw_ttp"))
        self.maplayer_qtw.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.maplayer_qtw.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.maplayer_qtw.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.maplayer_qtw.setColumnCount(7)
        self.maplayer_qtw.setHorizontalHeaderLabels(
            ["Layer-ID", "Layer-Name", "Layer-Type", "Provider", "Path", "Sub-Layer", "Datasource"]
        )

        self.maplayer_qtw.horizontalHeader().setStretchLastSection(True)

        ov_tab_wdg.layout().addWidget(self.maplayer_qtw)

        sub_wdg = QWidget(self)
        sub_wdg.setLayout(QHBoxLayout())
        sub_wdg.layout().setAlignment(Qt.AlignmentFlag.AlignLeft)

        sub_wdg.layout().addWidget(
            QLabel(MY_DICT.tr("store_file_path_mode_qcb"))
        )

        self.store_file_path_mode_qcb = QComboBox(self)
        self.store_file_path_mode_qcb.setFixedWidth(100)
        self.store_file_path_mode_qcb.addItems(["Absolute", "Relative"])

        self.store_file_path_mode_qcb.currentIndexChanged.connect(
            self.apply_store_file_path_mode
        )
        sub_wdg.layout().addWidget(self.store_file_path_mode_qcb)

        ov_tab_wdg.layout().addWidget(sub_wdg)

        self.update_container_file_qpb = QPushButton(
            MY_DICT.tr("update_container_file_qpb_txt"), self
        )
        # else will be triggered by any enter on the dialog
        self.update_container_file_qpb.setAutoDefault(False)

        # Return or Enter key is pressed
        self.update_container_file_qpb.pressed.connect(self.update_container_file)
        ov_tab_wdg.layout().addWidget(self.update_container_file_qpb)


        self.content_qtw.addTab(ov_tab_wdg,QIcon(f"{ICON_DIR}/mActionOpenTable.svg"),'Overview')

        # Form-Tab for edit single selected datasource
        ed_tab_wdg = QWidget()
        ed_tab_wdg.setLayout(QGridLayout())


        row = 0
        ed_tab_wdg.layout().addWidget(
            QLabel(MY_DICT.tr("ed_layer_id_qlbl_txt")), row, 0
        )
        self.ed_layer_id_qlbl = QLabel(self)
        self.ed_layer_id_qlbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ed_tab_wdg.layout().addWidget(self.ed_layer_id_qlbl,row,1)

        row += 1
        ed_tab_wdg.layout().addWidget(
            QLabel(MY_DICT.tr("ed_layer_provider_qlbl_txt")), row, 0
        )
        self.ed_layer_provider_qlbl = QLabel(self)
        ed_tab_wdg.layout().addWidget(self.ed_layer_provider_qlbl,row,1)

        row += 1
        ed_tab_wdg.layout().addWidget(
            QLabel(MY_DICT.tr("ed_layer_name_qle_txt")), row, 0
        )
        self.ed_layer_name_qle = QLineEdit(self)
        ed_tab_wdg.layout().addWidget(self.ed_layer_name_qle,row,1)

        row += 1
        self.ed_datasource_path_qlbl = QLabel(MY_DICT.tr("ed_datasource_path_qlbl_txt"))
        ed_tab_wdg.layout().addWidget(self.ed_datasource_path_qlbl, row, 0)
        self.ed_datasource_path_qle = QLineEdit(self)
        self.ed_datasource_path_qle.setReadOnly(True)
        ed_tab_wdg.layout().addWidget(self.ed_datasource_path_qle, row, 1)
        self.ed_select_file_path_qpb = QPushButton(
            QIcon(f"{ICON_DIR}/mActionFileOpen.svg"),
            "",
        )
        # else will be triggered by any enter on the dialog
        self.ed_select_file_path_qpb.setAutoDefault(False)
        ed_tab_wdg.layout().addWidget(self.ed_select_file_path_qpb, row, 2)
        self.ed_select_file_path_qpb.pressed.connect(self.st_select_datasource_path)

        # optional, only if called with specified sub-layer from inspect-area, f.e. gpkg-file
        row += 1
        self.ed_sub_layer_qlbl = QLabel(MY_DICT.tr("ed_sub_layer_qlbl_txt"))
        ed_tab_wdg.layout().addWidget(self.ed_sub_layer_qlbl, row, 0)
        self.ed_sub_layer_qlbl_2 = FlashingQLabel(self)
        self.ed_sub_layer_qlbl_2.setToolTip(MY_DICT.tr("ed_sub_layer_qlbl_2_ttp"))
        ed_tab_wdg.layout().addWidget(self.ed_sub_layer_qlbl_2, row, 1)

        # optional Sub-Layer-Part
        row += 1
        self.ed_sub_layer_qlwdg_qlbl = QLabel(MY_DICT.tr("ed_sub_layer_qlwdg_qlbl_txt"))
        ed_tab_wdg.layout().addWidget(self.ed_sub_layer_qlwdg_qlbl, row, 0)
        self.ed_sub_layer_qlwdg = QListWidget(self)
        self.ed_sub_layer_qlwdg.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        ed_tab_wdg.layout().addWidget(self.ed_sub_layer_qlwdg, row, 1)
        self.ed_sub_layer_qlwdg.itemSelectionChanged.connect(
            self.st_select_sub_layer
        )

        row += 1
        ed_tab_wdg.layout().addWidget(
            QLabel(MY_DICT.tr("ed_datasource_qpte_txt")), row, 0
        )
        self.ed_datasource_qpte = QPlainTextEdit(self)
        ed_tab_wdg.layout().addWidget(self.ed_datasource_qpte,row,1)

        # optional QPlainTextEdit for queries of virtual layers (without edit-possibilities)
        row += 1
        self.ed_virtual_query_qlbl = QLabel(MY_DICT.tr("ed_virtual_query_qlbl_txt"))
        ed_tab_wdg.layout().addWidget(
            self.ed_virtual_query_qlbl, row, 0
        )
        self.ed_virtual_query_qpte = QPlainTextEdit(self)
        ed_tab_wdg.layout().addWidget(self.ed_virtual_query_qpte,row,1)

        row += 1
        self.ed_update_datasource_qpb = QPushButton(
            MY_DICT.tr("ed_update_datasource_qpb_txt"), self
        )
        # else will be triggered by any enter on the dialog
        self.ed_update_datasource_qpb.setAutoDefault(False)
        self.ed_update_datasource_qpb.pressed.connect(self.st_update_datasource)
        ed_tab_wdg.layout().addWidget(self.ed_update_datasource_qpb,row,0,1,2)

        self.content_qtw.addTab(ed_tab_wdg,QIcon(f"{ICON_DIR}/mActionToggleEditing.svg"), 'Details')

        self.layout().addWidget(self.content_qtw)
        self.log_message_fqlbl = FlashingQLabel()
        self.layout().addWidget(self.log_message_fqlbl)
        self.dlg_reset_all()


    def st_item_selection_changed(self):
        """Selection changed in maplayer_qtw => open details-Tab
        not connected, because of ClickableQLabel (pencil-icon) in column 6 with connected lambda
        """
        # Rev. 2026-11-19
        for qtw_item in self.maplayer_qtw.selectedItems():
            maplayer_id = qtw_item.data(Qt.ItemDataRole.DisplayRole)
            if maplayer_id:
                self.st_edit_datasource(maplayer_id)
                break


    def apply_store_file_path_mode(self, current_index: int):
        """triggered from QComboBox store_file_path_mode_qcb (relative/absolute)
        Changes all paths in file-based datasources

        Args:
            current_index (int): Index of selected option, 0 => abolute, 1 => relative
        """
        # Rev. 2026-11-19
        new_datasource_paths = {}
        skipped_layer_ids = []

        extracted_map_layers = extract_map_layers(
            self.dom_doc, self.container_path
        )

        # identify file-based with valid paths:
        for maplayer_id, map_layer in extracted_map_layers.items():
            if map_layer.provider in ["ogr", "gdal"]:
                if map_layer.file_exists:
                    if current_index == 0:
                        new_datasource_paths[maplayer_id] = map_layer.abs_path
                    else:
                        if map_layer.rel_path:
                            new_datasource_paths[maplayer_id] = map_layer.rel_path
                        else:
                            skipped_layer_ids.append(maplayer_id)
                else:
                    skipped_layer_ids.append(maplayer_id)


        file_suffix = str.lower(Path(self.container_path).suffix.lstrip("."))

        # alter Project-Settings (no project-settings in qlr-files)
        if file_suffix in ["qgs", "qgz"]:
            properties_node = self.dom_doc.documentElement().namedItem(
                "properties"
            )
            if not properties_node.isNull():
                paths_node = properties_node.namedItem("Paths")
                if not paths_node.isNull():
                    absolute_node = paths_node.namedItem("Absolute")
                    if not absolute_node.isNull():
                        if current_index == 0:
                            node_value = "true"
                        else:
                            node_value = "false"

                        absolute_node.firstChild().setNodeValue(node_value)

        # second run with above identified file-based and valid datasources
        if new_datasource_paths:
            for maplayer_id,new_data_source_path in new_datasource_paths.items():
                maplayer_node = get_maplayer_node(self.dom_doc, maplayer_id)
                datasource = (
                    maplayer_node.namedItem("datasource")
                    .firstChild()
                    .toText()
                    .data()
                )
                # only replace the path and keep other params
                datasource_parts = datasource.split("|")
                datasource_parts[0] = new_data_source_path

                new_datasource_path = "|".join(datasource_parts)
                maplayer_node.namedItem(
                    "datasource"
                ).firstChild().toText().setData(new_datasource_path)

            if skipped_layer_ids:
                show_log_message("INFO",f"{len(new_datasource_paths)} paths altered, {len(skipped_layer_ids)} layers with invalid paths skipped",self.log_message_fqlbl,True)
            else:
                show_log_message("SUCCESS",f"{len(new_datasource_paths)} paths altered",self.log_message_fqlbl,True)

            self.dlg_refresh_maplayer_qtw()
        else:
            show_log_message("INFO","No datasources affected...",self.log_message_fqlbl,True)




    def enable_update(self, container_path: str, maplayer_id: str = None):
        """show metada of container-file for info/edit

        Args:
            container_path (str): path to container-file
            maplayer_id (str): ID of layer inside container-file, used for pre-selection only
        """
        # Rev. 2026-11-19
        self.dlg_reset_all()

        if isinstance(container_path, str) and os.path.isfile(container_path):

            file_path_posix = Path(container_path)
            file_suffix = str.lower(file_path_posix.suffix.lstrip("."))

            if file_suffix in CONTAINER_EXTENSIONS:

                try:
                    self.dom_doc = get_container_file_dom_doc(container_path)
                    self.container_path = container_path
                    self.file_path_fqle.setText(container_path)

                    # default: relative paths
                    store_file_paths_absolute = False
                    if file_suffix in ["qgs", "qgz"]:
                        # regard path absolute/relativ-settings in QGis-Projects
                        properties_node = self.dom_doc.documentElement().namedItem(
                            "properties"
                        )
                        if not properties_node.isNull():
                            paths_node = properties_node.namedItem("Paths")
                            if not paths_node.isNull():
                                absolute_node = paths_node.namedItem("Absolute")
                                if not absolute_node.isNull():
                                    store_file_paths_absolute = (
                                        absolute_node.firstChild().toText().data()
                                        == "true"
                                    )

                        self.store_file_path_mode_qcb.setToolTip(
                            MY_DICT.tr("store_absolute_qcb_ttp")
                        )
                    else:
                        # if exported from project, the paths are stored absolute or relative dependend on project-settings
                        # but in qlr-file project-settings itself are not stored
                        # by test evaluated: each maplayer can be stored absolute or relative to qlr, both variants are supported on restore (if paths are valid, else layer in legend with exclamation-icon to show invalid path "Repair data-source"...)

                        self.store_file_path_mode_qcb.setToolTip(
                            MY_DICT.tr("store_absolute_qcb_qlr_ttp")
                        )

                    with QSignalBlocker(self.store_file_path_mode_qcb):
                        if store_file_paths_absolute:
                            self.store_file_path_mode_qcb.setCurrentIndex(0)
                        else:
                            self.store_file_path_mode_qcb.setCurrentIndex(1)

                    self.dlg_refresh_maplayer_qtw()

                    # pre-selection of maplayer in container-file
                    if maplayer_id:
                        self.st_edit_datasource(maplayer_id)
                        self.dlg_select_maplayer_row(maplayer_id)

                except Exception as e:
                    show_log_message(
                        "WARNING",
                        MY_DICT.tr("error_parsing_container_file", container_path, e),
                        self.log_message_fqlbl,
                        True,
                    )
            else:
                self.file_path_fqle.start_flash()
                show_log_message(
                    "WARNING",
                    MY_DICT.tr("file_suffix_not_supported", file_suffix),
                    self.log_message_fqlbl,
                    True,
                )
        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("container_file_not_found", container_path),
                self.log_message_fqlbl,
                True,
            )

    def dlg_refresh_maplayer_qtw(self):
        """refresh maplayer_qtw with current state of self.dom_doc"""
        # Rev. 2026-11-19
        self.maplayer_qtw.clearContents()
        extracted_map_layers = extract_map_layers(
            self.dom_doc, self.container_path
        )

        self.maplayer_qtw.setRowCount(len(extracted_map_layers))
        rc = 0
        for maplayer_id, map_layer in extracted_map_layers.items():


            self.maplayer_qtw.setItem(
                rc, 0, QTableWidgetItem(maplayer_id)
            )
            self.maplayer_qtw.setItem(
                rc, 1, QTableWidgetItem(map_layer.layername)
            )
            self.maplayer_qtw.setItem(
                rc, 2, QTableWidgetItem(map_layer.layer_type)
            )
            self.maplayer_qtw.setItem(
                rc, 3, QTableWidgetItem(map_layer.provider)
            )

            if map_layer.provider in ["ogr", "gdal"]:
                cw_4 = ClickableQLabel(
                    map_layer.datasource_path
                )
                if map_layer.file_exists:
                    cw_4.add_icon(
                        f"{ICON_DIR}/check-bold.svg", tool_tip="Path found"
                    )
                else:
                    cw_4.add_icon(
                        f"{ICON_DIR}/mIconWarning.svg", tool_tip="Path not found"
                    )


                self.maplayer_qtw.setCellWidget(rc, 4, cw_4)

                if map_layer.sub_layer_name:
                    cw_5 = ClickableQLabel(map_layer.sub_layer_name)
                    if map_layer.sub_layer_found:
                        cw_5.add_icon(
                            f"{ICON_DIR}/check-bold.svg", tool_tip="Sub-Layer found"
                        )
                    else:
                        cw_5.add_icon(
                            f"{ICON_DIR}/mIconWarning.svg",
                            tool_tip="Sub-Layer not found",
                        )


                    self.maplayer_qtw.setCellWidget(rc, 5, cw_5)

            cw_6 = ClickableQLabel(map_layer.datasource)
            cw_6.add_icon(
                f"{ICON_DIR}/mActionToggleEditing.svg",
                tool_tip="Click to show/edit datasource",
                cursor=Qt.CursorShape.PointingHandCursor,
            )

            cw_6.pressed.connect(lambda maplayer_id=maplayer_id:self.st_edit_datasource(maplayer_id) )

            self.maplayer_qtw.setCellWidget(rc, 6, cw_6)

            self.maplayer_qtw.setRowHeight(rc,40)

            rc += 1




    def dlg_select_maplayer_row(self,maplayer_id:str):
        """select specified row in self.maplayer_qtw

        Args:
            maplayer_id (str): Maplayer-ID to be selected
        """
        # Rev. 2026-11-19
        with QSignalBlocker(self.maplayer_qtw.selectionModel()):
            self.maplayer_qtw.selectionModel().clearSelection()
            for rc in range(self.maplayer_qtw.rowCount()):
                col_0_item = self.maplayer_qtw.item(rc,0)

                if col_0_item.data(Qt.ItemDataRole.DisplayRole) == maplayer_id:
                    self.maplayer_qtw.selectRow(rc)
                    break




    def st_edit_datasource(self, maplayer_id:str):
        """select one of the listed Maplayers for edit

        Args:
            maplayer_id (str): Maplayer-ID
        """
        # Rev. 2026-11-19
        self.dlg_reset_edit_tab()

        self.ed_layer_id_qlbl.setText(maplayer_id)

        extracted_map_layers = extract_map_layers(
            self.dom_doc, self.container_path
        )

        maplayer_node = get_maplayer_node(self.dom_doc, maplayer_id)

        if maplayer_node and maplayer_id in extracted_map_layers:
            self.ed_maplayer_id = maplayer_id
            self.content_qtw.setCurrentIndex(1)

            # force to lowercase, because sometimes "WFS" instead of "wfs"
            self.ed_provider = maplayer_node.namedItem("provider").firstChild().toText().data().lower()
            self.ed_layer_provider_qlbl.setText(self.ed_provider)


            layername = (
                maplayer_node.namedItem("layername").firstChild().toText().data()
            )

            self.ed_layer_name_qle.setText(layername)

            datasource = (
                maplayer_node.namedItem("datasource").firstChild().toText().data()
            )
            self.ed_datasource_qpte.setPlainText(datasource)

            self.ed_datasource_parts = datasource.split("|")


            if self.ed_provider in ['ogr','gdal']:
                self.ed_datasource_path_qlbl.setVisible(True)
                self.ed_datasource_path_qle.setVisible(True)
                self.ed_select_file_path_qpb.setVisible(True)

                datasource_path = self.ed_datasource_parts[0]
                self.ed_datasource_path_qle.setText(datasource_path)

                self.ed_datasource_path_abs = get_absolute_path(
                    datasource_path, self.container_path
                )

                # additional parameters, espacially sublayer in ogr
                if len(self.ed_datasource_parts) > 1:
                    for datasource_part in self.ed_datasource_parts[1:]:
                        if "layername=" in datasource_part:
                            self.ed_sub_layer_qlbl.setVisible(True)
                            self.ed_sub_layer_qlbl_2.setVisible(True)
                            self.ed_sub_layer_qlwdg_qlbl.setVisible(True)
                            self.ed_sub_layer_qlwdg.setVisible(True)
                            self.ed_sub_layer_name = datasource_part.replace("layername=", "")
                            self.ed_sub_layer_qlbl_2.setText(self.ed_sub_layer_name)
                            if self.ed_datasource_path_abs:
                                self.dlg_refresh_sub_layer_qle()

            elif self.ed_provider in ['virtual']:
                self.ed_virtual_query_qlbl.setVisible(True)
                self.ed_virtual_query_qpte.setVisible(True)
                self.ed_virtual_query_qpte.setPlainText(extracted_map_layers[maplayer_id].virtual_query)



    def dlg_reset_all(self):
        """clear/reset complete dialog"""
        # Rev. 2026-11-19
        self.content_qtw.setCurrentIndex(0)
        self.dom_doc = None
        self.container_path = None


        self.file_path_fqle.clear()
        # clear all but headers
        self.maplayer_qtw.clearContents()

        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")


        self.dlg_reset_edit_tab()

    def dlg_reset_edit_tab(self):
        """clear/reset edit-part of dialog
        """
        # Rev. 2026-11-19
        self.ed_maplayer_id = None
        self.ed_provider = None
        self.ed_datasource_path_abs = None

        self.ed_layer_id_qlbl.clear()
        self.ed_layer_name_qle.clear()
        self.ed_datasource_qpte.clear()
        self.ed_datasource_path_qle.clear()
        self.ed_sub_layer_qlbl_2.clear()
        self.ed_sub_layer_qlwdg.clear()

        self.ed_datasource_path_qlbl.setVisible(False)
        self.ed_datasource_path_qle.setVisible(False)
        self.ed_select_file_path_qpb.setVisible(False)
        self.ed_sub_layer_qlbl.setVisible(False)
        self.ed_sub_layer_qlbl_2.setVisible(False)
        self.ed_sub_layer_qlwdg_qlbl.setVisible(False)
        self.ed_sub_layer_qlwdg.setVisible(False)

        self.ed_virtual_query_qlbl.setVisible(False)
        self.ed_virtual_query_qpte.setVisible(False)

        # only some layers allow direct editing of datasource (wms, virtual)
        # ogr/gdal are edited by selecting file (and sometimes ogr-sublayer)
        # self.ed_datasource_qpte.setReadOnly(True)
        # self.ed_update_datasource_qpb.setEnabled(False)

        self.ed_sub_layer_qlwdg.setToolTip(MY_DICT.tr("ed_sub_layer_qlwdg_no_sublayers_ttp"))


    def update_container_file(self):
        """parse user-inputs, change this datasource in container-file and save"""
        # Rev. 2026-11-19
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

        # prevent saving/overwriting the project-file which is just running
        if (
            Path(QgsProject.instance().absoluteFilePath()).as_posix()
            != Path(self.container_path).as_posix()
        ):
            # security check before replacement
            dialog_result = QMessageBox.question(
                None,
                MY_DICT.tr("dlg_confirm_update_container_file_title"),
                MY_DICT.tr(
                    "dlg_confirm_update_container_file_text",
                ),
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                defaultButton=QMessageBox.StandardButton.Yes,
            )

            if dialog_result == QMessageBox.StandardButton.Yes:
                if save_container_file_dom_doc(self.container_path, self.dom_doc):
                    show_log_message(
                        "SUCCESS",
                        MY_DICT.tr(
                            "EditDataSourcePath_dom_doc_saved_success", self.container_path
                        ),
                        self.log_message_fqlbl,
                        True,
                    )
                else:
                    show_log_message(
                        "WARNING",
                        MY_DICT.tr(
                            "EditDataSourcePath_dom_doc_saved_error",
                            self.container_path,
                        ),
                        self.log_message_fqlbl,
                        True,
                    )
        else:
            show_log_message(
                "CRITICAL",
                "Altering currently loaded project is not allowed...",
                self.log_message_fqlbl,
                True,
            )

    def st_select_container_file(self):
        """select another container-file from within dialog
        """
        # Rev. 2026-11-19
        filter = f"QGis-Container-File (*.qgz *.qgs *.qlr)"
        default_dir = get_valid_file(
            [
                self.file_path_fqle.text(),
                self.layer_lib.last_user_file,
            ],
            self.layer_lib.treeview_source_path
        )

        # getSaveFileName ohne "Confirm Overwrite" bei bereits vorhandener Datei
        selected_container_file_path, filter = QFileDialog.getOpenFileName(
            None,
            MY_DICT.tr("dlg_select_container_file_title"),
            default_dir,
            filter=filter,
        )

        if selected_container_file_path and os.path.isfile(selected_container_file_path):
            selected_container_file_path_posix = Path(selected_container_file_path)
            selected_container_file_path_suffix = str.lower(selected_container_file_path_posix.suffix.lstrip("."))
            if selected_container_file_path_suffix in CONTAINER_EXTENSIONS:
                self.enable_update(selected_container_file_path)




    def st_select_datasource_path(self):
        """open file-dialog to chose another file for this map-layer"""
        # Rev. 2026-11-19

        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

        self.ed_datasource_path_abs = None

        if self.ed_datasource_path_qle.text():
            old_datasource_path_posix = Path(self.ed_datasource_path_qle.text())
            old_datasource_file_name = old_datasource_path_posix.name
            old_datasource_suffix = str.lower(old_datasource_path_posix.suffix.lstrip("."))

            default_dir = get_valid_file(
                [
                    self.ed_datasource_path_qle.text(),
                    self.container_path,
                    self.layer_lib.last_user_file
                ],
                self.container_path
            )

            filter = f"File-Type *.{old_datasource_suffix} (*.{old_datasource_suffix})"

            # getSaveFileName ohne "Confirm Overwrite" bei bereits vorhandener Datei
            new_datasource_path, filter = QFileDialog.getOpenFileName(
                None,
                MY_DICT.tr("dlg_replace_data_source_file_title", old_datasource_file_name),
                default_dir,
                filter=filter,
            )

            if new_datasource_path and os.path.isfile(new_datasource_path):
                new_datasource_path_posix = Path(new_datasource_path)
                new_datasource_suffix = str.lower(new_datasource_path_posix.suffix.lstrip("."))
                self.layer_lib.last_user_file = new_datasource_path_posix.as_posix()


                if self.ed_provider == 'gdal':
                    if new_datasource_suffix in self.layer_lib.raster_extensions:
                        self.ed_datasource_path_abs = new_datasource_path
                        self.ed_datasource_parts[0] = new_datasource_path
                        self.ed_datasource_path_qle.setText(new_datasource_path)
                        self.dlg_refresh_datasource_qpte()
                    else:
                        show_log_message("WARNING",f"Selected file with extension '{new_datasource_suffix}' not suitable for raster-layer...",self.log_message_fqlbl,True)
                elif self.ed_provider == 'ogr':
                    if new_datasource_suffix in self.layer_lib.vector_extensions:

                        self.ed_datasource_path_abs = new_datasource_path
                        self.ed_datasource_parts[0] = new_datasource_path
                        self.ed_datasource_path_qle.setText(new_datasource_path)

                        self.dlg_refresh_datasource_qpte()
                        self.dlg_refresh_sub_layer_qle()

                    else:
                        show_log_message("WARNING",f"Selected file with extension '{new_datasource_suffix}' not suitable for vector-layer...",self.log_message_fqlbl,True)
                else:
                    show_log_message("WARNING",f"Provider '{self.ed_provider}' not implemented for file-based datasources (gdal/ogr)...",self.log_message_fqlbl,True)


    def dlg_refresh_sub_layer_qle(self):
        """refresh list of sublayers in ogr-vector-file
        """
        # Rev. 2026-11-19

        self.ed_sub_layer_qlwdg.clear()


        if self.ed_datasource_path_abs:
            try:
                sub_layer_found = False
                with ogr.Open(
                    self.ed_datasource_path_abs, gdal.GA_ReadOnly
                ) as ds:
                    for sub_layer in ds:
                        qlwi = QListWidgetItem()
                        qlwi.setData(
                            Qt.ItemDataRole.DisplayRole,
                            sub_layer.GetName(),
                        )
                        qlwi.setData(
                            Qt.ItemDataRole.UserRole,
                            sub_layer.GetName(),
                        )

                        self.ed_sub_layer_qlwdg.addItem(qlwi)

                        # select current assigned sub-layer
                        if sub_layer.GetName() == self.ed_sub_layer_name:
                            self.ed_sub_layer_qlwdg.setCurrentItem(qlwi)
                            sub_layer_found = True

                    if self.ed_sub_layer_name and not sub_layer_found:
                        show_log_message("WARNING",f"Sub-Layer '{self.ed_sub_layer_name}' not found in '{Path(self.ed_datasource_path_abs).name}'...",self.log_message_fqlbl,True)
                        self.ed_sub_layer_qlbl_2.start_flash()


            except Exception as e:
                show_log_message("WARNING",f"ogr.Open-Exception: {e}",self.log_message_fqlbl,True)

            if self.ed_sub_layer_qlwdg.model().rowCount():
                self.ed_sub_layer_qlwdg.setToolTip(MY_DICT.tr("ed_sub_layer_qlwdg_ttp"))
            else:
                self.ed_sub_layer_qlwdg.setToolTip(MY_DICT.tr("ed_sub_layer_qlwdg_no_sublayers_ttp"))



    def st_update_datasource(self):
        """update edited data-source in self.dom_doc -> maplayer_node
        not written to file
        """
        # Rev. 2026-11-19
        maplayer_node = get_maplayer_node(self.dom_doc, self.ed_maplayer_id)
        if maplayer_node:
            new_layername = self.ed_layer_name_qle.text()

            if not new_layername:
                new_layername = (
                    maplayer_node.namedItem("layername").firstChild().toText().data()
                )
                show_log_message("INFO",f"Missing Layer-Name, keep '{new_layername}'",self.log_message_fqlbl,True)

            # no further checks, take contents from ed_datasource_qpte, save to maplayer_node and refresh maplayer-list (parsing and validating the altered datasource)
            new_datasource = self.ed_datasource_qpte.toPlainText()
            maplayer_node.namedItem("layername").firstChild().setNodeValue(new_layername)
            maplayer_node.namedItem("datasource").firstChild().setNodeValue(new_datasource)
            self.dlg_refresh_maplayer_qtw()
            self.content_qtw.setCurrentIndex(0)

    def st_select_sub_layer(self):
        """triggered by itemSelectionChanged in ed_sub_layer_qlwdg
        specify sub-layer in ed_datasource_parts and write generated datasource to ed_datasource_qpte
        """
        # Rev. 2026-11-19
        for item in self.ed_sub_layer_qlwdg.selectedItems():
            sub_layer_name = item.text()
            part_found = False
            for part_idx,datasource_part in enumerate(self.ed_datasource_parts):
                if "layername=" in datasource_part:
                    self.ed_datasource_parts[part_idx] = f"layername={sub_layer_name}"
                    part_found = True
                    break

            if not part_found:
                self.ed_datasource_parts.append(f"layername={sub_layer_name}")

            self.dlg_refresh_datasource_qpte()
            self.ed_sub_layer_qlbl_2.setText(sub_layer_name)

    def dlg_refresh_datasource_qpte(self):
        """refreshes ed_datasource_qpte with altered datasource by joining self.ed_datasource_parts
        """
        self.ed_datasource_qpte.clear()
        plain_text = '|'.join(self.ed_datasource_parts)
        self.ed_datasource_qpte.setPlainText(plain_text)

