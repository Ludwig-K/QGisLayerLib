#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dialog to confirm resource or folder-deletes
* with additional "do-not-ask-again"-option

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


from qgis.PyQt.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


from qgis.PyQt.QtGui import QFont

from LayerLib.tools.MyConstants import MY_DICT

from LayerLib.tools.MyTools import get_resource_node, get_folder_node, show_log_message

from LayerLib import LayerLib

from LayerLib.qt.MyQtWidgets import FlashingQLabel


class MyConfirmDialog(QDialog):
    """Dialog for QGis-Plugin LayerLib: dialog to confirm resource or folder-deletes with additional "do-not-ask-again"-option"""
    # Rev. 2026-11-21

    def __init__(self, layer_lib:LayerLib,  parent: QWidget = None):
        """Constructor

        Args:
            layer_lib (LayerLib): Back-Reference to Plugin
            parent (QWidget, optional): optional Qt-Parent-Element for Hierarchy. Defaults to None.
        """
        # Rev. 2026-11-21
        super().__init__(parent)

        self.layer_lib = layer_lib


        self.resize(300, 150)

        self.setWindowTitle(MY_DICT.tr("MyConfirmDialog_title"))
        self.setObjectName("LayerLibMyConfirmDialog")


        self.setLayout(QVBoxLayout())

        # content depending on deleted object, see enable_delete_folder/enable_delete_resource
        self.header_qlbl = QLabel(MY_DICT.tr("MyConfirmDialog_header"))
        my_font = self.header_qlbl.font()
        my_font.setPointSize(10)
        my_font.setWeight(QFont.Weight.Bold)
        self.header_qlbl.setFont(my_font)
        self.layout().addWidget(self.header_qlbl)

        self.contents_qlbl = QLabel("")
        self.layout().addWidget(self.contents_qlbl)


        self.confirm_single_qpb = QPushButton(MY_DICT.tr("confirm_single_qpb_txt"), self)
        self.confirm_single_qpb.setAutoDefault(False)
        self.confirm_single_qpb.pressed.connect(self.confirm_single)
        self.layout().addWidget(self.confirm_single_qpb)

        self.confirm_always_qpb = QPushButton(MY_DICT.tr("confirm_always_qpb_txt"), self)
        self.confirm_always_qpb.setAutoDefault(False)
        self.confirm_always_qpb.pressed.connect(self.confirm_always)
        self.layout().addWidget(self.confirm_always_qpb)

        self.cancel_qpb = QPushButton(MY_DICT.tr("cancel_qpb_txt"), self)
        # default-action Cancel with any enter on the dialog
        self.cancel_qpb.setAutoDefault(True)
        self.cancel_qpb.pressed.connect(self.cancel)

        self.layout().addWidget(self.cancel_qpb)

        self.log_message_fqlbl = FlashingQLabel()
        self.layout().addWidget(self.log_message_fqlbl)


    def enable_delete_folder(self,folder_id:str):
        """Dialog used to delete folder (with sub-folders and resources)

        Args:
            folder_id (str): id of deleted folder
        """
        # Rev. 2026-11-21
        self.header_qlbl.clear()
        self.contents_qlbl.clear()
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip('')


        folder_node = get_folder_node(self.layer_lib.treeview_dom_doc, folder_id)
        if folder_node:
            if folder_node != self.layer_lib.treeview_dom_doc.documentElement():
                # root-folder can't be deleted
                folder_label = (
                    folder_node.namedItem("label").firstChild().toText().data()
                )
                layer_nodes = folder_node.toElement().elementsByTagName("resource")
                folder_nodes = folder_node.toElement().elementsByTagName("folder")

                num_delete_layers = layer_nodes.size()
                num_delete_folders = folder_nodes.size()

                self.header_qlbl.setText(MY_DICT.tr("confirm_delete_folder",folder_label))

                if num_delete_layers or num_delete_folders:
                    self.contents_qlbl.setText(MY_DICT.tr("confirm_delete_folder_with_contents",num_delete_layers,num_delete_folders + 1))
            else:
                # should not happen
                show_log_message(
                    "WARNING", MY_DICT.tr("root_folder_not_deletable"), self.log_message_fqlbl,True
                )
        else:
            show_log_message(
                "WARNING", MY_DICT.tr("folder_not_found", folder_id), self.log_message_fqlbl,True
            )

    def enable_delete_resource(self,resource_id:str):
        """Dialog used for resource-delete

        Args:
            resource_id (str): ID of deleted resource
        """
        # Rev. 2026-11-21
        self.header_qlbl.clear()
        self.contents_qlbl.clear()
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip('')

        resource_node = get_resource_node(self.layer_lib.treeview_dom_doc, resource_id)
        if resource_node:
            resource_label = resource_node.namedItem("label").firstChild().toText().data()
            self.header_qlbl.setText(MY_DICT.tr("confirm_delete_resource",resource_label))
        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("metadata_for_resource_missing", resource_id),self.log_message_fqlbl,True
            )

    def confirm_single(self):
        """click on self.confirm_single_qpb
        returns 1 to the function which called dialog.exec()
        """
        # Rev. 2026-11-21
        self.done(1)


    def confirm_always(self):
        """click on self.confirm_always_qpb ("Do not ask again")
        returns 2 to the function which called dialog.exec()
        """
        # Rev. 2026-11-21
        self.done(2)


    def cancel(self):
        """click on self.cancel_qpb "Cancel"
        returns 0 to the function which called dialog.exec()
        (same as if the user siomply closes dialog)
        """
        # Rev. 2026-11-21
        self.done(0)


