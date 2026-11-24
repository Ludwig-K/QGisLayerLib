#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib, but usable for any other PyQt-Project
* Replacement for Qt-Linguist which lacks multi-lines and markup and wildcards
* Application to edit XML-File "Snippets.xml": Translation-Dictionary
* Can be executed as Stand-Alone QApplication outside QGis
* result-file hard coded: Snippets.xml inside the current directory
* Paths to Python-Files using the registered snippets must be defined
* relative to current directory

********************************************************************

* Date                 : 2026-07-09
* Copyright            : (C) 2026 by Ludwig Kniprath
* Email                : ludwig at kni minus online dot de

********************************************************************

this program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

********************************************************************
"""
# Rev. 2026-09-15
import os, sys, re, json
from pathlib import Path

# geht mit PyQt5 und PyQt6...
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTableWidget,
    QTableView,
    QLabel,
    QLineEdit,
    QTableWidgetItem,
    QAbstractItemView,
    QScrollArea,
    QFrame,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QMessageBox,
    QSplitter,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QInputDialog,
    QStyle,
    QWidget
)

from PyQt5.QtXml import QDomDocument, QDomElement, QDomNode

from PyQt5.QtCore import (
    QTextStream,
    QByteArray,
    QBuffer,
    QIODevice,
    Qt,
    pyqtSignal,
    QObject,
    QEvent,
    QModelIndex,
    QItemSelection,
    QSignalBlocker
)

from PyQt5.QtGui import QFontDatabase, QTextOption, QStandardItemModel, QStandardItem


def ba_to_string(in_ba: bytearray | bytes | QByteArray) -> str:
    """Convert bytes to string
    avoid "'utf-8' codec can't decode byte 0xfc in position 0: invalid start byte", often raised by file-names containing äöü-"Umlauts" in windows
    Args:
        in_ba (bytearray | bytes | QByteArray): Note: bytes and bytearray are the same in Python
        Vice verso strings can be converted to bytes f. e. by stringvar.encode('utf-8')

    Returns:
        str: utf-8-compatible version
    """
    # Rev. 2026-09-22
    out_str = ""
    try:
        # strict, runs under linux without problems, throws Exception for german "umlaute" äöü under windows
        out_str = str(in_ba, "utf-8")
    except Exception as e:
        try:
            # f.e. for german "umlaute" äöü
            out_str = str(in_ba, "Windows-1252")
        except Exception as e:
            try:
                out_str = str(in_ba, "latin-1")
            except Exception as e:
                out_str = str(in_ba, "utf-8", "ignore")

    return out_str

class MultiLineDelegate(QStyledItemDelegate):
    """Delegate used in qtw_snippet_translations to enable multi-line-edits
    Without delegate a Double-Click to activate edits delivers a QLineEdit without linebreaks
    This delegate delivers a QPlainTextEdit *with* linebreaks
    """
    # Rev. 2026-09-15

    fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    fixed_font.setPixelSize(13)

    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(
        self, parent: QWidget, option: QStyleOptionViewItem, idx: QModelIndex
    ) -> QPlainTextEdit:
        """subclassed: delivers pimped QPlainTextEdit instead of QLineEdit

        Args:
            parent (QWidget)
            option (QStyleOptionViewItem)
            idx (QModelIndex)

        Returns:
            QPlainTextEdit
        """
        editor_wdg = QPlainTextEdit(parent)
        editor_wdg.setFont(self.fixed_font)
        editor_wdg.setWordWrapMode(QTextOption.WrapMode.NoWrap)

        return editor_wdg

    def setEditorData(self, editor_wdg: QWidget, idx: QModelIndex):
        """subclassed: Fills data from index into above created QPlainTextEdit

        Args:
            editor_wdg (QWidget)
            idx (QModelIndex)
        """
        # Rev. 2026-09-15
        editor_wdg.setPlainText(idx.data(Qt.ItemDataRole.DisplayRole))

class SnipDictEditor(QMainWindow):
    """Dialog to show and edit snippets"""
    # Rev. 2026-09-15
    def __init__(self):
        """constructor"""
        # Rev. 2026-09-15
        super().__init__()


        # file-name and path hard coded with file located in same directory as python-script
        self.snippets_path = (Path(os.path.dirname(__file__)) / "Snippets.xml").as_posix()

        # parsed XML-File, else None rsp. Exceptions
        self.load_dom_doc(self.snippets_path)


        # hard coded paths relative to current script, used for scan_all_usages
        # only necesary to examine usage of the registered snippets
        self.scan_files = [
            "LayerLib.py",
            "dialogs/LayerLibDialog.py",
            "dialogs/EditResourceDialog.py",
            "dialogs/AddResourceDialog.py",
            "dialogs/EditFolderDialog.py",
            "dialogs/AddFolderDialog.py",
            "dialogs/DataSourcesDialog.py",
            "dialogs/SelectSubLayerDialog.py",
            "dialogs/MyConfirmDialog.py",
            "qt/MyQtWidgets.py",
            "tools/MyTools.py"
        ]

        # Translation-languages, has to be adapted for other/further languages
        # Afterwards each translation must be processed separately.
        # <trans lan="en">...</trans>
        self.languages = ["en", "de"]




        # flag to register user-edits and avoid accidental overwriting
        self.snippet_modified = False

        # key of current edited snippet
        self.edit_snip_key = None

        self.multi_line_delegate = MultiLineDelegate()



        self.setWindowTitle("SnipDict-Editor")

        central_wdg = QSplitter(self)
        central_wdg.setObjectName("central_wdg")
        central_wdg.setChildrenCollapsible(True)
        central_wdg.setOrientation(Qt.Orientation.Horizontal)
        # StyleSHeet also applied to SUb-Splitter
        central_wdg.setStyleSheet("QSplitter::handle{background-color: lightGray}")
        central_wdg.setHandleWidth(2)

        qfr_left = QFrame()

        qfr_left = QSplitter(self)
        qfr_left.setChildrenCollapsible(True)
        qfr_left.setObjectName("qfr_left")
        qfr_left.setOrientation(Qt.Orientation.Vertical)
        qfr_left.setHandleWidth(2)



        qfr_left_top = QFrame()
        qfr_left_top.setLayout(QGridLayout())

        rc = 0
        self.qle_search_value = ClickableQLineEdit()
        self.qle_search_value.enter_pressed.connect(self.st_filter_snippets_all)

        qfr_left_top.layout().addWidget(self.qle_search_value, rc, 0)

        self.qpb_filter_snippets_all = QPushButton("Find all")
        self.qpb_filter_snippets_all.setToolTip("Wildcard-Search snippets on all columns")
        self.qpb_filter_snippets_all.clicked.connect(self.st_filter_snippets_all)
        qfr_left_top.layout().addWidget(self.qpb_filter_snippets_all, rc, 1)

        self.qpb_filter_snippets_trans = QPushButton("Find translation")
        self.qpb_filter_snippets_trans.setToolTip("Find snippets by translation(s)")
        self.qpb_filter_snippets_trans.clicked.connect(self.st_filter_snippets_trans)
        qfr_left_top.layout().addWidget(self.qpb_filter_snippets_trans, rc, 2)

        self.qpb_filter_snippets_key = QPushButton("Find key")
        self.qpb_filter_snippets_key.setToolTip("Find snippets by key")
        self.qpb_filter_snippets_key.clicked.connect(self.st_filter_snippets_key)
        qfr_left_top.layout().addWidget(self.qpb_filter_snippets_key, rc, 3)

        self.qpb_filter_snippets_usage = QPushButton("Find usage")
        self.qpb_filter_snippets_usage.setToolTip("Find snippets by usage")
        self.qpb_filter_snippets_usage.clicked.connect(self.st_filter_snippets_usage)
        qfr_left_top.layout().addWidget(self.qpb_filter_snippets_usage, rc, 4)

        self.qpb_scan_all_usages = QPushButton("Scan usages")
        self.qpb_scan_all_usages.setToolTip("Re-Scan all snippet-usages")
        self.qpb_scan_all_usages.clicked.connect(self.st_scan_all_usages)
        qfr_left_top.layout().addWidget(self.qpb_scan_all_usages, rc, 5)

        self.qpb_reload = QPushButton("Reload")
        self.qpb_reload.setToolTip("Reload data and table, remove search-filters")
        self.qpb_reload.clicked.connect(self.st_reload)
        qfr_left_top.layout().addWidget(self.qpb_reload, rc, 6)

        rc += 1
        self.qsa_snip_dict = QScrollArea()
        self.qsa_snip_dict.setWidgetResizable(True)

        self.qtv_snip_dict = QTableView()
        self.qtv_snip_dict.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.qtv_snip_dict.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.qtv_snip_dict.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.qtv_snip_dict.horizontalHeader().setStretchLastSection(True)

        self.qsa_snip_dict.setWidget(self.qtv_snip_dict)

        qfr_left_top.layout().addWidget(self.qsa_snip_dict, rc, 0, 1, 7)

        qfr_left.addWidget(qfr_left_top)


        qfr_left_bottom = QFrame()
        qfr_left_bottom.setLayout(QVBoxLayout())

        qfr_left_bottom.layout().addWidget(QLabel("Parsed File:"))

        self.qle_snippets_path = QLineEdit()
        self.qle_snippets_path.setReadOnly(True)

        qfr_left_bottom.layout().addWidget(self.qle_snippets_path)

        qfr_left_bottom.layout().addWidget(QLabel("Scan-Files for Snip-Usages:"))
        self.qpte_scan_files = QPlainTextEdit()
        self.qpte_scan_files.setReadOnly(True)
        self.qpte_scan_files.setPlainText('\n'.join(self.scan_files))
        qfr_left_bottom.layout().addWidget(self.qpte_scan_files)



        qfr_left.addWidget(qfr_left_bottom)


        qfr_left.setStretchFactor(0,4)
        qfr_left.setStretchFactor(1,1)


        central_wdg.addWidget(qfr_left)


        qfr_right = QSplitter(self)
        qfr_right.setObjectName("qfr_right")
        qfr_right.setOrientation(Qt.Orientation.Vertical)
        qfr_right.setHandleWidth(2)

        qfr_right_top = QFrame()
        qfr_right_top.setLayout(QGridLayout())

        rc = 0

        qfr_right_top.layout().addWidget(QLabel("snip_key:"), rc, 0)
        self.qle_snip_key = QLineEdit()
        #self.qle_snip_key.setReadOnly(True)
        qfr_right_top.layout().addWidget(self.qle_snip_key, rc, 1)

        rc += 1
        qfr_right_top.layout().addWidget(QLabel("Snip-Info:"), rc, 0)
        self.qpte_snip_info = QPlainTextEdit()
        self.qpte_snip_info.setToolTip("Optional info for this snippet")
        self.qpte_snip_info.textChanged.connect(self.st_register_snippet_edit)
        qfr_right_top.layout().addWidget(self.qpte_snip_info, rc, 1)

        rc += 1
        qfr_right_top.layout().addWidget(QLabel("Snip-Usages:"), rc, 0)
        self.qpte_snip_usages = QPlainTextEdit()
        self.qpte_snip_usages.setReadOnly(True)
        self.qpte_snip_usages.setToolTip(
            "Dynamically collected usages for this snippet in specified Scan-Files"
        )
        qfr_right_top.layout().addWidget(self.qpte_snip_usages, rc, 1)

        qfr_right.addWidget(qfr_right_top)

        qfr_right_center = QFrame()
        qfr_right_center.setLayout(QGridLayout())

        rc = 0

        qfr_right_center.layout().addWidget(QLabel("Translations:"), rc, 0)

        self.qtw_snippet_translations = QTableWidget()
        self.qtw_snippet_translations.setColumnCount(2)
        self.qtw_snippet_translations.setHorizontalHeaderLabels(
            ["language", "translation"]
        )

        self.qtw_snippet_translations.horizontalHeader().setStretchLastSection(True)

        self.qtw_snippet_translations.setItemDelegateForColumn(
            1, self.multi_line_delegate
        )

        self.qtw_snippet_translations.itemChanged.connect(self.st_register_snippet_edit)
        qfr_right_center.layout().addWidget(self.qtw_snippet_translations, rc, 1)

        rc += 1

        self.qpb_save_edits = QPushButton("Save snippet...")
        qfr_right_center.layout().addWidget(self.qpb_save_edits, rc, 0, 1, 2)
        self.qpb_save_edits.clicked.connect(self.st_save_snippet)

        rc += 1

        self.qpb_new_snippet = QPushButton("Create New Snippet...")
        qfr_right_center.layout().addWidget(self.qpb_new_snippet, rc, 0, 1, 2)
        self.qpb_new_snippet.clicked.connect(self.st_new_snippet)

        rc += 1
        self.qlbl_update_messages = QLabel()
        qfr_right_center.layout().addWidget(self.qlbl_update_messages, rc, 0, 1, 2)

        qfr_right.addWidget(qfr_right_center)


        qfr_right_bottom = QFrame()
        qfr_right_bottom.setLayout(QVBoxLayout())

        qfr_right_bottom.layout().addWidget(QLabel("Scratch-Pad:"))

        self.qpte_scratch_pad = QPlainTextEdit()

        qfr_right_bottom.layout().addWidget(self.qpte_scratch_pad)

        qfr_right.addWidget(qfr_right_bottom)

        qfr_right.setStretchFactor(0,1)
        qfr_right.setStretchFactor(1,3)
        qfr_right.setStretchFactor(2,1)


        central_wdg.addWidget(qfr_right)

        self.setCentralWidget(central_wdg)

        self.st_reload()

    def load_dom_doc(self,snippets_path:str):
        """opens and parses xml-file, set self.snippets_dom_doc

        Args:
            snippets_path (str): usually self.snippets_path

        Returns:
            QDomDocument if snippets_path could be parsed, else None

        Raises:
            Exception: XML not valid
            Exception: File not found
        """
        # Rev. 2026-09-15
        self.snippets_dom_doc = QDomDocument()
        if isinstance(snippets_path,str) and snippets_path != '':
            snippets_path_posix = Path(snippets_path)

            if snippets_path_posix.is_file():
                with open(snippets_path_posix.as_posix(), 'rb', -1) as in_f:
                    # can raise exceptions, f.e. if there are control-characters in the xml-file
                    parse_ok, error_msg, error_line, error_col = (
                        self.snippets_dom_doc.setContent(in_f.read())
                    )
                    if not parse_ok:
                        raise Exception(
                            f"SnipDict: parsing SnippetsPath '{snippets_path_posix.as_posix()}' failed in line #{error_line}: {error_msg}"
                        )
            else:
                raise FileNotFoundError(
                    f"SnipDict: parsing SnippetsPath '{snippets_path}' failed: file not found"
                )
        else:
            raise FileNotFoundError(
                f"SnipDict: SnippetsPath is empty"
            )


    def st_scan_all_usages(self):
        """scans snip_dict-usages via self.scan_files and refreshes QTableWidget to show new <snip_usages>
        note: file/line of usage is stored to XML-File only for information-purposes
        """
        # Rev. 2026-09-15
        # pre-check if file exists
        for scan_file in self.scan_files:
            scan_path_posix = Path(os.path.dirname(__file__)).parent / scan_file

            if not scan_path_posix.is_file():
                QMessageBox.warning(
                    self,
                    "Scan Usages aborted",
                    f"Scan-File '{scan_file}' not found",
                    buttons=QMessageBox.StandardButton.Ok,
                    defaultButton=QMessageBox.StandardButton.Ok,
                )
                return

        # will modify and save dom-doc
        self.scan_all_usages()

        scaned_files = "\n - " + "\n - ".join(self.scan_files)
        QMessageBox.information(
            self,
            "Scan Usages",
            f"Scaned files:\n{scaned_files}",
            buttons=QMessageBox.StandardButton.Ok,
            defaultButton=QMessageBox.StandardButton.Ok,
        )

        #refresh QTreeView
        self.st_reload()

    def st_filter_snippets_all(self):
        """refresh QTableWidget and filter items, if search string is entered"""
        # Rev. 2026-09-15
        for row in range(self.qtv_snip_dict.model().rowCount()):
            self.qtv_snip_dict.setRowHidden(row, False)

        if self.qle_search_value.text():
            search_value = self.qle_search_value.text().lower()
            for row in range(self.qtv_snip_dict.model().rowCount()):
                string_found = False
                #all columns
                for col in range(self.qtv_snip_dict.model().columnCount()):
                    item = self.qtv_snip_dict.model().item(row, col)
                    string_found |= (
                        item.data(Qt.ItemDataRole.DisplayRole) is not None
                        and search_value
                        in item.data(Qt.ItemDataRole.DisplayRole).lower()
                    )

                self.qtv_snip_dict.setRowHidden(row, not string_found)


    def st_reload(self):
        """reload and refresh QTableWidget"""
        # Rev. 2026-09-15
        self.load_dom_doc(self.snippets_path)
        self.qtv_snip_dict.setModel(None)
        self.populate_qtv_snip_dict()

    def st_filter_snippets_trans(self):
        """refresh QTableWidget and filter items, if search string is entered"""
        # Rev. 2026-09-15
        for row in range(self.qtv_snip_dict.model().rowCount()):
            self.qtv_snip_dict.setRowHidden(row, False)

        if self.qle_search_value.text():
            search_value = self.qle_search_value.text().lower()
            for row in range(self.qtv_snip_dict.model().rowCount()):
                string_found = False
                # no search in tranlation columns
                for col in range(2,2 + len(self.languages)):
                    item = self.qtv_snip_dict.model().item(row, col)
                    string_found |= (
                        item.data(Qt.ItemDataRole.DisplayRole) is not None
                        and search_value
                        in item.data(Qt.ItemDataRole.DisplayRole).lower()
                    )

                self.qtv_snip_dict.setRowHidden(row, not string_found)



    def st_filter_snippets_key(self):
        """refresh QTableWidget and filter items, if search string is entered"""
        # Rev. 2026-09-15
        for row in range(self.qtv_snip_dict.model().rowCount()):
            self.qtv_snip_dict.setRowHidden(row, False)

        if self.qle_search_value.text():
            search_value = self.qle_search_value.text().lower()
            col_index = 1
            for row in range(self.qtv_snip_dict.model().rowCount()):
                string_found = False
                item = self.qtv_snip_dict.model().item(row, col_index)
                string_found |= (
                    item.data(Qt.ItemDataRole.DisplayRole) is not None
                    and search_value
                    in item.data(Qt.ItemDataRole.DisplayRole).lower()
                )

                self.qtv_snip_dict.setRowHidden(row, not string_found)


    def st_filter_snippets_usage(self):
        """refresh QTableWidget and filter items, if search string is entered"""
        # Rev. 2026-09-15
        for row in range(self.qtv_snip_dict.model().rowCount()):
            self.qtv_snip_dict.setRowHidden(row, False)

        if self.qle_search_value.text():
            search_value = self.qle_search_value.text().lower()
            col_index = 3 + len(self.languages)
            for row in range(self.qtv_snip_dict.model().rowCount()):
                item = self.qtv_snip_dict.model().item(row, col_index)
                string_found = (
                    item.data(Qt.ItemDataRole.DisplayRole) is not None
                    and search_value
                    in item.data(Qt.ItemDataRole.DisplayRole).lower()
                )

                self.qtv_snip_dict.setRowHidden(row, not string_found)



    def populate_qtv_snip_dict(self):
        """parses self.snippets_dom_doc and fills parsed snippet-nodes into qtv_snip_dict"""
        # Rev. 2026-09-15
        self.qle_snippets_path.setText(self.snippets_path)

        self.qtv_snip_dict.setSortingEnabled(False)

        header_labels = ["line-nbr", "key"]

        for lan in self.languages:
            header_labels.append(f'<trans lan="{lan}">')

        header_labels.append("snip_info")
        header_labels.append("usages")
        header_labels.append("delete")

        snippet_nodes = self.snippets_dom_doc.elementsByTagName("snippet")

        # start-size 0 incremented by in_model.appendRow(items)
        in_model = QStandardItemModel(0, len(header_labels))

        in_model.setHorizontalHeaderLabels(header_labels)

        rc = 0
        for snippet_node in (snippet_nodes.at(i) for i in range(snippet_nodes.size())):

            snip_key = snippet_node.toElement().attribute("snip_key")

            child_nodes = snippet_node.childNodes()

            translations = {}
            for node_idx in range(child_nodes.size()):
                child_node = child_nodes.at(node_idx)
                if child_node.nodeName() == "trans":
                    lan = child_node.toElement().attribute("lan")
                    snip_content = child_node.firstChild().toText().data()
                    # re-replace CDEnd, see SnipDictEditor.create_snippet_node
                    snip_content = re.sub(r"##CDEnd##", "]]>", snip_content)
                    translations[lan] = snip_content

            snip_info = (
                snippet_node.firstChildElement("snip_info").firstChild().toText().data()
            )
            # re-replace CDEnd, see SnipDictEditor.create_snippet_node
            snip_info = re.sub("##CDEnd##", "]]>", snip_info)

            snip_usages = (
                snippet_node.firstChildElement("snip_usages")
                .firstChild()
                .toText()
                .data()
            )

            items = []

            nr_item = QStandardItem()
            # append blanks to make this column sortable numerically instead of string
            lpad = str(snippet_node.lineNumber()).rjust(6, " ")

            nr_item.setData(f"# {lpad}", Qt.ItemDataRole.DisplayRole)
            nr_item.setData(snip_key, Qt.ItemDataRole.UserRole)

            items.append(nr_item)

            item = QStandardItem()
            item.setData(snip_key, Qt.ItemDataRole.DisplayRole)
            items.append(item)

            for lan in self.languages:
                item = QStandardItem()
                item.setData(translations.get(lan, ""), Qt.ItemDataRole.DisplayRole)
                items.append(item)

            item = QStandardItem()
            item.setData(snip_info, Qt.ItemDataRole.DisplayRole)
            items.append(item)

            item = QStandardItem()
            item.setData(snip_usages, Qt.ItemDataRole.DisplayRole)
            items.append(item)

            del_item = QStandardItem()
            del_item.setData(snip_key, Qt.ItemDataRole.UserRole)
            items.append(del_item)

            in_model.appendRow(items)





        self.qtv_snip_dict.setModel(in_model)

        col = self.qtv_snip_dict.model().columnCount() - 1
        for row in range(self.qtv_snip_dict.model().rowCount()):
            # Achtung: item(row,col) ist ein künstlicher Index und hat nur indirekt mit dem Modell-Index zu tun
            del_item = self.qtv_snip_dict.model().item(row,col)
            del_item_cell_widget = QWidget()
            del_item_cell_widget.setLayout(QHBoxLayout())
            qtb_delete = QToolButton(self.qtv_snip_dict)
            qtb_delete.setToolButtonStyle(Qt.ToolButtonIconOnly)
            qtb_delete.setFixedSize(20, 20)
            qtb_delete.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
            qtb_delete.pressed.connect(lambda item=del_item:self.st_delete_snippet(item))
            qtb_delete.setStyleSheet("QToolButton { border: 1px solid transparent; } QToolButton::hover {background-color: silver;}")
            del_item_cell_widget.layout().addWidget(qtb_delete)
            self.qtv_snip_dict.setIndexWidget(
                del_item.index(), del_item_cell_widget
            )



        self.qtv_snip_dict.setSortingEnabled(True)

        self.qtv_snip_dict.selectionModel().selectionChanged.connect(
            self.st_selection_changed
        )

    def st_new_snippet(self):
        """create new snippet:
        asks for snip_key (checked for uniqueness), creates and inserts XML-template (new empty snippet with that snip_key), show edit-dialog for this snippet"""
        # Rev. 2026-09-15
        if self.edit_snip_key and self.snippet_modified:
            result_button = QMessageBox.question(
                self,
                "SnipDict Save edits",
                f"Snippet '{self.edit_snip_key}' was modified, save edits?",
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                defaultButton=QMessageBox.StandardButton.Yes,
            )
            if result_button == QMessageBox.StandardButton.Yes:
                self.st_save_snippet()


        self.snippet_modified = False
        self.edit_snip_key = None

        snip_key, ok = QInputDialog.getText(
            self, "New Snippet", "Enter unique and valid Snip-Key:"
        )

        if ok and snip_key:
            snip_key_ok, error_msg = self.get_unique_id(snip_key)

            if snip_key_ok:
                new_snippet_node = self.create_snippet_node(snip_key)

                if new_snippet_node:
                    # should always be the case, since snip_key can not contain XML-invalid contents
                    # append node
                    self.snippets_dom_doc.documentElement().appendChild(
                        new_snippet_node
                    )

                    self.sys_save_dom_doc()

                    self.qlbl_update_messages.setText(
                        f"New Snippet '{snip_key}' created"
                    )

                    # refresh QTableWidget
                    self.st_reload()
                    # refresh edit-form
                    self.st_edit_snippet(snip_key)
            else:
                QMessageBox.warning(
                    self,
                    "New Snippet aborted",
                    f"Snip-Key '{snip_key}' invalid:\n{error_msg}",
                    buttons=QMessageBox.StandardButton.Ok,
                    defaultButton=QMessageBox.StandardButton.Ok,
                )

    def st_save_snippet(self):
        """saves selected snippet"""
        # Rev. 2026-09-15
        self.snippet_modified = False
        self.qlbl_update_messages.clear()

        if self.edit_snip_key:

            # qle_snip_key is read-only
            snip_key = self.qle_snip_key.text()

            old_snippet_node = self.find_snippet(self.edit_snip_key)

            translations = {}
            for rc in range(self.qtw_snippet_translations.rowCount()):
                lan = self.qtw_snippet_translations.item(rc, 0).text()
                trans = self.qtw_snippet_translations.item(rc, 1).text()

                translations[lan] = trans


            snip_info = self.qpte_snip_info.toPlainText()

            snip_usage = "\n".join(self.scan_usage(snip_key))

            new_snippet_node = self.create_snippet_node(
                snip_key, snip_info, snip_usage, translations
            )

            if new_snippet_node:
                if old_snippet_node:
                    # replace node
                    self.snippets_dom_doc.documentElement().insertAfter(
                        new_snippet_node, old_snippet_node
                    )
                    old_snippet_node.parentNode().removeChild(old_snippet_node)
                else:
                    # append node
                    self.snippets_dom_doc.documentElement().appendChild(
                        new_snippet_node
                    )


                self.sys_save_dom_doc()

                # refresh QTableWidget
                self.st_reload()
                # refresh edit-form
                self.st_edit_snippet(snip_key)



        else:
            QMessageBox.warning(
                self,
                "Save Snippet aborted",
                "No Snippet selected",
                buttons=QMessageBox.StandardButton.Ok,
                defaultButton=QMessageBox.StandardButton.Ok,
            )

    def create_snippet_node(
        self,
        snip_key: str = "",
        snip_info: str = "",
        snip_usage: str = "",
        translations: dict = {},
    ) -> QDomElement:
        """creates optionally populated snippet node

        Args:
            snip_key (str, optional): Defaults to ''.
            snip_info (str, optional): Defaults to ''.
            snip_usage (str, optional):  Defaults to ''.
            translations (dict, optional): Defaults to {}.

        Returns:
            QDomElement
        """
        snippet_node = self.snippets_dom_doc.createElement("snippet")
        snippet_node.setAttribute("snip_key", snip_key)

        update_messages = []

        for lan in self.languages:
            trans_node = self.snippets_dom_doc.createElement("trans")
            trans_node.setAttribute("lan", lan)

            trans = translations.get(lan, "")

            # avoids invalid XML:
            if "]]>" in trans:
                # https://www.w3.org/TR/REC-xml/#NT-CDEnd
                # "]]>" within CDATA-Section is invalid XML
                update_messages.append(f"replaced CDEnd ']]>' in translation '{lan}' with '##CDEnd##', which will be re-replaced on usage...")
                trans = re.sub(r"]]>", "##CDEnd##", trans)

            trans_node.appendChild(self.snippets_dom_doc.createCDATASection(trans))
            snippet_node.appendChild(trans_node)

        # storing "<![CDATA[]]>" within CDATA-Section creates invalid XML
        if "]]>" in snip_info:
            # https://www.w3.org/TR/REC-xml/#NT-CDEnd
            # "]]>" within CDATA-Section is invalid XML
            update_messages.append(f"replaced CDEnd ']]>' in Snip-Info with '##CDEnd##', which will be re-replaced on usage...")
            snip_info = re.sub(r"]]>", "##CDEnd##", snip_info)


        self.qlbl_update_messages.setText("\n".join(update_messages))

        snip_info_node = self.snippets_dom_doc.createElement("snip_info")
        snip_info_node.appendChild(self.snippets_dom_doc.createCDATASection(snip_info))
        snippet_node.appendChild(snip_info_node)

        snip_usages_node = self.snippets_dom_doc.createElement("snip_usages")
        snip_usages_node.appendChild(
            self.snippets_dom_doc.createCDATASection(snip_usage)
        )
        snippet_node.appendChild(snip_usages_node)

        return snippet_node

    def st_delete_snippet(self,item:QStandardItem):
        """delete snippet from dom-doc

        Args:
            item (QStandardItem): clicked item from self.qtv_snip_dict, snip_key comes from UserRole
        """
        # Rev. 2026-09-15

        snip_key = item.data(Qt.ItemDataRole.UserRole)

        if snip_key:
            snippet_node = self.find_snippet(snip_key)
            if snippet_node:
                dialog_result = QMessageBox.question(
                    self,
                    "Delete Snippet",
                    f"Delete Snippet '{snip_key}'?",
                    buttons=QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Abort,
                    defaultButton=QMessageBox.StandardButton.Yes,
                )

                if dialog_result == QMessageBox.StandardButton.Yes:

                    snippet_node.parentNode().removeChild(snippet_node)
                    self.sys_save_dom_doc()

                    # no refresh QTableWidget, but set row disabled to keep selection and order
                    # self.st_reload()

                    self.qlbl_update_messages.setText(f"Snippet '{snip_key}' deleted")

                    for col in range(self.qtv_snip_dict.model().columnCount()):
                        cur_item = self.qtv_snip_dict.model().item(item.index().row(),col)
                        if cur_item:
                            cur_item.setEnabled(False)

                    #also disable indexWidget with delete-QToolButton
                    index_widget = self.qtv_snip_dict.indexWidget(item.index())
                    index_widget.setDisabled(True)

            else:
                # perhaps already deleted, the QToolButton inside the CellWidget is not disabled
                pass

        else:
            QMessageBox.info(
                self,
                "Delete Snippet",
                "No Snippet selected",
                buttons=QMessageBox.StandardButton.Ok,
                defaultButton=QMessageBox.StandardButton.Ok,
            )


    def st_register_snippet_edit(self):
        """triggered by any edits, sets flag-variable snippet_modified to True to avoid accidental overwriting"""
        # Rev. 2026-09-15
        self.snippet_modified = True

    def st_selection_changed(
        self, selected_items: QItemSelection, deselected_items: QItemSelection
    ):
        """triggered by new (single-row) selection in self.qtv_snip_dict.selectionModel()

        Args:
            selected_items (QItemSelection)
            deselected_items (QItemSelection): not used
        """
        # Rev. 2026-09-15
        if len(selected_items.indexes()) > 0:
            first_selected_index = selected_items.indexes()[0]
            snip_key = first_selected_index.data(Qt.ItemDataRole.UserRole)
            self.st_edit_snippet(snip_key)

    def st_edit_snippet(self, snip_key: str):
        """shows the snippet-metas in edit-form

        Args:
            snip_key (str): _description_
        """
        # Rev. 2026-09-15
        if self.edit_snip_key and self.snippet_modified:
            result_button = QMessageBox.question(
                self,
                "SnipDict Save edits",
                f"Snippet '{self.edit_snip_key}' was modified, save edits?",
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                defaultButton=QMessageBox.StandardButton.Yes,
            )
            if result_button == QMessageBox.StandardButton.Yes:
                self.st_save_snippet()
            else:
                return

        self.snippet_modified = False
        self.edit_snip_key = None

        snippet_node = self.find_snippet(snip_key)

        if snippet_node:
            self.edit_snip_key = snip_key

            translations = {}

            child_nodes = snippet_node.childNodes()

            for node_idx in range(child_nodes.size()):
                child_node = child_nodes.at(node_idx)
                if child_node.nodeName() == "trans":
                    lan = child_node.toElement().attribute("lan")
                    snip_content = child_node.firstChild().toText().data()
                    # re-replace CDEnd, see SnipDictEditor.create_snippet_node
                    snip_content = re.sub(r"##CDEnd##", "]]>", snip_content)
                    translations[lan] = snip_content

            rc = 0
            with QSignalBlocker(self.qtw_snippet_translations):
                self.qtw_snippet_translations.setRowCount(len(self.languages))
                for lan in self.languages:
                    qtw_lan = QTableWidgetItem(lan)
                    # first column with en/de/fr... => not editable
                    qtw_lan.setFlags(qtw_lan.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.qtw_snippet_translations.setItem(rc, 0, qtw_lan)
                    self.qtw_snippet_translations.setItem(
                        rc, 1, QTableWidgetItem(translations.get(lan, ""))
                    )
                    rc += 1

            snip_info = (
                snippet_node.firstChildElement("snip_info").firstChild().toText().data()
            )
            # re-replace CDEnd, see SnipDictEditor.create_snippet_node
            snip_info = re.sub(r"##CDEnd##", "]]>", snip_info)
            snip_usages = (
                snippet_node.firstChildElement("snip_usages")
                .firstChild()
                .toText()
                .data()
            )

            self.qle_snip_key.setText(snip_key)
            with QSignalBlocker(self.qpte_snip_info):
                self.qpte_snip_info.setPlainText(snip_info)

            self.qpte_snip_usages.setPlainText(snip_usages)

            self.qpb_save_edits.setEnabled(True)

    def scan_all_usages(self) -> str:
        """scans a list of files for usage of any snippet by searching snip_key
        writes this usage (file + line) in snippet-node <snip_usages>
        dom-doc is modified and saved
        """
        # Rev. 2026-09-15
        snippet_nodes = self.snippets_dom_doc.elementsByTagName("snippet")
        for snippet_node in (snippet_nodes.at(i) for i in range(snippet_nodes.size())):
            snip_key = snippet_node.toElement().attribute("snip_key")

            snip_usage = "\n".join(self.scan_usage(snip_key))
            snippet_node.namedItem("snip_usages").firstChild().setNodeValue(snip_usage)

        self.sys_save_dom_doc()

    def scan_usage(self, snip_key: str) -> list:
        """scans a list of files for usage of snippet defined by snip_key
        returns usages (file + line) or error-hint, if file was not found

        Args:
            snip_key (str): identifier

        Returns:
            list: usages
        """
        # Rev. 2026-09-15
        usages = []

        for scan_file in self.scan_files:
            scan_path_posix = Path(os.path.dirname(__file__)).parent / scan_file

            if scan_path_posix.is_file():

                with scan_path_posix.open() as f:
                    num_hits = 0
                    l_no = 0
                    for line in f:
                        l_no += 1

                        search_string_single_quote = f"'{snip_key}'"
                        search_string_double_quote = f'"{snip_key}"'
                        if (
                            search_string_single_quote in line
                            or search_string_double_quote in line
                        ):
                            num_hits += 1
                            # append file and line-number
                            lpad = str(l_no).rjust(6, " ")
                            usages.append(f"{scan_file} # {lpad}")

            else:
                usages.append(f"[!] file '{scan_file}' not found")

        return usages

    def sys_save_dom_doc(self):
        """writes snippets_dom_doc to file"""
        # Rev. 2026-09-15
        ba_dom_doc = QByteArray()
        buffer = QBuffer(ba_dom_doc)
        buffer.open(QIODevice.OpenModeFlag.ReadWrite)
        # important: save only the document-Element, else XML invalid...
        #  2  x <?xml version='1.0' encoding='UTF-8'?>
        # no <!DOCTYPE snippets...
        self.snippets_dom_doc.documentElement().save(QTextStream(buffer), 4)

        ba_dom_doc_txt = ba_to_string(ba_dom_doc)

        ba_header_txt = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE snippets
[
    <!ELEMENT snippets (snippet*)>
    <!ELEMENT snippet (trans*,snip_info,snip_usages)>
    <!ELEMENT trans (#PCDATA)>
    <!ELEMENT snip_info (#PCDATA)>
    <!ELEMENT snip_usages (#PCDATA)>
    <!ATTLIST snippet snip_key ID #REQUIRED>
    <!ATTLIST trans lan CDATA #REQUIRED>
]>"""

        new_file = Path(self.snippets_path)
        # Create this file with the given access mode, if it doesn't exist.
        new_file.touch()
        new_file.write_text(ba_header_txt + ba_dom_doc_txt,"utf-8")

    def find_snippet(self, search_snip_key: str)->QDomNode:
        """find snippet by its identify-attribute "snip_key"

        Args:
            search_snip_key (str)

        Returns:
            _type_: _description_
        """
        snippet_nodes = self.snippets_dom_doc.elementsByTagName("snippet")
        for snippet_node in (snippet_nodes.at(i) for i in range(snippet_nodes.size())):
            snip_key = snippet_node.toElement().attribute("snip_key")
            if snip_key == search_snip_key:
                return snippet_node

    def get_unique_id(self, in_str: str) -> tuple:
        """ensures user-defined string valid for usage as unique id-attribute
        NCName => "non-colonized name"
        see https://stackoverflow.com/questions/1631396/what-is-an-xsncname-type-and-when-should-it-be-used
        Args:
            in_str (str): the value for the id-attribute
        Returns:
            tuple (bool,error_msg)
        """
        # Rev. 2026-09-15
        if isinstance(in_str, str) and in_str != "":
            out_str = str(in_str)

            # replace white-space-characters
            out_str = re.sub(r"\s", "_", out_str)

            # replace non word characters
            out_str = re.sub(r"\W", "_", out_str)

            # prepend underscore for numbers as first character
            out_str = re.sub(r"(^[0-9])", r"_\1", out_str)

            if out_str == in_str:

                # check uniqueness with list of already used ids
                check_nodes = self.snippets_dom_doc.elementsByTagName("snippet")
                used_atts = []
                for check_node in (
                    check_nodes.at(i) for i in range(check_nodes.size())
                ):
                    used_atts.append(check_node.toElement().attribute("snip_key"))

                if out_str not in used_atts:
                    return True, None
                else:
                    return False, "Value not unique"
            else:
                return (
                    False,
                    "Value not valid (no white-spaces, no non-words, no starting numbers)",
                )

        else:
            return False, "Empty Value"


