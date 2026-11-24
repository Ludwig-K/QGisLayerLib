#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dialog to show/edit resource-metadata stored in treeview_dom_doc

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

from qgis.PyQt.QtCore import Qt,QTimer

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QWidget,
    QVBoxLayout,
    QCheckBox,
    QFileDialog,
    QLineEdit,
    QFileDialog,
    QTabWidget
)

from LayerLib.qt.MyQtWidgets import (
    FlashingBorderQLineEdit,
    MySubLayerTextBrowser,
    FlashingQLabel,
)

from qgis.PyQt.QtXml import QDomNode

from pathlib import Path

from qgis.PyQt.QtGui import (
    QIcon,
    QFont,
    QDropEvent,
    QDragEnterEvent,
)

from qgis.PyQt.QtCore import Qt

from LayerLib.tools.MyTools import (
    get_resource_node,
    alter_resource_node,
    save_treeview_dom_doc,
    # debug_print,
    get_absolute_path,
    get_relative_path,
    get_valid_file,
    show_log_message,
    parse_container_file
)

from LayerLib.tools.MyConstants import MY_DICT, ICON_DIR, CONTAINER_EXTENSIONS

from LayerLib import LayerLib

class EditResourceDialog(QDialog):
    """Dialog for QGis-Plugin LayerLib: dialog to show/edit Metadata of registered resource"""
    # Rev. 2026-11-19
    def __init__(self, layer_lib:LayerLib, parent:QWidget=None):
        """Constructor

        Args:
            layer_lib (LayerLib): reference to plugin
            parent (QWidget, optional): optional Qt-Parent-Element for Hierarchy. Defaults to None.
        """

        # Rev. 2026-11-19
        super().__init__(parent)

        self.layer_lib = layer_lib

        # ID of selected resource, not editable, auto-generated for inserted resources, used to query and store resources from library
        self.resource_id = None

        self.resource_path = None


        self.resize(600, 600)

        # self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setWindowTitle(MY_DICT.tr("EditResourceDialog_title"))

        self.setObjectName("LayerLibEditResourceDialog")

        self.setLayout(QVBoxLayout())

        header_qlbl = QLabel(MY_DICT.tr("EditResourceDialog_header"))
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
        form_tab_wdg.layout().addWidget(QLabel("Resource-ID"), row, 0)
        self.resource_id_qle = QLineEdit(self)
        self.resource_id_qle.setReadOnly(True)
        self.resource_id_qle.setToolTip(MY_DICT.tr("resource_id_qlbl_ttp"))
        form_tab_wdg.layout().addWidget(self.resource_id_qle, row, 1)

        row += 1

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
        self.update_resource_qpb = QPushButton(MY_DICT.tr("update_resource_qpb"), self)
        # else will be triggered by any enter on the dialog
        self.update_resource_qpb.setAutoDefault(False)
        # Return or Enter key is pressed
        self.update_resource_qpb.pressed.connect(self.update_resource)
        form_tab_wdg.layout().addWidget(self.update_resource_qpb, row, 0,1,2)


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
        """open file-dialog to chose another file for this resource"""
        # Rev. 2026-11-21

        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")
        self.layer_lib.parse_cache['EditResourceDialog'] = {}


        filter = f"QGis-Container-File (*.qgz *.qgs *.qlr)"

        default_dir = get_valid_file(
            [
                self.resource_path_fqle.text(),
                self.layer_lib.last_user_file
            ],
            self.layer_lib.treeview_source_path
        )

        # getSaveFileName ohne "Confirm Overwrite" bei bereits vorhandener Datei
        selected_resource_path, filter = QFileDialog.getOpenFileName(
            None,
            MY_DICT.tr("dlg_replace_data_source_file_title", Path(self.resource_path).name),
            default_dir,
            filter=filter,
        )

        if selected_resource_path and os.path.isfile(selected_resource_path):
            self.layer_lib.last_user_file = Path(selected_resource_path).as_posix()
            parse_result = parse_container_file(selected_resource_path,self.layer_lib,'EditResourceDialog',-1)
            self.insert_layer_drop_area.setHtml(parse_result.parse_html)
            if parse_result.parse_cache:
                self.layer_lib.parse_cache['EditResourceDialog'] = parse_result.parse_cache
                self.resource_path = selected_resource_path
                self.resource_path_fqle.setText(selected_resource_path)
            else:
                show_log_message(
                    "WARNING", MY_DICT.tr("no_layers_found_in_file", selected_resource_path,self.log_message_fqlbl,True)
                )
                self.resource_path_fqle.start_flash()


    def update_resource(self):
        """update selected resource with path of storable_resource and user-defined metadata"""
        # Rev. 2026-11-21

        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

        new_resource_path = self.resource_path_fqle.text()

        new_resource_path_abs = get_absolute_path(
            new_resource_path, self.layer_lib.treeview_source_path
        )

        if new_resource_path_abs:
            file_suffix = str.lower(Path(new_resource_path_abs).suffix.lstrip("."))
            if (
                file_suffix in CONTAINER_EXTENSIONS
            ):

                new_layer_label = self.resource_label_fqle.text().strip()

                if new_layer_label:
                    storage_path = None
                    if self.store_resource_path_relative_qcb.isChecked():
                        storage_path = get_relative_path(
                            new_resource_path_abs, self.layer_lib.treeview_source_path
                        )
                        if not storage_path:
                            show_log_message(
                                "WARNING",
                                "Path not storable as relative path, different anchors/drives, use absolute",self.log_message_fqlbl,True
                            )
                            return
                    else:
                        storage_path = new_resource_path_abs

                    if storage_path:
                        # optional
                        new_layer_description = (
                            self.resource_description_qpte.toPlainText().strip()
                        )


                        # Note: self.folder_qcbx has no empty option, so at least root-folder is selected
                        new_folder_id = self.folder_qcbx.currentData()

                        alter_ok, returned_resource_id, error_reason = (
                            alter_resource_node(
                                self.layer_lib.treeview_dom_doc,
                                self.resource_id,
                                self.resource_id,
                                new_layer_label,
                                new_layer_description,
                                new_folder_id,
                                storage_path
                            )
                        )

                        if alter_ok:
                            save_treeview_dom_doc(
                                self.layer_lib.treeview_dom_doc,
                                self.layer_lib.treeview_source_path,
                            )
                            self.layer_lib.dlg_refresh_qtrv()

                            # delayed call because dlg_refresh_qtrv will refresh TreeView with own delay
                            QTimer.singleShot(
                                10,
                                lambda returned_resource_id=returned_resource_id: self.layer_lib.tool_select_resource_by_id(
                                    returned_resource_id
                                ),
                            )

                            show_log_message(
                                "SUCCESS",
                                MY_DICT.tr(
                                    "success_resource_updated",
                                    new_layer_label,
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
            current_folder_id = self.folder_qcbx.itemData(rc, Qt.ItemDataRole.UserRole)

            if current_folder_id == pre_selected_folder_id:
                self.folder_qcbx.setCurrentIndex(rc)

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
            if child_node.nodeName() == "folder":
                self.fill_folder_qcbx_recursive(child_node, recursion_level + 1)

    def enable_update(self, resource_id: str):
        """init dialog with stored resource

        Args:
            resource_id (str): id of resource in treeview_dom_doc
        """
        # Rev. 2026-11-21
        self.reset_dlg()
        resource_node = get_resource_node(self.layer_lib.treeview_dom_doc, resource_id)
        if resource_node:

            self.resource_id = resource_id
            self.resource_id_qle.setText(self.resource_id)


            # exctract node-values from resource-node, firstChild because of <![CDATA[...]>
            resource_label = (
                resource_node.namedItem("label").firstChild().toText().data()
            )

            self.resource_label_fqle.setText(resource_label)


            resource_description = (
                resource_node.namedItem("description").firstChild().toText().data()
            )

            self.resource_description_qpte.setPlainText(resource_description)

            # set property, even if not valid
            self.resource_path = resource_node.namedItem("path").firstChild().toText().data()

            self.resource_path_fqle.setText(self.resource_path)

            resource_path_abs = get_absolute_path(
                self.resource_path, self.layer_lib.treeview_source_path
            )

            if resource_path_abs:

                self.layer_lib.last_user_file = resource_path_abs

                parse_result = parse_container_file(resource_path_abs,self.layer_lib,'EditResourceDialog',-1)

                if parse_result:
                    self.layer_lib.parse_cache['EditResourceDialog'] = parse_result.parse_cache
                    self.insert_layer_drop_area.setHtml(parse_result.parse_html)

                else:
                    # should not happen, already checked in check_valid_evt_resource
                    self.resource_path_fqle.start_flash()
                    self.insert_layer_drop_area.start_flash()
                    show_log_message("WARNING", MY_DICT.tr("error_parsing_container_file",self.resource_path), self.log_message_fqlbl, True)
                    return

            else:
                self.resource_path_fqle.start_flash()
                show_log_message(
                    "WARNING", MY_DICT.tr("file_not_found", self.resource_path),self.log_message_fqlbl,True
                )

            self.folder_id = None
            if resource_node.parentNode().nodeName() == "folder":
                self.folder_id = resource_node.parentNode().toElement().attribute("id")

            self.fill_folder_qcbx(self.folder_id)

        else:
            show_log_message("WARNING", MY_DICT.tr("resource_not_found",resource_id), self.log_message_fqlbl, True)

    def reset_dlg(self):
        """resets dialog and settings from last usage"""
        # Rev. 2026-11-21
        self.resource_label_fqle.clear()
        self.resource_id_qle.clear()
        self.resource_description_qpte.clear()
        self.folder_qcbx.clear()
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")
        self.resource_id = None
        self.layer_lib.parse_cache['EditResourceDialog'] = {}
        self.insert_layer_drop_area.setHtml(
            MY_DICT.tr("insert_layer_drop_area_ttp")
        )


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
        MySubLayerTextBrowser has setAcceptDrops = True and pre-evaluates drop of files from file-system, layers from QGis-layers-panel or uris from QGis-browser-panel

        Args:
            evt (QDropEvent)
        """
        # Rev. 2026-11-19

        resource_path,error_msg = self.insert_layer_drop_area.check_valid_evt_resource(evt)
        if resource_path:
            self.layer_lib.last_user_file = Path(resource_path).as_posix()
            parse_result = parse_container_file(resource_path,self.layer_lib,'EditResourceDialog',-1)
            self.insert_layer_drop_area.setHtml(parse_result.parse_html)
            if parse_result.parse_cache:
                self.layer_lib.parse_cache['EditResourceDialog'] = parse_result.parse_cache
                self.resource_path = resource_path
                self.resource_path_fqle.setText(resource_path)
            else:
                show_log_message(
                    "WARNING", MY_DICT.tr("no_layers_found_in_file", resource_path,self.log_message_fqlbl,True)
                )
                self.resource_path_fqle.start_flash()
        else:
            show_log_message("WARNING", error_msg,self.log_message_fqlbl,True)