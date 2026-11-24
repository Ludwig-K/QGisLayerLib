#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dialog to create new folder

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

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from LayerLib.qt.MyQtWidgets import FlashingBorderQLineEdit, FlashingQLabel

from qgis.PyQt.QtXml import QDomNode


from qgis.PyQt.QtGui import QFont

from qgis.PyQt.QtCore import Qt

from LayerLib.tools.MyTools import (
    get_folder_node,
    # debug_print_dom_node,
    save_treeview_dom_doc,
    insert_folder_node,
    show_log_message
)

from LayerLib.tools.MyConstants import MY_DICT

from LayerLib import LayerLib


class AddFolderDialog(QDialog):
    """Dialog for QGis-Plugin LayerLib: dialog to create new folder"""
    # Rev. 2026-11-19
    def __init__(self, layer_lib: LayerLib, parent=None):
        """Constructor

        Args:
            layer_lib (LayerLib): access to plugin
            parent (_type_, optional): optional Qt-Parent-Element for Hierarchy
        """
        # Rev. 2026-11-19
        super().__init__(parent)
        self.layer_lib = layer_lib
        self.resize(500, 300)
        self.setWindowTitle(MY_DICT.tr("AddFolderDialog_title"))
        self.setObjectName("LayerLibEditFolderDialog")
        self.setLayout(QVBoxLayout())

        header_qlbl = QLabel(MY_DICT.tr("AddFolderDialog_header"))
        my_font = header_qlbl.font()
        my_font.setPointSize(10)
        my_font.setWeight(QFont.Weight.Bold)
        header_qlbl.setFont(my_font)
        self.layout().addWidget(header_qlbl)

        content_wdg = QWidget()
        content_wdg.setLayout(QGridLayout())
        content_wdg.layout().setContentsMargins(10, 10, 10, 10)

        row = 0


        # row += 1
        folder_label_qlbl = QLabel(MY_DICT.tr("folder_label_qlbl"))
        content_wdg.layout().addWidget(folder_label_qlbl, row, 0)
        self.folder_label_fqle = FlashingBorderQLineEdit(self)
        self.folder_label_fqle.setToolTip(MY_DICT.tr("folder_lbl_qlbl_ttp"))
        content_wdg.layout().addWidget(self.folder_label_fqle, row, 1)

        row += 1
        folder_description_qlbl = QLabel(MY_DICT.tr("folder_description_qlbl"))
        content_wdg.layout().addWidget(folder_description_qlbl, row, 0)
        self.folder_description_qpte = QPlainTextEdit(self)
        self.folder_description_qpte.setToolTip(MY_DICT.tr("folder_description_qpte_ttp"))
        content_wdg.layout().addWidget(self.folder_description_qpte, row, 1)

        row += 1
        parent_folder_qlbl = QLabel(MY_DICT.tr("parent_folder_qlbl"))
        content_wdg.layout().addWidget(parent_folder_qlbl, row, 0)
        self.folder_qcbx = QComboBox(self)
        self.folder_qcbx.setToolTip("")
        content_wdg.layout().addWidget(self.folder_qcbx, row, 1)

        self.layout().addWidget(content_wdg)
        self.create_folder_qpb = QPushButton(MY_DICT.tr("create_folder_qpb"), self)
        # else will be triggered by any enter on the dialog
        self.create_folder_qpb.setAutoDefault(False)
        # Return or Enter key is pressed
        self.create_folder_qpb.pressed.connect(self.post_insert)

        self.layout().addWidget(self.create_folder_qpb)

        self.log_message_fqlbl = FlashingQLabel()
        self.layout().addWidget(self.log_message_fqlbl)

        self.reset_dlg()

    def reset_dlg(self):
        """remove contents/settings from previous usage
        """
        # Rev. 2026-11-19
        self.folder_label_fqle.clear()
        self.folder_description_qpte.clear()
        self.folder_qcbx.clear()
        self.log_message_fqlbl.clear()

    def enable_insert(self, parent_folder_id: str = None):
        """prepare dialog for insert

        Args:
            parent_folder_id (str, optional): Selected folder-id in QTreeView, used for pre-selection. Defaults to None.
        """
        # Rev. 2026-11-19
        self.reset_dlg()
        self.fill_folder_qcbx(parent_folder_id)

    def post_insert(self):
        """parse user-inputs and insert new folder"""
        # Rev. 2026-11-19
        new_folder_label = None
        new_folder_description = None
        new_parent_folder_id = None

        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

        new_folder_label = self.folder_label_fqle.text().strip()

        if new_folder_label:
            new_folder_description = self.folder_description_qpte.toPlainText().strip()

            # Note: self.folder_qcbx has no empty option, so at least root-folder is selected
            new_parent_folder_id = self.folder_qcbx.currentData()

            # Note: no folder-id posted, so insert_folder_node will generate a random, uniqe and valid id
            insert_ok, returned_folder_id, error_reason = insert_folder_node(
                self.layer_lib.treeview_dom_doc,
                None,
                new_folder_label,
                new_folder_description,
                new_parent_folder_id,
            )

            if insert_ok:
                # insert ok => save XML, refresh TreeView, select the new folder and clos this dialog
                save_treeview_dom_doc(
                    self.layer_lib.treeview_dom_doc, self.layer_lib.treeview_source_path
                )
                self.layer_lib.dlg_refresh_qtrv()
                show_log_message(
                    "SUCCESS",
                    MY_DICT.tr(
                        "success_folder_created_msg",
                        new_folder_label,
                    ),
                    show_iface_message=True
                )
                # delayed call because dlg_refresh_qtrv will refresh TreeView with own delay
                QTimer.singleShot(
                    10,
                    lambda returned_folder_id=returned_folder_id: self.layer_lib.tool_select_folder_by_id(
                        returned_folder_id
                    ),
                )
                self.close()
            else:
                show_log_message("WARNING", error_reason,self.log_message_fqlbl,True)
        else:
            self.folder_label_fqle.start_flash()
            show_log_message("WARNING", "Missing Folder-Label",self.log_message_fqlbl,True)




    def fill_folder_qcbx(self, parent_folder_id: str = None):
        """fill QComboBox folder_qcbx with (recursive) folder-structure

        Args:
            parent_folder_id (str, optional): Default parent folder ID which will be the selected option. Defaults to None => first option (DocumentElement) "root" will be selected.
        """
        # Rev. 2026-11-19

        self.folder_qcbx.clear()

        root_folder = self.layer_lib.treeview_dom_doc.documentElement()
        self.fill_folder_qcbx_recursive(root_folder)

        # pre-selected parent folder
        if parent_folder_id:
            for rc in range(self.folder_qcbx.count()):
                if self.folder_qcbx.itemData(rc, Qt.ItemDataRole.UserRole) == parent_folder_id:
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
            # childs can be <resource> or <folder>
            if child_node.nodeName() == "folder":
                self.fill_folder_qcbx_recursive(child_node, recursion_level + 1)