class ClickableQLineEdit(QLineEdit):
    """fixes the missing pressed-signal on QLineEdit
    usage here:
    read-only QLineEdit with path to a gpkg-file, the click on the widget is intercepted and instead opens a QT-file-dialog to select a gpkg-file
    """
    # Rev. 2026-09-15


    # "fake" events, which can be connected to the desired slot-method
    pressed = pyqtSignal(bool)
    enter_pressed = pyqtSignal(bool)

    def __init__(self, parent: QWidget = None):
        """Constructor, original __init__ plus event-filter

        Args:
            parent (QWidget): Parent-Object in Qt-Hierarchy
        """
        # Rev. 2026-09-15
        super().__init__(parent)
        self.installEventFilter(self)

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        """derived function called on any event, Note: installEventFilter has to be called before

        Args:
            source (QObject): the emitting Qt-Object, in this case self == ClickableQLineEdit-instance
            event (QEvent): the filtered event, any type, see https://doc.qt.io/qt-6/qevent.html
                further actions depend on event.type,
                here: clickable => MouseButtonPress

        Returns:
            bool: either the below defined event.type-specific (MouseButtonPress) or the result super()-eventFilter for any other event-type
        """
        # Rev. 2026-09-15

        if source == self and event.type() == QEvent.Type.MouseButtonPress:
            # emit the "fake" pressed event, which is connected to the desired slot-method
            self.pressed.emit(True)
            return False
        elif (
            source == self
            and event.type() == QEvent.Type.KeyRelease
            and (event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return)
        ):
            self.enter_pressed.emit(True)
            return False
        else:
            # delegate all other events to default-handler
            return super().eventFilter(source, event)


if __name__ == "__main__":
    app = QApplication([])
    app.setQuitOnLastWindowClosed(True)
    app.setWindowIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOkButton))
    my_mw = SnipDictEditor()
    my_mw.show()
    sys.exit(app.exec())
