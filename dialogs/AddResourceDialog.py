#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dialog to insert resource (container-file *.qlr/*.qgs/*.qgz) in treeview_dom_doc

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

from qgis.PyQt.QtCore import Qt, QTimer

from qgis.PyQt.QtXml import QDomNode


from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QWidget,
    QVBoxLayout,
    QFileDialog,
    QCheckBox,
    QTabWidget
)

from LayerLib.qt.MyQtWidgets import (
    FlashingBorderQLineEdit,
    MySubLayerTextBrowser,
    FlashingQLabel,
)

from pathlib import Path


from qgis.PyQt.QtGui import QFont, QDropEvent, QDragEnterEvent, QIcon

from qgis.PyQt.QtCore import Qt

from LayerLib.tools.MyTools import (
    #get_debug_trace,
    #debug_print,
    #debug_print_dom_node,
    insert_resource_node,
    save_treeview_dom_doc,
    get_absolute_path,
    get_relative_path,
    get_valid_file,
    show_log_message,
    parse_container_file
)

from LayerLib.tools.MyConstants import MY_DICT, ICON_DIR,CONTAINER_EXTENSIONS

from LayerLib import LayerLib

class AddResourceDialog(QDialog):
    """Dialog for QGis-Plugin LayerLib: dialog to add new resource to library"""
    # Rev. 2026-11-19

    def __init__(self, layer_lib:LayerLib, parent:QWidget=None):
        """_summary_

        Args:
            layer_lib (LayerLib): reference to plugin
            parent (QWidget, optional): optional Qt-Parent-Element for Hierarchy. Defaults to None.
        """

        # Rev. 2026-11-19
        super().__init__(parent)

        self.layer_lib = layer_lib

        self.resize(600, 600)

        # self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setWindowTitle(MY_DICT.tr("AddResourceDialog_title"))
        self.setObjectName("LayerLibAddResourceDialog")
        self.setLayout(QVBoxLayout())

        header_qlbl = QLabel(MY_DICT.tr("AddResourceDialog_header"))
        my_font = header_qlbl.font()
        my_font.setPointSize(10)
        my_font.setWeight(QFont.Weight.Bold)
        header_qlbl.setFont(my_font)
        self.layout().addWidget(header_qlbl)

        self.content_qtw = QTabWidget(self)

        form_tab_wdg = QWidget()
        form_tab_wdg.setLayout(QGridLayout())
        form_tab_wdg.layout().setContentsMargins(10, 10, 10, 10)

        row = 0
        form_tab_wdg.layout().addWidget(QLabel(MY_DICT.tr("resource_path_fqle")), row, 0)
        self.resource_path_fqle = FlashingBorderQLineEdit(self)
        self.resource_path_fqle.setToolTip(MY_DICT.tr("resource_path_fqle_ttp"))
        # self.resource_path_fqle.setReadOnly(True)
        form_tab_wdg.layout().addWidget(self.resource_path_fqle, row, 1)
        self.select_resource_path_qpb = QPushButton(
            QIcon(f"{ICON_DIR}/mActionFileOpen.svg"),
            "",
        )
        # else will be triggered by any enter on the dialog
        self.select_resource_path_qpb.setToolTip(MY_DICT.tr("select_resource_path_qpb_ttp"))
        self.select_resource_path_qpb.setAutoDefault(False)
        form_tab_wdg.layout().addWidget(self.select_resource_path_qpb, row, 2)
        self.select_resource_path_qpb.pressed.connect(self.st_select_resource_path)


        row += 1
        form_tab_wdg.layout().addWidget(QLabel(MY_DICT.tr("resource_label_fqle")), row, 0)
        self.resource_label_fqle = FlashingBorderQLineEdit(self)
        form_tab_wdg.layout().addWidget(self.resource_label_fqle, row, 1)

        row += 1
        form_tab_wdg.layout().addWidget(QLabel(MY_DICT.tr("resource_description_qpte")), row, 0)
        self.resource_description_qpte = QPlainTextEdit(self)
        self.resource_description_qpte.setMaximumHeight(160)
        form_tab_wdg.layout().addWidget(self.resource_description_qpte, row, 1)

        row += 1
        form_tab_wdg.layout().addWidget(QLabel(MY_DICT.tr("folder_qcbx")), row, 0)
        self.folder_qcbx = QComboBox(self)
        form_tab_wdg.layout().addWidget(self.folder_qcbx, row, 1)


        row += 1
        form_tab_wdg.layout().addWidget(QLabel(MY_DICT.tr("store_relative_to_treeview_txt")), row, 0)
        self.store_resource_path_relative_qcb = QCheckBox(self)
        self.store_resource_path_relative_qcb.setToolTip(
            MY_DICT.tr("store_relative_to_treeview_ttp")
        )
        self.store_resource_path_relative_qcb.setChecked(True)
        form_tab_wdg.layout().addWidget(self.store_resource_path_relative_qcb, row, 1)

        row += 1
        self.insert_resource_qpb = QPushButton(MY_DICT.tr("insert_resource_qpb"), self)
        self.insert_resource_qpb.setAutoDefault(False)
        self.insert_resource_qpb.pressed.connect(self.insert_resource)
        form_tab_wdg.layout().addWidget(self.insert_resource_qpb,row, 0,1,2)
        self.content_qtw.addTab(form_tab_wdg,'Data')



        inspect_tab_wdg = QWidget()
        inspect_tab_wdg.setLayout(QVBoxLayout())

        self.insert_layer_drop_area = MySubLayerTextBrowser(self.layer_lib, self)
        self.insert_layer_drop_area.anchorClicked.connect(
            self.layer_lib.tool_evaluate_storable_resource
        )
        self.insert_layer_drop_area.drag_enter.connect(
            self.st_eval_drag_enter_event
        )
        self.insert_layer_drop_area.drag_move.connect(
            self.st_eval_drag_move_event
        )
        self.insert_layer_drop_area.dropped.connect(self.st_eval_drop_event)
        self.insert_layer_drop_area.setToolTip(
            MY_DICT.tr("insert_layer_drop_area_ttp")
        )
        self.insert_layer_drop_area.setHtml(
            MY_DICT.tr("insert_layer_drop_area_ttp")
        )
        inspect_tab_wdg.layout().addWidget(self.insert_layer_drop_area)

        self.content_qtw.addTab(inspect_tab_wdg,'Inspect')

        self.layout().addWidget(self.content_qtw)

        self.log_message_fqlbl = FlashingQLabel()

        self.layout().addWidget(self.log_message_fqlbl)

        self.reset_dlg()

    def st_select_resource_path(self):
        """select the resource-file to be inserted as new resource"""
        # Rev. 2026-11-19
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

        self.layer_lib.parse_cache['AddResourceDialog'] = {}

        filter = f"QGis-Container-File (*.qgz *.qgs *.qlr)"
        default_dir = get_valid_file(
            [
                self.resource_path_fqle.text(),
                self.layer_lib.last_user_file
            ],
            self.layer_lib.treeview_source_path
        )

        # getSaveFileName ohne "Confirm Overwrite" bei bereits vorhandener Datei
        resource_path, filter = QFileDialog.getOpenFileName(
            None,
            MY_DICT.tr("dlg_select_new_layer_file_title"),
            default_dir,
            filter=filter,
        )

        if resource_path and os.path.isfile(resource_path):
            self.layer_lib.last_user_file = Path(resource_path).as_posix()
            parse_result = parse_container_file(resource_path,self.layer_lib,'AddResourceDialog',-1)
            self.insert_layer_drop_area.setHtml(parse_result.parse_html)
            if parse_result.parse_cache:
                self.layer_lib.parse_cache['AddResourceDialog'] = parse_result.parse_cache
                self.resource_path = resource_path
                self.resource_path_fqle.setText(resource_path)

                # convenience
                self.resource_label_fqle.setText(Path(resource_path).name)
            else:
                show_log_message(
                    "WARNING", MY_DICT.tr("no_layers_found_in_file", resource_path,self.log_message_fqlbl,True)
                )
                self.resource_path_fqle.start_flash()


    def st_eval_drag_enter_event(self, evt: QDragEnterEvent):
        """Part 1 of Drag&Drop: Drag-object first moved over target widget

        Args:
            evt (QDragEnterEvent)
        """
        # Rev. 2026-11-19
        resource_path,error_msg = self.insert_layer_drop_area.check_valid_evt_resource(evt)
        if resource_path:
            evt.accept()
        else:
            evt.ignore()

    def st_eval_drag_move_event(self, evt: QDragEnterEvent):
        """Part 2 of Drag&Drop: Drag-object moving over target widget

        Args:
            evt (QDragEnterEvent)
        """
        # Rev. 2026-11-19
        resource_path,error_msg = self.insert_layer_drop_area.check_valid_evt_resource(evt)
        if resource_path:
            evt.accept()
        else:
            evt.ignore()

    def st_eval_drop_event(self, evt: QDropEvent):
        """Part 3 of Drag&Drop: Drag-Object is dropped on target-widget

        Args:
            evt (QDropEvent)
        """
        # Rev. 2026-11-19
        resource_path,error_msg = self.insert_layer_drop_area.check_valid_evt_resource(evt)

        if resource_path:
            self.layer_lib.last_user_file = Path(resource_path).as_posix()
            parse_result = parse_container_file(resource_path,self.layer_lib,'AddResourceDialog',-1)
            self.insert_layer_drop_area.setHtml(parse_result.parse_html)
            if parse_result.parse_cache:
                self.layer_lib.parse_cache['AddResourceDialog'] = parse_result.parse_cache
                self.resource_path = resource_path
                self.resource_path_fqle.setText(resource_path)
                # convenience
                self.resource_label_fqle.setText(Path(resource_path).name)
            else:
                show_log_message(
                    "WARNING", MY_DICT.tr("no_layers_found_in_file", resource_path),self.log_message_fqlbl,True
                )
                self.resource_path_fqle.start_flash()
        else:
            show_log_message("WARNING", error_msg,self.log_message_fqlbl,True)


    def insert_resource(self):
        """parse user-inputs and try to insert resource"""
        # Rev. 2026-11-19

        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

        new_resource_path = self.resource_path_fqle.text()

        if new_resource_path and os.path.isfile(new_resource_path):
            file_suffix = str.lower(Path(new_resource_path).suffix.lstrip("."))
            if (
                file_suffix in CONTAINER_EXTENSIONS
            ):

                new_resource_label = self.resource_label_fqle.text().strip()
                if new_resource_label:
                    if self.store_resource_path_relative_qcb.isChecked():
                        storage_path = get_relative_path(
                            new_resource_path, self.layer_lib.treeview_source_path
                        )
                        if not storage_path:
                            show_log_message(
                                "WARNING",
                                "Path not storable as relative path, different anchors/drives, use absolute",self.log_message_fqlbl,True
                            )
                            return
                    else:
                        storage_path = get_absolute_path(
                            new_resource_path, self.layer_lib.treeview_source_path
                        )

                    if storage_path:
                        # optional
                        new_resource_description = (
                            self.resource_description_qpte.toPlainText().strip()
                        )


                        # Note: self.folder_qcbx has no empty option, so at least root-folder is selected
                        new_folder_id = self.folder_qcbx.currentData()

                        # Note: resource_id None => returned_layer_id random-generated, unique and valid
                        insert_ok, returned_layer_id, error_reason = (
                            insert_resource_node(
                                self.layer_lib.treeview_dom_doc,
                                None,
                                new_resource_label,
                                new_resource_description,
                                new_folder_id,
                                storage_path,
                            )
                        )

                        if insert_ok:
                            # save XML-File, reload TreeView, select new resource and close dialog
                            save_treeview_dom_doc(
                                self.layer_lib.treeview_dom_doc,
                                self.layer_lib.treeview_source_path,
                            )
                            self.layer_lib.dlg_refresh_qtrv()

                            # delayed call because dlg_refresh_qtrv will refresh TreeView with own delay
                            QTimer.singleShot(
                                10,
                                lambda returned_layer_id=returned_layer_id: self.layer_lib.tool_select_resource_by_id(
                                    returned_layer_id
                                ),
                            )

                            show_log_message(
                                "SUCCESS",
                                MY_DICT.tr(
                                    "success_resource_stored_msg",
                                    new_resource_label,
                                ),
                                show_iface_message=True
                            )

                            self.close()
                        else:
                            show_log_message("WARNING", error_reason,self.log_message_fqlbl,True)

                    else:
                        show_log_message(
                            "WARNING",
                            MY_DICT.tr(
                                "ifm_warning_data_source_path_not_found",
                                new_resource_path,
                            ),self.log_message_fqlbl,True
                        )

                else:
                    self.resource_label_fqle.start_flash()
                    show_log_message(
                        "WARNING", MY_DICT.tr("label_attribute_missing"),self.log_message_fqlbl,True
                    )
            else:
                show_log_message(
                    "WARNING",
                    MY_DICT.tr(
                        "file_suffix_not_supported", file_suffix
                    ),self.log_message_fqlbl,True
                )
        else:
            show_log_message(
                "WARNING",
                "No storable resource selected, please drop layer/file rsp. select file",
                self.log_message_fqlbl,True
            )
            return


    def fill_folder_qcbx(self, pre_selected_folder_id: str = None):
        """folder_qcbx, QComboBox with (recursive) folder-structure

        Args:
            pre_selected_folder_id (str, optional)
        """
        # Rev. 2026-11-19
        self.folder_qcbx.clear()

        root_folder = self.layer_lib.treeview_dom_doc.documentElement()
        self.fill_folder_qcbx_recursive(root_folder)

        for rc in range(self.folder_qcbx.count()):
            if self.folder_qcbx.itemData(rc, Qt.ItemDataRole.UserRole) == pre_selected_folder_id:
                self.folder_qcbx.setCurrentIndex(rc)
                break

    def fill_folder_qcbx_recursive(
        self, folder_node: QDomNode, recursion_level: int = 0
    ):
        """recursive part of fill_folder_qcbx Display-Role: folder-label User-Role: folder-id

        Args:
            folder_node (QDomNode): Current node in Treeview-XML-Dom-Document
            recursion_level (int, optional): incremented recursion-level, simulate folder-structure with prepended blanks. Defaults to 0.
        """
        # Rev. 2026-11-19
        folder_id = folder_node.toElement().attribute("id")
        folder_label = folder_node.namedItem("label").firstChild().toText().data()

        item_label = f"{recursion_level * '    '} - {folder_label}"
        self.folder_qcbx.addItem(item_label, folder_id)

        child_nodes = folder_node.childNodes()

        for node_idx in range(child_nodes.size()):
            child_node = child_nodes.at(node_idx)
            # can be <resource> or <folder>
            if child_node.nodeName() == "folder":
                self.fill_folder_qcbx_recursive(child_node, recursion_level + 1)


    def reset_dlg(self):
        """remove contents and settings from last usage"""
        # Rev. 2026-11-21
        self.resource_label_fqle.clear()
        self.resource_description_qpte.clear()
        self.resource_path_fqle.clear()
        self.log_message_fqlbl.clear()
        self.insert_layer_drop_area.setHtml(
            MY_DICT.tr("insert_layer_drop_area_ttp")
        )
        self.log_message_fqlbl.setToolTip("")
        self.layer_lib.parse_cache['AddResourceDialog'] = {}

        # keep pre-selected folder and settings
        # self.folder_qcbx.clear()
        # self.store_resource_path_relative_qcb.setChecked(False)

    def enable_insert(
        self, resource_path:str = None, folder_id:str = None
    ):
        """prepare dialog for insert

        Args:
            resource_path (str, optional): path to qlr/qgs/qgz-file
            folder_id (str,optional): pre-selected folder
        """
        # Rev. 2026-11-21
        self.reset_dlg()

        if folder_id:
            self.folder_id = folder_id
        else:
            self.folder_id = self.layer_lib.my_dialog.qtrv_layer_lib.get_selected_folder_id()

        self.fill_folder_qcbx(self.folder_id)


        if resource_path:
            if os.path.isfile(resource_path):
                self.layer_lib.last_user_file = Path(resource_path).as_posix()
                parse_result = parse_container_file(resource_path,self.layer_lib,'AddResourceDialog',-1)
                self.insert_layer_drop_area.setHtml(parse_result.parse_html)
                if parse_result.parse_cache:
                    self.layer_lib.parse_cache['AddResourceDialog'] = parse_result.parse_cache
                    self.resource_path = resource_path
                    self.resource_path_fqle.setText(resource_path)
                    # convenience
                    self.resource_label_fqle.setText(Path(resource_path).stem)
