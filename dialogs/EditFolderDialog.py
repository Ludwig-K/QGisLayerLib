#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dialog to show/edit folder-metadata stored in treeview_dom_doc

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
    QLineEdit
)

from LayerLib.qt.MyQtWidgets import FlashingBorderQLineEdit, FlashingQLabel

from qgis.PyQt.QtXml import QDomNode


from qgis.PyQt.QtGui import QFont

from qgis.PyQt.QtCore import Qt

from LayerLib.tools.MyTools import (
    get_folder_node,
    # debug_print_dom_node,
    alter_folder_node,
    save_treeview_dom_doc,
    show_log_message
)

from LayerLib.tools.MyConstants import MY_DICT

from LayerLib import LayerLib

class EditFolderDialog(QDialog):
    """Dialog for QGis-Plugin LayerLib: dialog to show and edit Metadata of folder"""
    # Rev. 2026-11-21
    def __init__(self, layer_lib:LayerLib, parent:QWidget=None):
        """Constructor

        Args:
            layer_lib (LayerLib): access to plugin
            parent (QWidget, optional): optional Qt-Parent-Element for Hierarchy. Defaults to None.
        """
        # Rev. 2026-11-21
        super().__init__(parent)

        self.layer_lib = layer_lib

        # unique id, auto-generated
        self.folder_id = None

        self.resize(500, 300)

        self.setWindowTitle(MY_DICT.tr("EditFolderDialog_title"))
        self.setObjectName("LayerLibEditFolderDialog")

        self.setLayout(QVBoxLayout())

        header_qlbl = QLabel(MY_DICT.tr("EditFolderDialog_header"))
        my_font = header_qlbl.font()
        my_font.setPointSize(10)
        my_font.setWeight(QFont.Weight.Bold)
        header_qlbl.setFont(my_font)
        self.layout().addWidget(header_qlbl)

        content_wdg = QWidget()
        content_wdg.setLayout(QGridLayout())
        content_wdg.layout().setContentsMargins(10, 10, 10, 10)

        row = 0
        content_wdg.layout().addWidget(QLabel(MY_DICT.tr("folder_id_qle")), row, 0)
        self.folder_id_qle = QLineEdit(self)
        self.folder_id_qle.setReadOnly(True)
        self.folder_id_qle.setToolTip(MY_DICT.tr("folder_id_qlbl_ttp"))
        content_wdg.layout().addWidget(self.folder_id_qle, row, 1)

        row += 1
        folder_label_qlbl = QLabel(MY_DICT.tr("folder_label_qlbl"))
        content_wdg.layout().addWidget(folder_label_qlbl, row, 0)
        self.folder_label_fqle = FlashingBorderQLineEdit(self)
        self.folder_label_fqle.setToolTip(MY_DICT.tr("folder_lbl_qlbl_ttp"))
        content_wdg.layout().addWidget(self.folder_label_fqle, row, 1)

        row += 1
        folder_description_qlbl = QLabel(MY_DICT.tr("folder_description_qlbl"))
        content_wdg.layout().addWidget(folder_description_qlbl, row, 0)
        self.folder_description_qpte = QPlainTextEdit(self)
        self.folder_description_qpte.setToolTip(
            MY_DICT.tr("folder_description_qpte_ttp")
        )
        content_wdg.layout().addWidget(self.folder_description_qpte, row, 1)

        row += 1
        parent_folder_qlbl = QLabel(MY_DICT.tr("parent_folder_qlbl"))
        content_wdg.layout().addWidget(parent_folder_qlbl, row, 0)
        self.folder_qcbx = QComboBox(self)
        self.folder_qcbx.setToolTip("")
        content_wdg.layout().addWidget(self.folder_qcbx, row, 1)

        self.layout().addWidget(content_wdg)

        self.update_folder_qpb = QPushButton(MY_DICT.tr("update_folder_qpb"), self)
        # else will be triggered by any enter on the dialog
        self.update_folder_qpb.setAutoDefault(False)
        self.update_folder_qpb.setToolTip(MY_DICT.tr("folder_update_folder_qpb_ttp"))
        # Return or Enter key is pressed
        self.update_folder_qpb.pressed.connect(self.post_update)
        self.layout().addWidget(self.update_folder_qpb)

        self.log_message_fqlbl = FlashingQLabel()
        self.layout().addWidget(self.log_message_fqlbl)

        self.reset_dlg()

    def enable_update(self, folder_id: str):
        """show metada of existing folder for info/edit

        Args:
            folder_id (str): id of folder, unique attribute in TreeView-XML-File
        """
        # Rev. 2026-11-19

        self.reset_dlg()
        folder_node = get_folder_node(self.layer_lib.treeview_dom_doc, folder_id)
        if folder_node:
            self.folder_id = folder_node.toElement().attribute("id")

            self.folder_id_qle.setText(folder_id)

            folder_label = folder_node.namedItem("label").firstChild().toText().data()
            folder_description = (
                folder_node.namedItem("description").firstChild().toText().data()
            )

            self.folder_label_fqle.setText(folder_label)
            self.folder_description_qpte.setPlainText(folder_description)

            parent_folder_id = None
            if folder_node.parentNode().nodeName() == "folder":
                parent_folder_id = folder_node.parentNode().toElement().attribute("id")

            self.fill_folder_qcbx(parent_folder_id)
        else:
            show_log_message("WARNING", MY_DICT.tr("folder_not_found",folder_id), self.log_message_fqlbl, True)

    def reset_dlg(self):
        """resets complete dialog:
        remove contents from form-widgets
        hide functional-buttons for update/insert/delete
        reset self.folder_id
        """
        # Rev. 2026-11-19
        self.folder_id = None
        self.folder_id_qle.clear()
        self.folder_label_fqle.clear()
        self.folder_description_qpte.clear()
        self.folder_qcbx.clear()

        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

    def post_update(self):
        """parse user-inputs and update existing folder"""
        # Rev. 2026-11-19
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")

        # new_folder_id = self.folder_id_fqle.text().strip()
        new_folder_label = self.folder_label_fqle.text().strip()

        if new_folder_label:
            new_folder_description = self.folder_description_qpte.toPlainText().strip()
            # Note: self.folder_qcbx has no empty option, so at least root-folder is selected
            new_parent_folder_id = self.folder_qcbx.currentData()

            # note: folder_id twice, id not editable, the old id is kept
            alter_ok, returned_folder_id, error_reason = alter_folder_node(
                self.layer_lib.treeview_dom_doc,
                self.folder_id,
                self.folder_id,
                new_folder_label,
                new_folder_description,
                new_parent_folder_id,
            )

            if alter_ok:
                save_treeview_dom_doc(
                    self.layer_lib.treeview_dom_doc, self.layer_lib.treeview_source_path
                )
                self.layer_lib.dlg_refresh_qtrv()
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
            return






    def fill_folder_qcbx(self, pre_selected_folder_id: str = None):
        """folder_qcbx, QComboBox with (recursive) folder-structure

        Args:
            pre_selected_folder_id (str, optional)
        """
        # Rev. 2026-11-21
        self.folder_qcbx.clear()

        root_folder = self.layer_lib.treeview_dom_doc.documentElement()
        self.fill_folder_qcbx_recursive(root_folder)

        # tricky: folder can't be moved to one of it's sub-folders, so these must be disabled
        sub_folder_ids = []

        if self.folder_id:
            sub_folder_ids.append(self.folder_id)
            current_folder_node = get_folder_node(
                self.layer_lib.treeview_dom_doc, self.folder_id
            )

            sub_folder_nodes = current_folder_node.toElement().elementsByTagName(
                "folder"
            )
            for sub_folder_node in (
                sub_folder_nodes.at(i) for i in range(sub_folder_nodes.size())
            ):
                sub_folder_ids.append(sub_folder_node.toElement().attribute("id"))

        for rc in range(self.folder_qcbx.count()):

            current_folder_id = self.folder_qcbx.itemData(rc, Qt.ItemDataRole.UserRole)

            if current_folder_id == pre_selected_folder_id:
                self.folder_qcbx.setCurrentIndex(rc)


            # disable all items, which are a child of pre_selected_folder_id
            if current_folder_id in sub_folder_ids:
                # not documented: setting Qt.ItemDataRole.UserRole - 1 (256 - 1 == 255) to False disables this option
                self.folder_qcbx.setItemData(rc, False, Qt.ItemDataRole.UserRole - 1)

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

