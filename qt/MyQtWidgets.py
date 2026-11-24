#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Some derived QtWidgets

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

from pathlib import Path

from qgis.PyQt.QtXml import QDomDocument, QDomNode

import os, time, re

from typing import Any, Generator

import collections.abc

# Note: qgis.PyQt will import Qt5 or Qt6 depending on installed version!

from qgis.PyQt.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QTreeView,
    QAbstractItemView,
    QTextBrowser,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QSizePolicy,
    QLabel,
    QStyle,
    QToolTip,
    QProxyStyle,
    QStyleOption,
    QListWidget,
    QGroupBox,
)

from qgis.PyQt.QtCore import (
    Qt,
    pyqtSignal,
    QObject,
    QEvent,
    QSize,
    QMimeData,
    QModelIndex,
    QItemSelectionModel,
    QTimer,
    QRect,
    QPoint,
    QAbstractItemModel,
)

from qgis.PyQt.QtGui import (
    QIcon,
    QColor,
    QStandardItem,
    QStandardItemModel,
    QDropEvent,
    QDragMoveEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QPalette,
    QFont,
    QTextOption,
    QMouseEvent,
    QFontMetrics,
    QPainter,
    QFontDatabase,
    QPixmap,
)


from typing import Any

from LayerLib.tools.MyTools import (
    get_resource_node,
    get_absolute_path,
    show_log_message,
    # debug_print,
    # debug_print_dom_node,
    ba_to_string,
)

from LayerLib.tools.MyConstants import MY_DICT, QT_ROLES, ICON_DIR, CONTAINER_EXTENSIONS

from LayerLib import LayerLib

# QGis 3.44.7 => QT_VERSION: '5.15.13' PYQT_VERSION: '5.15.10'
# QGIS 4.0.2-Norrköping => QT_VERSION: '6.10.2' PYQT_VERSION: '6.10.2'

# print(QT_VERSION_STR,PYQT_VERSION_STR)


class QGroupBoxExpandable(QGroupBox):
    """QGroupBox with clickable icon and toggle-functionality"""

    # Rev. 2026-11-22

    _min_height = 20
    _max_height = 12345

    def __init__(
        self, title: str = "", initially_opened: bool = False, parent: QWidget = None
    ):
        """Constructor

        Args:
            title (str): Title-Text
            initially_opened (bool): initially show/hide the Group-Box, defaults False
            parent (QWidget): Parent-Object in Qt-Hierarchy
        """
        # Rev. 2026-11-22
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setStyle(self.GroupBoxProxyStyle())
        self.toggled.connect(self.s_toggle)
        # internal used styleSheet for QGroupBox has bold font
        # self.setStyleSheet("QGroupBox { font-weight: Normal; } ")

        # self.setChecked triggers s_toggle
        if initially_opened:
            self.setChecked(True)
        else:
            self.setChecked(False)

    class GroupBoxProxyStyle(QProxyStyle):
        """QProxyStyle to make QGroupbox expandable
        see:
        https://stackoverflow.com/questions/55977559/changing-qgroupbox-checkbox-visual-to-an-expander
        """

        # Rev. 2026-11-22

        def drawPrimitive(
            self,
            element: QStyle.PrimitiveElement,
            option: QStyleOption,
            painter: QPainter,
            widget: QWidget,
        ):
            # Rev. 2026-11-22
            """derived from super() (QProxyStyle)

            Args:
                element (QStyle.PrimitiveElement): Qt-internal Element inside the widget, here: PE_IndicatorCheckBox inside a QGroupBox
                option (QStyleOption): Style the PrimitiveElement
                painter (QPainter): Draw the PrimitiveElement
                widget (QWidget): Parent-Widget for the PrimitiveElement, here: QGroupBox
            """
            if element == QStyle.PrimitiveElement.PE_IndicatorCheckBox and isinstance(
                widget, QGroupBox
            ):
                # PE_IndicatorCheckBox inside a QGroupBox
                # paint a PE_IndicatorArrowDown rsp. PE_IndicatorArrowRight into widget dependend on isChecked()
                if widget.isChecked():
                    super().drawPrimitive(
                        QStyle.PrimitiveElement.PE_IndicatorArrowDown,
                        option,
                        painter,
                        widget,
                    )
                else:
                    super().drawPrimitive(
                        QStyle.PrimitiveElement.PE_IndicatorArrowRight,
                        option,
                        painter,
                        widget,
                    )
            else:
                # paint all PrimitiveElement != PE_IndicatorCheckBox in widgets != QGroupBox
                super().drawPrimitive(element, option, painter, widget)

    def s_toggle(self, status: bool):
        """Toggle Group-Box in Dialog

        Args:
            status (bool): isChecked()-State
        """
        # Rev. 2026-11-22
        if status:
            self.setMaximumHeight(self._max_height)
        else:
            self.setMaximumHeight(self._min_height)


class MyQLWi(QListWidget):
    """Derived QListWidget with checkboxes for Sub-Layer-Selection"""

    # Rev. 2026-11-22

    class MyHeightDelegate(QStyledItemDelegate):
        """Subclass Delegate to increase item height"""

        # Rev. 2026-11-22
        def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
            """return super().sizeHint(...) with increased height

            Args:
                option (QStyleOptionViewItem)
                index (QModelIndex)

            Returns:
                QSize: original width, increased height
            """
            size = super().sizeHint(option, index)
            size.setHeight(size.height() + 5)
            return size

    def __init__(self, parent: QWidget = None):
        """Constructor

        Args:
            parent (QWidget, optional): Qt-Hierarchy. Defaults to None.
        """
        # Rev. 2026-11-22
        super().__init__(parent)
        self.setItemDelegate(MyQLWi.MyHeightDelegate())
        # no select, but use Check-Boxes
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)




class ClickableQLineEdit(QLineEdit):
    """fixes the missing pressed-signal on QLineEdit
    usage f.e for paths, click on the widget opens a file-dialog
    """

    # Rev. 2026-11-22

    # on MouseButtonPress emitted signal, which can be connected to the desired slot-method
    pressed = pyqtSignal(bool)

    def __init__(self, parent: QWidget = None):
        """Constructor, original __init__ plus event-filter

        Args:
            parent (QWidget): Parent-Object in Qt-Hierarchy
        """
        # Rev. 2026-11-22
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
        # Rev. 2026-11-22
        if source == self and event.type() == QEvent.Type.MouseButtonPress:
            # emit the pressed event, which can be connected to the desired slot-method
            self.pressed.emit(True)
            return False
        else:
            # all other events to default-handler
            return super().eventFilter(source, event)


class ClickableQLabel(QWidget):
    """QLabel with connectable pressed-signal and optional prepended icon"""

    # Rev. 2026-11-22

    # on MouseButtonPress emitted signal, which can be connected to the desired slot-method
    pressed = pyqtSignal()

    def __init__(self, text_content: str, parent: QWidget = None):
        """constructor

        Args:
            cursor Qt.CursorShape.PointingHandCursor
            parent (QWidget, optional): Qt-Hierarchy. Defaults to None.
        """
        super().__init__(parent)
        self.installEventFilter(self)

        self.setLayout(QHBoxLayout())

        self.icon_qlbl = QLabel()
        self.layout().addWidget(self.icon_qlbl)

        self.text_qlbl = QLabel(text_content)
        self.layout().addWidget(self.text_qlbl)

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        """applied via installEventFilter, emits the pressed-signal, triggered by click on icon and text

        Args:
            source (QObject)
            event (QEvent)

        Returns:
            bool: _description_
        """
        # Rev. 2026-11-22
        if source == self and event.type() == QEvent.Type.MouseButtonPress:
            # emit the pressed event, which can be connected to slot
            self.pressed.emit()
            return False
        else:
            # delegate all other events to default-handler
            return super().eventFilter(source, event)

    def add_icon(
        self,
        icon_path: str,
        tool_tip: str = None,
        cursor: Qt.CursorShape = None,
        icon_width: int = 15,
        icon_height: int = 15,
    ):
        """replace or set icon

        Args:
            icon_path (str): path to icon
            tool_tip (str, optional): ToolTip for icon only. Defaults to None.
            cursor (Qt.CursorShape, optional): f.e. Qt.CursorShape.PointingHandCursor. Defaults to None.
            icon_width (int, optional): icon-width. Defaults to 15.
            icon_height (int, optional): icon-height. Defaults to 15.

        Raises:
            FileNotFoundError: if icon_path is not found
        """
        # Rev. 2026-11-22
        if os.path.isfile(icon_path):
            self.icon_qlbl.setFixedSize(QSize(icon_width, icon_height))
            self.icon_qlbl.setPixmap(
                QPixmap(icon_path).scaled(
                    QSize(icon_width, icon_height),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

            # self.setCursor(Qt.CursorShape.ArrowCursor)
            # cursor applied to icon only, but pressed-signal emitted from whole widget
            if cursor:
                self.icon_qlbl.setCursor(cursor)

            if tool_tip:
                self.icon_qlbl.setToolTip(tool_tip)
        else:
            raise FileNotFoundError(f"Icon-Path '{icon_path}' invalid")


class MyQComboBox(QComboBox):
    """pimped QComboBox"""

    # Rev. 2026-11-22

    def __init__(self, parent: QWidget):
        """constructor
        Args:
            parent (QWidget): Qt-Hierarchy
        """
        # Rev. 2026-11-22
        super().__init__(parent)

    def add_item(
        self, text: str, data: Any = None, tooltip: str = None, enabled: bool = True
    ):
        """derived addItem-method with some data

        Args:
            text (str): item.data(0) =>  Qt.ItemDataRole.DisplayRole
            data (Any, optional): item.data(256) => Qt.ItemDataRole.UserRole
            enabled (bool, optional): Defaults to True.
        """
        # Rev. 2026-11-22
        item = QStandardItem()
        item.setText(text)
        # 256 => Qt.ItemDataRole.UserRole
        item.setData(data, 256)
        item.setEnabled(enabled)
        if tooltip:
            item.setToolTip(tooltip)

        self.model().appendRow(item)

    def select_option(self, data: Any):
        """select an option in this QComboBox by data == Qt.ItemDataRole.UserRole 256
        Note: blockSignals(True/False) must be called before/after if setCurrentIndex-signal should be avoided

        Args:
            data (Any)
        """
        # Rev. 2026-11-22
        self.setCurrentIndex(-1)
        for c_idx in range(self.model().rowCount()):
            if self.model().item(c_idx).data(256) == data:
                self.setCurrentIndex(c_idx)
                break


class MyQTreeView(QTreeView):
    """QTreeView for resource-folder-tree"""

    # Rev. 2026-11-22

    # signals for dragged/dropped objects, which can be connected and evaluated outside of the widget
    # signal triggered by dragEnterEvent
    drag_enter = pyqtSignal(QDragEnterEvent)

    # signal triggered by dragMoveEvent
    drag_move = pyqtSignal(QDragMoveEvent)

    # signal triggered by dropEvent
    # returns the event, evt_val, evt_val_type, evt_index (with data QT_ROLES.FOLDER_ID or QT_ROLES.RESOURCE_ID)
    dropped = pyqtSignal(QDropEvent, str, str, QModelIndex)

    def __init__(self, layer_lib: LayerLib, parent=None):
        """constructor

        Args:
            layer_lib (LayerLib): back-reference to plugin
            parent (QWidget, optional): Qt-Hierarchy. Defaults to None.
        """
        # Rev. 2026-11-22

        super().__init__(parent)

        self.setStyle(self.MyProxyStyle())

        self.layer_lib = layer_lib

        # not double-click-edit-functionality in TreeView
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # https://doc.qt.io/qt-5/qabstractitemview.html#SelectionMode-enum
        # Default: SingleSelection => only one cell rsp. row
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # https://doc.qt.io/qt-5/qabstractitemview.html#SelectionBehavior-enum
        # SelectItems/SelectRows/SelectColumns
        # only for manual selection via click or cursor
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # in EditResourceDialog the layer-description is shown in QPlainTextEdit, which allows line-breaks
        # the delegates force vertical alignment of text and icons, looks nice with non-uniform row heights
        # => matter of taste
        self.setUniformRowHeights(False)

        # note: MyStandardItem implement custom sort function __lt__
        self.setSortingEnabled(True)

        # matter of taste...
        self.header().setStretchLastSection(True)

        # delegates, stored as property, else garbage-collected and no effect
        self.delegates = {}

        # animated (slow) sliding to show child-nodes
        self.setAnimated(True)

        # visual focus on whole selected row (all columns, incl. tree-padding in column 0)
        # shown only with focussed dialog
        self.setAllColumnsShowFocus(True)

        # drop-down-icon in "Root"-row
        self.setRootIsDecorated(True)

        # overwrite default-highlight-color, which will interfere with delegates (blue coloured gap between left TreeView-edge and tree-padded first column)
        # other palette-colors are overruled by delegates
        pal = self.palette()
        hightlight_brush = pal.brush(QPalette.ColorRole.Highlight)
        hightlight_brush.setColor(QColor("#ffffff"))
        pal.setBrush(QPalette.ColorRole.Highlight, hightlight_brush)
        self.setPalette(pal)

        # tricky: delayed open of hovered folder
        self.delayed_expand_idx = None
        self.delayed_expand_qtmr = QTimer(self)
        self.delayed_expand_qtmr.setSingleShot(True)
        self.delayed_expand_qtmr.timeout.connect(self.delayed_expand)

        # Drag&Drop-Settings are set dynamically
        # QAbstractItemView.DragDropMode https://doc.qt.io/qt-6/qabstractitemview.html#DragDropMode-enum
        # https://doc.qt.io/qt-6/qabstractitemview.html#DragDropMode-enum
        # self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

        # https://doc.qt.io/qt-6/qwidget.html#acceptDrops-prop
        # necessary for internal drag&drop
        # self.viewport().setAcceptDrops(True)

        # symbolize target with marker
        # self.setDropIndicatorShown(True)

        # necessary to get target-folder for internal reorder
        # self.setMouseTracking(True)

        # already init model without data to register delegates with connected signals
        self.setModel(RecursiveXMLModel(layer_lib))

        # three columns: Layer/Folder Description Path

        self.model().setHorizontalHeaderItem(
            0, QStandardItem(MY_DICT.tr("qtrv_header_0"))
        )

        self.model().setHorizontalHeaderItem(
            1, QStandardItem(MY_DICT.tr("qtrv_header_1"))
        )

        self.model().setHorizontalHeaderItem(
            2, QStandardItem(MY_DICT.tr("qtrv_header_2"))
        )

        # enable/disable add-resource-to-project-icon (1) depending on QT_ROLES.ENABLED in MyStandardItem
        # enable/disable delete-icon (2) depending on QT_ROLES.EDITABLE in MyStandardItem
        self.delegates[0] = LeftSideIconsDelegateFolderLayer(
            40,
            False,
            {0: None, 2: QT_ROLES.EDITABLE},
            60,
            True,
            {0: None, 1: QT_ROLES.ENABLED, 2: QT_ROLES.EDITABLE},
        )
        self.setItemDelegateForColumn(0, self.delegates[0])

        self.delegates[1] = LeftSideIconsDelegateFolderLayer()
        self.setItemDelegateForColumn(1, self.delegates[1])

        self.delegates[2] = LeftSideIconsDelegateFolderLayer()
        self.setItemDelegateForColumn(2, self.delegates[2])


        # store visual settings (column-widths, selections) of QTreeView for restore after data-reload
        self.qtrv_pre_settings = dict()

    def store_pre_settings(self):
        """qtrv_pre_settings with metadata for later restore
        must be called before model is cleared"""
        # Rev. 2026-11-23
        self.qtrv_pre_settings = dict()
        # self.model().rowCount() == 0 on first load
        if self.model() and self.model().rowCount():

            self.qtrv_pre_settings["old_indicator"] = (
                self.header().sortIndicatorSection()
            )
            self.qtrv_pre_settings["old_order"] = (
                self.header().sortIndicatorOrder()
            )

            # https://doc.qt.io/qt-6/qscrollbar.html
            self.qtrv_pre_settings["old_scroll_position_h"] = (
                self.horizontalScrollBar().value()
            )
            self.qtrv_pre_settings["old_scroll_position_v"] = (
                self.verticalScrollBar().value()
            )

            self.qtrv_pre_settings["expended_folder_ids"] = {}
            self.qtrv_pre_settings["selected_folder_ids"] = []
            folder_items = self.extract_recursive_items(
                None,
                0,
                QT_ROLES.FOLDER_ID,
            )
            for item in folder_items:
                folder_id = item.data(QT_ROLES.FOLDER_ID)
                self.qtrv_pre_settings["expended_folder_ids"][folder_id] = (
                    self.isExpanded(item.index())
                )

                if self.selectionModel().isSelected(
                    item.index()
                ):
                    self.qtrv_pre_settings["selected_folder_ids"].append(folder_id)

            self.qtrv_pre_settings["selected_resource_ids"] = []
            resource_items = self.extract_recursive_items(
                None,
                0,
                QT_ROLES.RESOURCE_ID,
            )
            for item in resource_items:
                resource_id = item.data(QT_ROLES.RESOURCE_ID)
                if self.selectionModel().isSelected(
                    item.index()
                ):
                    self.qtrv_pre_settings["selected_resource_ids"].append(resource_id)

            self.qtrv_pre_settings["old_column_widths"] = []
            for col_idx in range(
                self.model().columnCount()
            ):
                self.qtrv_pre_settings["old_column_widths"].append(
                    self.columnWidth(col_idx)
                )

    def restore_pre_settings(self):
        """restore qtrv_pre_settings after model is refreshed
        """
        # Rev. 2026-11-23
        if self.model() and self.model().rowCount() and self.qtrv_pre_settings:
            # restore previous sort:
            old_indicator = self.qtrv_pre_settings.get("old_indicator")
            old_order = self.qtrv_pre_settings.get("old_order")
            if old_indicator is not None and old_order is not None:
                self.sortByColumn(old_indicator, old_order)

            # restore previous expended or collapsed rows
            expended_folder_ids = self.qtrv_pre_settings.get("expended_folder_ids")

            if expended_folder_ids:
                folder_items = self.extract_recursive_items(
                    None,
                    0,
                    QT_ROLES.FOLDER_ID,
                )
                for item in folder_items:
                    folder_id = item.data(QT_ROLES.FOLDER_ID)
                    if folder_id in expended_folder_ids:
                        self.setExpanded(
                            item.index(), expended_folder_ids[folder_id]
                        )

            selected_folder_ids = self.qtrv_pre_settings.get("selected_folder_ids")
            if selected_folder_ids:
                folder_items = self.extract_recursive_items(
                    None,
                    0,
                    QT_ROLES.FOLDER_ID,
                )
                for item in folder_items:
                    folder_id = item.data(QT_ROLES.FOLDER_ID)
                    if folder_id in selected_folder_ids:
                        self.selectionModel().select(
                            item.index(),
                            QItemSelectionModel.SelectionFlag.Select
                            | QItemSelectionModel.SelectionFlag.Rows,
                        )

            selected_resource_ids = self.qtrv_pre_settings.get("selected_resource_ids")
            if selected_resource_ids:
                resource_items = self.extract_recursive_items(
                    None,
                    0,
                    QT_ROLES.RESOURCE_ID,
                )
                for item in resource_items:
                    resource_id = item.data(QT_ROLES.RESOURCE_ID)
                    if resource_id in selected_resource_ids:
                        self.selectionModel().select(
                            item.index(),
                            QItemSelectionModel.SelectionFlag.Select
                            | QItemSelectionModel.SelectionFlag.Rows,
                        )

            old_scroll_position_h = self.qtrv_pre_settings.get("old_scroll_position_h")

            if old_scroll_position_h is not None:
                self.horizontalScrollBar().setValue(
                    old_scroll_position_h
                )

            old_scroll_position_v = self.qtrv_pre_settings.get("old_scroll_position_v")
            if old_scroll_position_v is not None:
                self.verticalScrollBar().setValue(
                    old_scroll_position_v
                )

            old_column_widths = self.qtrv_pre_settings.get("old_column_widths")
            if old_column_widths:
                for col_idx, col_width in enumerate(old_column_widths):
                    self.setColumnWidth(
                        col_idx, col_width
                    )


        else:
            # fresh initialized => rowCount = 0
            self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
            self.setColumnWidth(0, 300)

        # refresh the trash-icons dependend on layer_lib.tool_mode
        editable_items = self.extract_recursive_items(
            None,
            0,
            QT_ROLES.EDITABLE,
        )

        for item in editable_items:
            item.setData(self.layer_lib.tool_mode == "reorder", QT_ROLES.EDITABLE)


    class MyProxyStyle(QProxyStyle):
        """https://web.archive.org/web/20250614212417/https://apocalyptech.com/linux/qt/qtableview/
        enhanced dropIndicator-visual-effect, whole row instead of single cell
        """

        # Rev. 2026-11-22

        def drawPrimitive(self, element, option, painter, widget=None):
            """
            Draw a line across the entire row rather than just the column
            we're hovering over.  This may not always work depending on global
            style - for instance I think it won't work on OSX.
            """
            # Rev. 2026-11-23
            if (
                element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemDrop
                and not option.rect.isNull()
            ):
                option_new = QStyleOption(option)
                option_new.rect.setLeft(0)
                if widget:
                    option_new.rect.setRight(widget.width())
                option = option_new
            super().drawPrimitive(element, option, painter, widget)

    def open_folder(self, folder_id: str):
        """open folder and all parents in MyQTreeView by folder_id, no folder selection
        Note:
            must be called *before* LayerLib.dlg_refresh_qtrv(), else no effect, because dlg_refresh_qtrv will apply settings with QTimer-delay

        Args:
            folder_id (str): ID of folder (should be unique), no Exceptions, if folder not found
        """
        # Rev. 2026-11-22

        # folder_id None oder NULL will open *all* folders, because extract_recursive_items then filters all items having this attribute with any value
        if folder_id:
            folder_items = self.extract_recursive_items(
                None, 0, QT_ROLES.FOLDER_ID, folder_id
            )
            for folder_item in folder_items:
                self.setExpanded(folder_item.index(), True)
                parent_item = folder_item.parent()
                # important to avoid endless-recursions: parent() returns *allways* an QModelIndex, but its row/col will get -1 if the root-node is reached
                while parent_item and parent_item.row() != -1:
                    self.setExpanded(parent_item.index(), True)
                    parent_item = parent_item.parent()

    def select_resource(self, resource_id: str):
        """select single resource in QTreeView:
        deselected and collaps all other (clearAll, collapseAll)
        select only one resource and open its branches

        Args:
            resource_id (str)
        """
        # Rev. 2026-11-23
        column_settings = [
            # first column, special role for layer-id
            [
                0,
                QT_ROLES.RESOURCE_ID,
                Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
            ]
        ]

        self.select_by_value(column_settings, resource_id, 1)

    def select_folder(self, folder_id: str):
        """select single folder in QTreeView:
        deselected and collaps all other (clearAll, collapseAll)
        select only one folder and open its branches
        folder is not opened

        Args:
            folder_id (str)
        """
        # Rev. 2026-11-22
        column_settings = [
            # first column, special role for folder-id
            [
                0,
                QT_ROLES.FOLDER_ID,
                Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
            ]
        ]
        self.select_by_value(column_settings, folder_id, 1)

    def select_resources(self, resource_ids: list) -> list:
        """scans the recursive data-model for resources with list of ids, selects the assigned rows and returns their row-indizes
        Folder-tree-branches are opened
        enclose with QtCore.QSignalBlocker() to avoid unwanted trigger of select-signals

        Args:
            resource_ids (list): list resource-ids

        Returns:
            list: found row-indizes
        """
        # Rev. 2026-11-22
        # first column, special role for layer-id
        col_idx = 0
        role_idx = QT_ROLES.RESOURCE_ID
        flags = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive

        self.collapseAll()
        if self.model():
            model = self.model()
            selection_model = self.selectionModel()
            selection_model.clearSelection()

            matches = []

            for resource_id in resource_ids:
                matches += model.match(
                    model.index(0, col_idx), role_idx, resource_id, -1, flags
                )

            for index in matches:
                # select whole row instead of single cell: QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows
                selection_model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )

                # and (re-)open the parent branches
                parent = index.parent()

                # important to avoid endless-recursions: parent() returns is *allways* an QModelIndex, but its row/col will get -1 if the root-node is reached
                while parent and parent.row() != -1:
                    self.setExpanded(parent, True)
                    parent = parent.parent()

            return matches

    def select_by_value(
        self, column_settings: list, select_value: Any, num_values: int = 1
    ) -> list:
        """scans the recursive data-model for a specific value, selects the assigned rows and returns their row-indizes
        Must be enclosed with QtCore.QSignalBlocker() to avoid unwanted trigger of select-signals
        opens Folder-Tree-branches

        Args:
            column_settings (list): list of lists [col_idx, role_idx, flags]
            select_value (Any): the compare-value (MatchExactly)
            num_values (int, optional): only one hit or multiple rows/cells, -1 => no limit. Defaults to 1.

        Returns:
            list: found row-indizes
        """
        # Rev. 2026-11-22
        self.collapseAll()
        if self.model():
            model = self.model()
            selection_model = self.selectionModel()
            selection_model.clearSelection()
            # find the matching row, returns only 1 match, MatchRecursive for TreeView
            # https://doc.qt.io/qt-5/qabstractitemmodel.html#match
            matches = []
            for column_setting in column_settings:
                col_idx = column_setting[0]
                role_idx = column_setting[1]
                flags = column_setting[2]

                matches += model.match(
                    model.index(0, col_idx), role_idx, select_value, num_values, flags
                )

            for index in matches:
                # select whole row instead of single cell: QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows
                selection_model.select(
                    index,
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )

                # and (re-)open the parent branches
                parent = index.parent()

                # important to avoid endless-recursions: parent() returns is *allways* an QModelIndex, but its row/col will get -1 if the root-node is reached
                while parent and parent.row() != -1:
                    self.setExpanded(parent, True)
                    parent = parent.parent()

            return matches

    # note on all drag&drop: bubble-up-behaviour seems to be influenced by dock-state of the dialog, docked => bubble-up to mainWindow
    def dragEnterEvent(self, evt: QDragEnterEvent):
        """subclassed, triggered on internal or external drag of an item over the Treeview

        Args:
            evt (QDragEnterEvent)
        """
        # Rev. 2026-11-22
        if self.pre_check_dragdrop_event(evt)[0]:
            # necessary to show DropIndicator and for later dragMoveEvent and dropEvent
            super().dragEnterEvent(evt)
            self.drag_enter.emit(evt)
            evt.accept()

    def dragLeaveEvent(self, evt: QDragLeaveEvent):
        """subclassed, trigggered by leave a dragged object

        Args:
            evt (QDragLeaveEvent)
        """
        # Rev. 2026-11-22
        self.delayed_expand_qtmr.stop()

    def dragMoveEvent(self, evt: QDragMoveEvent):
        """subclassed, triggered if a dragged item is moved over the target
        item can only be dropped with evt.accept()
        necessary for dropEvent

        Args:
            evt (QDragMoveEvent)
        """
        # Rev. 2026-11-22
        self.delayed_expand_qtmr.stop()

        if self.pre_check_dragdrop_event(evt)[0]:
            # necessary to show DropIndicator and for later dropEvent
            super().dragMoveEvent(evt)
            self.drag_move.emit(evt)
            evt.accept()

            # delayed open folder
            try:
                pos = evt.pos()
            except Exception:
                # Qt6, evt.position() => QPointF
                pos = evt.position().toPoint()

            idx = self.indexAt(pos)

            if idx.data(QT_ROLES.FOLDER_ID) and not self.isExpanded(idx):
                self.delayed_expand_idx = idx
                self.delayed_expand_qtmr.start(1000)

    def delayed_expand(self):
        """connected and delayed called by QTimer self.delayed_expand_qtmr
        opens the folder identified by self.delayed_expand_idx
        """
        # Rev. 2026-11-22
        if self.delayed_expand_idx and not self.isExpanded(self.delayed_expand_idx):
            self.setExpanded(self.delayed_expand_idx, True)

    def dropEvent(self, evt: QDropEvent):
        """subclassed, triggered with drop of dragged item on QTreeView
        QTreeView-internal drag&drop and external drag&drop of files/folders implemented

        NOTE: requires previously accepted dragEnterEvent and dragMoveEvent

        Args:
            evt (QDropEvent)
        """
        # Rev. 2026-11-22

        self.delayed_expand_qtmr.stop()
        evt_val, evt_val_type, evt_idx = self.pre_check_dragdrop_event(evt)
        if evt_val:
            self.dropped.emit(evt, evt_val, evt_val_type, evt_idx)

    def pre_check_dragdrop_event(
        self, evt: QDragEnterEvent | QDragMoveEvent | QDropEvent
    ) -> tuple:
        """pre-checks drag/drop-event on self.my_dialog.qtrv_layer_lib
        for self.layer_lib.tool_mode == "reorder"

        Args:
            evt (QDragEnterEvent | QDragMoveEvent | QDropEvent)

        Returns:
            tuple(evt_val:str,evt_val_type:str,evt_idx:QModelIndex): event-value, its type (folder_id/resource_id/resource_path) and the model-index, where the event happened
            Note: these values are attached to the dropped-signal and evaluated in subsequent signal-connections
        """
        # Rev. 2026-11-22



        if self.layer_lib.tool_mode == "reorder":
            # delayed open folder
            try:
                pos = evt.pos()
            except Exception:
                # Qt6, evt.position() => QPointF
                pos = evt.position().toPoint()

            evt_idx = self.indexAt(pos)



            if evt.mimeData().data("LayerLib/folder_id"):
                return (
                    ba_to_string(evt.mimeData().data("LayerLib/folder_id")),
                    "folder_id",
                    evt_idx,
                )
            elif evt.mimeData().data("LayerLib/resource_id"):
                # TreeView-internal drag&drop of resource-item
                return (
                    ba_to_string(evt.mimeData().data("LayerLib/resource_id")),
                    "resource_id",
                    evt_idx,
                )
            elif evt.mimeData().hasUrls():
                # drag&drop from file-system or chrome/firefox/edge...-browser-adress-bar
                # accepted: single local url with container-suffix
                if len(evt.mimeData().urls()) == 1:
                    url = evt.mimeData().urls()[0]
                    if url.isLocalFile():
                        url_path = url.toLocalFile()

                        # in windows path is something like /C:/Users/..., which is not usable for Path
                        # simulating a file-system-root-element like in reasonable operating systems?
                        if url_path[2] == ":":
                            url_path = url_path.lstrip("/")

                        resource_path_posix = Path(url_path)

                        if resource_path_posix.exists():
                            if resource_path_posix.is_file():
                                file_suffix = str.lower(
                                    resource_path_posix.suffix.lstrip(".")
                                )
                                if file_suffix in CONTAINER_EXTENSIONS:
                                    return (
                                        resource_path_posix.as_posix(),
                                        "resource_path",
                                        evt_idx,
                                    )

            elif evt.mimeData().hasFormat("application/qgis.layertree.layerdefinitions"):
                # drag&drop layer/layer-group from Layers-Panel
                # note: must be checked *before* application/x-vnd.qgis.qgis.uri, because dropping from Layers-Panel obviously has both mimeData!
                return (
                    ba_to_string(evt.mimeData().data("application/qgis.layertree.layerdefinitions")),
                    "layerdefinitions",
                    evt_idx,
                )

            elif evt.mimeData().hasFormat("application/x-vnd.qgis.qgis.uri"):
                # drag&drop qlr-file from QGis-Browser-Panel...
                # note: must be checked *after* application/qgis.layertree.layerdefinitions, because dropping from Layers-Panel obviously has both mimeData!
                # same procedure as MyTools.parse_browser_panel_layers
                # check, if it was a container-file:
                uri_bya = evt.mimeData().data("application/x-vnd.qgis.qgis.uri")

                uri_bya_parts = []
                bya_part = bytes()

                # quite complicated: the byte-array can be splitted by a sequence of 5 bytes matching
                re_match = re.compile(rb"[\x00]{2}[\x00-\xff]{2}[\x00]{1}")
                for idx, by in enumerate(uri_bya):

                    if idx < len(uri_bya) - 5:
                        # chunk of 5 bytes
                        by_5 = uri_bya[idx : idx + 5]

                        if re.match(re_match, by_5):
                            # don't append the first match at the very beginning of uri_bya
                            if len(bya_part):
                                # strip the matching 5 bytes
                                uri_bya_parts.append(bya_part[5:])
                            # skip iteration
                            idx += 5
                            # new part:
                            bya_part = bytes()

                    bya_part += by

                # append the last part
                uri_bya_parts.append(bya_part[5:])

                if len(uri_bya_parts) == 1:
                    uri_decoded = ba_to_string(uri_bya_parts[0])

                    # note: uri is seperated by colons, but windows uses ':' in paths, masked as "\:"
                    # f.e. 'vector:ogr:2022-01-20 EZG Malefinkbach:C\:/temp/...'
                    # workaround to get 'C:/temp/...'
                    uri_decoded = uri_decoded.replace(r"\:", "#escaped_colon#")
                    uri_parts = uri_decoded.split(":")
                    uri_parts = [
                        uri_part.replace("#escaped_colon#", ":")
                        for uri_part in uri_parts
                    ]

                    uri_type = uri_parts[0]

                    if uri_type in ["custom", "project"]:
                        # custom: qlr-file
                        # project: qgs/qgz
                        uri_path = uri_parts[3]

                        # File or directory
                        resource_path_posix = Path(uri_path)

                        if resource_path_posix.is_file():

                            file_suffix = str.lower(
                                resource_path_posix.suffix.lstrip(".")
                            )
                            if file_suffix in CONTAINER_EXTENSIONS:
                                return (
                                    resource_path_posix.as_posix(),
                                    "resource_path",
                                    evt_idx,
                                )


        # allways return a tuple
        return None, None, None

    def get_selected_folder_id(self) -> str:
        """returns id of first selected folder f.e. as default-pre-selection for new layer/folder

        Returns:
            str: folder-id
        """
        # Rev. 2026-11-22

        # default-return-value: root-folder
        folder_id = self.layer_lib.treeview_dom_doc.documentElement().attribute("id")

        for idx in self.selectedIndexes():
            if idx.data(QT_ROLES.FOLDER_ID):
                # or the selected folder
                folder_id = idx.data(QT_ROLES.FOLDER_ID)
            elif idx.data(QT_ROLES.RESOURCE_ID):
                # or folder of selected layer
                resource_node = get_resource_node(
                    self.layer_lib.treeview_dom_doc, idx.data(QT_ROLES.RESOURCE_ID)
                )
                if resource_node:
                    folder_id = (
                        resource_node.toElement()
                        .parentNode()
                        .toElement()
                        .attribute("id")
                    )

        return folder_id

    def load_data(self, treeview_dom_doc: QDomDocument):
        """load/replace model-data by DomDocument containing nested folders and layers
        called on first init and with each data-reload, f.e. after edits

        Args:
            treeview_dom_doc (QDomDocument): parsed XML
        """
        # Rev. 2026-11-22
        if self.model():
            self.store_pre_settings()

            self.model().removeRows(0, self.model().rowCount())

            self.treeview_dom_doc = treeview_dom_doc

            folder_ids = []

            # pre-check uniqueness of folder- and layer-ids
            folder_nodes = self.treeview_dom_doc.elementsByTagName("folder")
            for folder_node in (folder_nodes.at(i) for i in range(folder_nodes.size())):
                folder_id = folder_node.toElement().attribute("id")

                if folder_id in folder_ids:
                    show_log_message(
                        "WARNING",
                        f"Folder-ID-Duplicate: id '{folder_id}' in row #{folder_node.lineNumber()}...",
                        None,
                        True,
                    )

                folder_ids.append(folder_id)

            resource_ids = []
            layer_nodes = self.treeview_dom_doc.elementsByTagName("resource")
            for layer_node in (layer_nodes.at(i) for i in range(layer_nodes.size())):
                resource_id = layer_node.toElement().attribute("id")

                # Duplikat-Check:
                if resource_id in resource_ids:
                    show_log_message(
                        "WARNING",
                        f"Layer-ID-Duplicate: id '{resource_id}' in row #{layer_node.lineNumber()}...",
                        None,
                        True,
                    )

                resource_ids.append(resource_id)

            # Rest is done recursively starting with root-folder
            self.load_data_recursive(
                self.model().invisibleRootItem(), treeview_dom_doc.documentElement()
            )

            # Folder-Rows use only first column for icons and label, but must have all items populated to enable sorting
            folder_items = self.extract_recursive_items(
                None, 0, QT_ROLES.FOLDER_ID
            )
            for folder_item in folder_items:
                self.setFirstColumnSpanned(
                    folder_item.index().row(), folder_item.index().parent(), True
                )

            QTimer.singleShot(10, self.restore_pre_settings)
        else:
            raise Exception("QTreeView without model")

    def load_data_recursive(self, parent: QStandardItem, folder_node: QDomNode):
        """recursive part of load_data

        Args:
            parent (QStandardItem): parent QSandardItem for self-recursion
            folder_node (QDomNode): current node from DomDocument
        """
        # Rev. 2026-11-22
        folder_id = folder_node.toElement().attribute("id")

        folder_label = folder_node.namedItem("label").firstChild().toText().data()

        folder_description = (
            folder_node.namedItem("description").firstChild().toText().data()
        )

        folder_item_0 = MyStandardItem()
        folder_item_0.setData(folder_label, Qt.ItemDataRole.DisplayRole)
        folder_item_0.setData(folder_id, QT_ROLES.FOLDER_ID)
        folder_item_0.setData(folder_description, Qt.ItemDataRole.ToolTipRole)
        folder_item_0.setData(False, QT_ROLES.EDITABLE)
        # tricky faked alphabetical sort-value to prevent mixed sub-folders/layers
        folder_item_0.setData(f"a_{folder_label}", QT_ROLES.CUSTOM_SORT)
        # special style-defining role for delegate
        folder_item_0.setData("folder", QT_ROLES.STYLE)

        # fork to sub-nodes: layer or sub-folder
        child_nodes = folder_node.childNodes()

        for node_idx in range(child_nodes.size()):
            child_node = child_nodes.at(node_idx)

            if child_node.nodeName() == "resource":
                resource_id = child_node.toElement().attribute("id")

                resource_label = (
                    child_node.namedItem("label").firstChild().toText().data()
                )

                resource_description = (
                    child_node.namedItem("description").firstChild().toText().data()
                )
                resource_path = (
                    child_node.namedItem("path").firstChild().toText().data()
                )

                # disable items with invalid path-attributes or unsupported extensions
                resource_path_abs = get_absolute_path(
                    resource_path, self.layer_lib.treeview_source_path
                )

                enabled = False

                resource_suffix = ""

                if resource_path_abs:

                    resource_path_posix = Path(resource_path_abs)

                    resource_suffix = str.lower(resource_path_posix.suffix.lstrip("."))

                    enabled = resource_suffix in CONTAINER_EXTENSIONS

                # same tooltip for all items
                tool_tip = f"""Layer #{resource_id}\n\n{resource_label}\n\nPath:\n{resource_path}"""

                if resource_description and resource_description != resource_label:
                    tool_tip += f"""\n\n{resource_description}"""

                if not enabled:
                    tool_tip += f"""\n\nLayer disabled, path invalid or suffix not implemented..."""

                resource_item_0 = MyStandardItem()
                resource_item_0.setData(resource_label, Qt.ItemDataRole.DisplayRole)
                resource_item_0.setData(tool_tip, Qt.ItemDataRole.ToolTipRole)
                resource_item_0.setData(resource_id, QT_ROLES.RESOURCE_ID)
                resource_item_0.setData(enabled, QT_ROLES.ENABLED)
                resource_item_0.setData(False, QT_ROLES.EDITABLE)
                # same trick as above to prevent mixed sub-folders/layers
                resource_item_0.setData(
                    f"z_{folder_label}_{resource_label}", QT_ROLES.CUSTOM_SORT
                )
                # special style-defining role for delegate
                resource_item_0.setData("resource", QT_ROLES.STYLE)

                resource_item_1 = MyStandardItem()
                resource_item_1.setData(
                    resource_description, Qt.ItemDataRole.DisplayRole
                )
                resource_item_1.setData(tool_tip, Qt.ItemDataRole.ToolTipRole)
                resource_item_1.setData(resource_id, QT_ROLES.RESOURCE_ID)
                resource_item_1.setData("resource", QT_ROLES.STYLE)

                resource_item_2 = MyStandardItem()
                resource_item_2.setData(resource_path, Qt.ItemDataRole.DisplayRole)
                resource_item_2.setData(tool_tip, Qt.ItemDataRole.ToolTipRole)
                resource_item_2.setData(resource_id, QT_ROLES.RESOURCE_ID)
                resource_item_2.setData("resource", QT_ROLES.STYLE)

                folder_item_0.appendRow(
                    [resource_item_0, resource_item_1, resource_item_2]
                )
            elif child_node.nodeName() == "folder":
                # recursion for nested folder
                self.load_data_recursive(folder_item_0, child_node)

        # dummy items for columns 1-3, necessary in model to enable layer-sorts by these columns
        this_row_items = [folder_item_0, MyStandardItem(), MyStandardItem()]

        # add this row (folder_item_0 with layers and nested sub-folders)
        parent.appendRow(this_row_items)

    def extract_recursive_items(
        self, start_item: QStandardItem, col_idx: int, role: int = None, value: Any = None
    ) -> collections.abc.Iterable:
        """delivers QStandardItem(s) with specific role/col/value from (recursive) QStandardItemModel

        Args:
            start_item (QStandardItem): start search at this item, normally self.model().invisibleRootItem()
            col_idx (int): check QStandardItem only in this columns
            role (int): check this role
            value (Any, optional): check the value for this role, if omitted, all items are returned, that have any value != None for this role


        Returns:
            collections.abc.Iterable: [QStandardItem]

        Yields:
            tuple(QStandardItem)
        """
        # Rev. 2026-11-23
        if self.model():

            def recurse(parent: QStandardItem) -> Generator[QStandardItem, None, None]:
                """recursive part

                Args:
                    parent (QStandardItem)

                Yields:
                    Generator[QStandardItem, None, None]
                """
                # Rev. 2026-09-09

                for rc in range(parent.rowCount()):
                    # the filtered column
                    child_n = parent.child(rc, col_idx)
                    # can be None
                    if child_n:
                        if role is not None:
                            if value is not None:
                                if child_n.data(role) == value:
                                    # yield this child, if the role is used and equal to value
                                    yield (child_n)
                            else:
                                # yield this child, if the role is used independend from value
                                if child_n.data(role) is not None:
                                    yield (child_n)
                        else:
                            yield (child_n)

                    # column 0 in this row, contains the self-reference
                    child_0 = parent.child(rc, 0)
                    if child_0:
                        yield from recurse(child_0)



            if not isinstance(start_item, QStandardItem):
                start_item = self.model().invisibleRootItem()
            yield from recurse(start_item)
        else:
            raise Exception("QTreeView without model")



class MyStandardItem(QStandardItem):
    """derived QStandardItem for usage in MyQTreeView
    enables sort by specific role instead of text() (QtDisplayRole)
    particularly useful for numerical values that would otherwise be sorted alphabetically instead of numerically.
    """

    # Rev. 2026-11-22

    def __init__(self, *args, **kwargs):
        """constructor"""
        # Rev. 2026-11-22
        super().__init__(*args, **kwargs)

    def __lt__(self: QStandardItem, other: QStandardItem) -> bool:
        """the only difference to QStandardItem:
        derived operator for custom sort using special role

        Note:
        each row/record in (nested) model must have the same number of columns, even if there is nothing to display, else this method is not called and sorting for that column only shows the indicator-icon, but nothing happens

        Note 2:
        For mixed Items (QStandardItem/MyStandardItem/XYZ-Item...) or items without QT_ROLES.CUSTOM_SORT, the normal sort-behaviour (=>QtDisplayRole) will occur

        Args:
            other (QStandardItem): compare-QStandardItem, compared against self

        Returns:
            bool:
                True => sorted at the beginning in ascending order
                False => sorted at the end in ascending order
        """
        # Rev. 2026-11-22
        try:
            # if CUSTOM_SORT-Values not set => use DisplayRole => string
            # avoids Exceptions like "'<' not supported between instances of 'NoneType' and 'NoneType'"
            my_data = (
                self.data(QT_ROLES.CUSTOM_SORT)
                if self.data(QT_ROLES.CUSTOM_SORT) is not None
                else self.data(Qt.ItemDataRole.DisplayRole)
            )
            other_data = (
                other.data(QT_ROLES.CUSTOM_SORT)
                if other.data(QT_ROLES.CUSTOM_SORT) is not None
                else other.data(Qt.ItemDataRole.DisplayRole)
            )
            return my_data < other_data
        except Exception as e:
            # f.e. if data-type of QT_ROLES.CUSTOM_SORT can not be compared numerically or alphabetically
            return False


class MySubLayerTextBrowser(QTextBrowser):
    """QTextBrowser to display parsed metadata (vector/raster-layer-files, container-files)
    implements drag&drop-functionalities by emitting special signals connected and evaluated outside of the widget
    """

    # Rev. 2026-11-23

    # signal triggered by dragEnterEvent
    drag_enter = pyqtSignal(QDragEnterEvent)

    # signal triggered by dragMoveEvent
    drag_move = pyqtSignal(QDragMoveEvent)

    # signal triggered by dropEvent
    dropped = pyqtSignal(QDropEvent)

    # stylsheet for flash
    flash_style = "QTextBrowser{background-color: #ff8f30;border: 2px dotted red}"
    # stylsheet for no flash, "" resets style to default
    no_flash_style = "QTextBrowser{background-color: #d5d5ff;border: 1px dotted blue}"
    # how long?
    flash_total_duration_msec = 2000
    # how fast?
    flash_interval_msec = 100

    def __init__(self, layer_lib: LayerLib, parent=None):
        """Constructor

        Args:
            layer_lib (LayerLib): access to plugin
            parent (_type_, optional): parent in Qt-Hierarchy
        """
        # Rev. 2026-11-23
        super().__init__(parent)
        self.layer_lib = layer_lib

        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(False)
        self.flash_timer.timeout.connect(self.do_flash)
        # flag-var to switch between flash_style/no_flash_style
        self.is_flashing = False
        # start-time in nano-seconds
        self.timer_started_ns = None

        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setAcceptDrops(True)

        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)

        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)

        fixed_font.setPointSize(10)

        self.setFont(fixed_font)

        self.setStyleSheet(self.no_flash_style)

        # special style for links
        self.document().setDefaultStyleSheet(
            "a { text-decoration: underline; color: green; font-weight: bold;}"
        )

    def start_flash(self):
        """starts the flash and stores current time in self.timer_started_ns"""
        # Rev. 2026-11-23
        self.setFocus()
        self.flash_timer.start(self.flash_interval_msec)
        self.timer_started_ns = time.perf_counter_ns()

    def do_flash(self):
        """function called every flash_interval_msec until flash_total_duration_msec is reached"""
        # Rev. 2026-11-23
        self.is_flashing = not self.is_flashing

        flash_time_ns = time.perf_counter_ns() - self.timer_started_ns
        if flash_time_ns < self.flash_total_duration_msec * 1e6:
            # toggles the styles depending on self.is_flashing
            if self.is_flashing:
                self.setStyleSheet(self.no_flash_style)
            else:
                self.setStyleSheet(self.flash_style)
        else:
            # flash_total_duration_msec is reached, stop the timer and reset the style
            self.flash_timer.stop()
            self.setStyleSheet(self.no_flash_style)

    def dragEnterEvent(self, evt: QDragEnterEvent):
        """subclassed, triggered if an object is dragged over this widget, not over an item of this widget
            evt.accept() => green check-cursor-icon
            evt.ignore() => red forbid-cursor-icon

        Args:
            evt (QDragEnterEvent)
        """
        # Rev. 2026-11-23
        self.drag_enter.emit(evt)

    def dragMoveEvent(self, evt: QDragMoveEvent):
        """subclassed, triggered by moving a dragged object over this widget
        same check as dragEnterEvent:
            evt.accept() => green check-cursor-icon
            evt.ignore() => red forbid-cursor-icon

        Note: only triggered, if dragEnter-event was accepted
        Note: must be defined, because else original dragMoveEvent is triggered, which does not accept the event

        Args:
            evt (QDropEvent)
        """
        # Rev. 2026-11-23
        self.drag_move.emit(evt)

    def dropEvent(self, evt: QDropEvent):
        """subclassed, triggered if an object is dropped onto this widget

        Note: only triggered, if dragEnter-event was accepted

        Args:
            evt (QDropEvent)
        """
        # Rev. 2026-11-23
        self.dropped.emit(evt)

    @staticmethod
    def check_valid_evt_resource(
        evt: QDragEnterEvent | QDragMoveEvent | QDropEvent,
    ) -> tuple:
        """Pre-Check mime-data of Drag&Drop-event on MySubLayerTextBrowser for usage as single resource

        Args:
            evt (QEvent): QDragEnterEvent/QDragMoveEvent/QDropEvent

        Returns
            tuple(path:str,error_msg:str): absolute path to qlr/qgs/qgz-file (evt can be accepted) or None + error_msg
        """
        # Rev. 2026-11-23

        if evt.mimeData().hasUrls():
            # drag&drop single container-file from file-system
            if len(evt.mimeData().urls()) == 1:
                url = evt.mimeData().urls()[0]
                if url.isLocalFile():
                    # qgis.PyQt.QtCore.QUrl('file:///home/...
                    url_path = url.toLocalFile()
                    # problem under windows:
                    # path is something like /C:/Users/..., which is not usable for Path
                    if url_path[2] == ":":
                        url_path = url_path.lstrip("/")

                    # File or directory
                    resource_path_posix = Path(url_path)

                    if resource_path_posix.exists():

                        if resource_path_posix.is_file():

                            file_suffix = str.lower(
                                resource_path_posix.suffix.lstrip(".")
                            )
                            if file_suffix in CONTAINER_EXTENSIONS:
                                return resource_path_posix.as_posix(), None
                            else:
                                return None, MY_DICT.tr(
                                    "file_suffix_not_supported", file_suffix
                                )
                        else:
                            return None, MY_DICT.tr(
                                "drag_and_drop_directory_not_supported"
                            )
                    else:
                        return None, MY_DICT.tr(
                            "file_not_found", resource_path_posix.as_posix()
                        )
                else:
                    # f.e. URL from Browser dropped
                    return None, MY_DICT.tr("only_local_files_supported")
            else:
                return None, MY_DICT.tr("ifm_warning_multiple_files_dropped")
        elif evt.mimeData().hasFormat("application/x-vnd.qgis.qgis.uri"):
            # drag&drop single container-file from QGis-Browser-Panel...
            uri_bya = evt.mimeData().data("application/x-vnd.qgis.qgis.uri")

            uri_bya_parts = []
            bya_part = bytes()

            # quite complicated: the byte-array can be splitted by a sequence of 5 bytes matching
            re_match = re.compile(rb"[\x00]{2}[\x00-\xff]{2}[\x00]{1}")
            for idx, by in enumerate(uri_bya):

                if idx < len(uri_bya) - 5:
                    # chunk of 5 bytes
                    by_5 = uri_bya[idx : idx + 5]

                    if re.match(re_match, by_5):
                        # don't append the first match at the very beginning of uri_bya
                        if len(bya_part):
                            # strip the matching 5 bytes
                            uri_bya_parts.append(bya_part[5:])
                        # skip iteration
                        idx += 5
                        # new part:
                        bya_part = bytes()

                bya_part += by

            # append the last part
            uri_bya_parts.append(bya_part[5:])

            if len(uri_bya_parts) == 1:
                uri_decoded = ba_to_string(uri_bya_parts[0])

                # note: uri is seperated by colons, but windows uses ':' in paths, masked as "\:"
                # f.e. 'vector:ogr:2022-01-20 EZG Malefinkbach:C\:/temp/...'
                # workaround to get 'C:/temp/...'
                uri_decoded = uri_decoded.replace(r"\:", "#escaped_colon#")
                uri_parts = uri_decoded.split(":")
                uri_parts = [
                    uri_part.replace("#escaped_colon#", ":") for uri_part in uri_parts
                ]

                uri_type = uri_parts[0]

                if uri_type in ["custom", "project"]:
                    # custom: qlr-file
                    # project: qgs/qgz
                    uri_path = uri_parts[3]

                    # File or directory
                    resource_path_posix = Path(uri_path)

                    if resource_path_posix.is_file():

                        file_suffix = str.lower(resource_path_posix.suffix.lstrip("."))
                        if file_suffix in CONTAINER_EXTENSIONS:
                            return resource_path_posix.as_posix(), None
                        else:
                            return None, MY_DICT.tr(
                                "file_suffix_not_supported", file_suffix
                            )
                else:
                    return None, MY_DICT.tr("uri_type_not_supported", uri_type)
            else:
                return None, MY_DICT.tr("ifm_warning_multiple_files_dropped")

        else:
            return None, MY_DICT.tr("mime_data_not_accepted")

    @staticmethod
    def pre_check_dragdrop_event(
        evt: QDragEnterEvent | QDragMoveEvent | QDropEvent,
    ) -> bool:
        """Pre-Check of any Drag&Drop-Event, used in LayerLibDialog

        note:
            can be changed by sys_set_tool_mode
            if set to DragOnly, the events will bubble up to main-window such triggering layer-load (supported layer-file)
            or project-load (if project-file qgs/qgz was dropped)

        Superficial check only accepting more than check_valid_evt_resource:
        mutliple urls, directories, vector/raster-layer-files,
        drag&drop layer(s)/layergroup(s) from QGis-Layer-Panel

        Args:
            evt (QEvent): QDragEnterEvent/QDragMoveEvent/QDropEvent

        Returns:
            bool: accept mime or not
        """
        # Rev. 2026-11-21

        if evt.mimeData().hasUrls():
            return True
        elif evt.mimeData().hasFormat("application/qgis.layertree.layerdefinitions"):
            # drag&drop layer/layer-group from Layers-Panel
            return True
        elif evt.mimeData().hasFormat("application/x-vnd.qgis.qgis.uri"):
            # drag&drop qlr-file from QGis-Browser-Panel...
            return True


class DelegateStyle:
    """Helper-Class with metadata for style in this delegate, replacement for dictionary
    initialized with defaults, can/must be adapted in instances
    """

    # Rev. 2026-11-23

    # padding-left in pixel => place for delegate-icons. Defaults to 0
    padding_left: int = 0

    # too long textes will be "..."-elided. Defaults to True
    elide_text: bool = True

    # padding from text to top. Defaults to 12.
    padding_top: int = 8

    # padding from text to bottom. Defaults to 12.
    padding_bottom: int = 8

    # width of icon, affects all icons. Defaults to 10.
    icon_width: int = 10

    # height of icon, affects all icons. Defaults to 10.
    icon_height: int = 10

    # gap between icons, width of icon. Defaults to 5.
    icon_gap: int = 5

    # background-color for this style
    bg_color: QColor = QColor("#D6D6D6")

    # text-color for this style
    text_color: QColor = Qt.GlobalColor.black

    # border-color for this style
    border_color: QColor = Qt.GlobalColor.lightGray

    # border-width for this style
    border_width: int = 1

    # border-width for this style if item is selected
    highlight_border_width: int = 1

    # border-color for this style if item is selected
    highlight_border_color: QColor = Qt.GlobalColor.black

    # background-color for this style if item is selected
    highlight_bg_color: QColor = QColor("#ffbd5b")

    def __init__(self, icon_idcs: dict = {}, icon_tooltips: dict = {}):
        """constructor with the two mutable properties, which therefore can't be initialized with class-vars

        Args:
            icon_idcs (dict, optional):
            indices of icons to be used
            keys matching to integer-keys in Delegate.qicons,
            values check_enable_role matching to special role in model-items,
            if item.data(check_enable_role) can be interpretated as True
            => icon will be drawn normal
            else (item.data(check_enable_role) not set or interpretated as False)
            => icon will be drawn disabled
            Defaults to {}.
            icon_tooltips (dict, optional): adaptable tooltips, keys matching to LeftSideIconsDelegate.qicons. Defaults to {}.
        """
        # Rev. 2026-11-23
        self.icon_idcs = icon_idcs
        self.icon_tooltips = icon_tooltips


class LeftSideIconsDelegate(QStyledItemDelegate):
    """delegate for appending icons in front of left-padded text
    can use multiple "styles" (icons, colors, border, tooltips...) depending on Item-Values, see DelegateStyle
    embeds icons, triggering two signals, which can be connected for click/hover-functionalities
    """

    # Rev. 2026-11-23

    # signal which can be connected anywhere
    # delivers QModelIndex, icon_nbr and icon_idx of pressed icon
    # self.tree_view.delegates[0].cell_button_pressed.connect(self.st_cell_button_pressed)
    cell_button_pressed = pyqtSignal(QModelIndex, int, int)

    # same for hover-event
    # requires QTreeView.viewport().setMouseTracking(True)
    # self.tree_view.delegates[0].cell_button_hover.connect(self.st_cell_button_hover)
    cell_button_hover = pyqtSignal(QModelIndex, int, int)

    def __init__(
        self,
        parent: QWidget = None,
    ):
        """_summary_

        Args:
            parent (QWidget, optional): Parent Widget in Qt-hierarchy. Defaults to None.
        """
        # Rev. 2026-11-23
        super().__init__(parent)

        # dictionary
        # key = style_id, matching to data(QT_ROLES.STYLE)
        # value = instance of DelegateStyle, defined in subclasses
        self.styles = {}

        # repository of icons, can be replaced/adapted/expanded in subclasses
        # integer-keys matching to DelegateStyle.icon_tooltips and DelegateStyle.icon_idcs
        self.qicons = {}

        # no file-exists-check here resulting in missing icons
        self.qicons[0] = QIcon(f"{ICON_DIR}/ll_show_metas.svg")
        self.qicons[1] = QIcon(f"{ICON_DIR}/ll_layer_add.svg")
        self.qicons[2] = QIcon(f"{ICON_DIR}/mActionDeleteSelectedFeatures.svg")

    def get_icon_rect(
        self, index: QModelIndex, option: QStyleOptionViewItem, icon_nbr: int
    ) -> QRect:
        """calculate position for icon insite QTreeView-cell-item
        icons are vertically centered by padding_top/padding_bottom

        Args:
            option (QStyleOptionViewItem): current item where the icon is drawn, necessary to get available width and height
            icon_nbr (int): Number of current icon

        Returns:
            QRect: position inside QStandardItem
        """
        # Rev. 2026-11-23
        icon_rect = QRect()
        delegate_style = self.styles.get(index.data(QT_ROLES.STYLE))
        if delegate_style:
            option_left = option.rect.left()
            option_top = option.rect.top()
            option_bottom = option.rect.bottom()

            icon_top = option_top + delegate_style.padding_top
            icon_bottom = option_bottom - delegate_style.padding_bottom
            icon_left = (
                option_left
                + delegate_style.icon_gap
                + icon_nbr * (delegate_style.icon_width + delegate_style.icon_gap)
            )
            icon_right = icon_left + delegate_style.icon_width
            icon_rect = QRect(
                QPoint(icon_left, icon_top), QPoint(icon_right, icon_bottom)
            )

        return icon_rect

    def editorEvent(
        self,
        event: QMouseEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        """Sub-classed, normally for edit-purpose (double-click on QStandardItem), here to register clicks or mouse-move on the Icons
        Note:
        cell_button_hover requires QTreeView.viewport().setMouseTracking(True), else not triggered

        Args:
            event (QMouseEvent), here: register MouseButtonPress or MouseMove on the prepended icons and emit the cell_button_pressed rsp. cell_button_hover-signals
            model (QAbstractItemModel)
            option (QStyleOptionViewItem)
            index (QModelIndex)

        Returns:
            bool: must be returned by editorEvent
        """
        # Rev. 2026-11-23
        delegate_style = self.styles.get(index.data(QT_ROLES.STYLE))
        if delegate_style:
            if event.type() == QEvent.Type.MouseButtonPress:
                icon_nbr = 0
                for icon_idx, check_enable_role in delegate_style.icon_idcs.items():
                    icon = self.qicons.get(icon_idx)
                    if icon:
                        icon_rect = self.get_icon_rect(index, option, icon_nbr)
                        if icon_rect.contains(event.pos()):
                            self.cell_button_pressed.emit(index, icon_nbr, icon_idx)
                            # return => break and avoid super()-delegate
                            return True
                    else:
                        pass
                        # raise IndexError(f"icon #{icon_idx} not in self.qicons...")

                    icon_nbr += 1

            if event.type() == QEvent.Type.MouseMove:
                icon_nbr = 0
                for icon_idx, check_enable_role in delegate_style.icon_idcs.items():
                    icon = self.qicons.get(icon_idx)
                    if icon:
                        icon_rect = self.get_icon_rect(index, option, icon_nbr)
                        if icon_rect.contains(event.pos()):
                            self.cell_button_hover.emit(index, icon_nbr, icon_idx)
                            # return => break and avoid super()-delegate
                            return True

                    else:
                        pass
                        # raise IndexError(f"icon #{icon_idx} not in self.qicons...")

                    icon_nbr += 1

        # delegate all other to super()-implementation
        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Reimplemented:
        Returns the size needed by the delegate to display the item specified by index, taking into account the style information provided by option.
        returns super().sizeHint + padding_left + padding_top + padding_bottom

        Args:
            option (QStyleOptionViewItem): parameters to draw an item in a view widget
            index (QModelIndex)

        Returns:
            QSize: enlarged super().sizeHint()
        """
        # Rev. 2026-11-23

        super_size_hint = super().sizeHint(option, index)

        delegate_style = self.styles.get(index.data(QT_ROLES.STYLE))
        if delegate_style:
            super_size_hint.setWidth(
                super_size_hint.width() + delegate_style.padding_left
            )
            super_size_hint.setHeight(
                super_size_hint.height()
                + delegate_style.padding_top
                + delegate_style.padding_bottom
            )
        return super_size_hint

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ):
        """Reimplemented to paint this item into the view widget

        Args:
            painter (QPainter): performs low-level painting on widgets
            option (QStyleOptionViewItem): parameters to draw an item in a view widget
            index (QModelIndex): index to QStandardItem ("record") in model

        Raises:
            IndexError: for icons accessed via icon_idx which are not defined not in self.qicons
        """
        # Rev. 2026-11-23

        delegate_style = self.styles.get(index.data(QT_ROLES.STYLE))
        if delegate_style:

            # if self.filter_role is None or index.data(self.filter_role) is not None:
            painter.save()
            pen = painter.pen()
            pen.setColor(delegate_style.border_color)
            pen.setWidth(delegate_style.border_width)
            painter.setPen(pen)
            painter.fillRect(option.rect, delegate_style.bg_color)

            # line lower edge
            painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
            # line right edge
            painter.drawLine(option.rect.topRight(), option.rect.bottomRight())

            if option.state & QStyle.StateFlag.State_Selected:
                # selected item with special background
                painter.fillRect(option.rect, delegate_style.highlight_bg_color)
                pen = painter.pen()
                pen.setColor(delegate_style.highlight_border_color)
                pen.setWidth(delegate_style.highlight_border_width)
                painter.setPen(pen)
                # and special lower edge
                painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

            icon_nbr = 0
            for icon_idx, check_enable_role in delegate_style.icon_idcs.items():
                icon = self.qicons.get(icon_idx)
                if icon:
                    icon_rect = self.get_icon_rect(index, option, icon_nbr)

                    # only draw icon, if the column-width is sufficient, else drawText '...' (elide-like)
                    if (
                        icon_rect.left() + delegate_style.icon_gap
                    ) <= option.rect.right():
                        mode = QIcon.Mode.Normal
                        # try because the value possibly can not be parsed as boolean
                        try:

                            if check_enable_role and not bool(
                                index.data(check_enable_role)
                            ):
                                mode = QIcon.Mode.Disabled
                        except:
                            mode = QIcon.Mode.Disabled

                        # note: as standalone-script with Qt6 icons were not painted, no error
                        # workaround: install additional package via
                        # sudo apt install libqt6svg6
                        # see https://stackoverflow.com/questions/76047551/icons-shown-in-qt5-not-showing-in-qt6

                        # fortunately this is not the case with qgis.PyQt for QGis4 (=> PyQt6)
                        icon.paint(
                            painter,
                            icon_rect,
                            # Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            mode=mode,
                        )

                    else:
                        # simulated elide-effect for icons
                        icon_rect.adjust(-delegate_style.icon_gap, 0, 0, 0)
                        pen = painter.pen()
                        pen.setColor(delegate_style.text_color)
                        painter.setPen(pen)

                        elide_font = painter.font()
                        elide_font.setWeight(QFont.Weight.Medium)
                        painter.setFont(elide_font)
                        painter.drawText(
                            icon_rect,
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                            "...",
                        )

                    icon_nbr += 1
                else:
                    raise IndexError(f"icon #{icon_idx} not in self.qicons...")

            if index.data(Qt.ItemDataRole.DisplayRole):
                if delegate_style.padding_left:
                    option.rect.adjust(delegate_style.padding_left, 0, 0, 0)

                # default align: left and vertically centered...
                option.displayAlignment = (
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                # ...or use text-alignment from model, if defined...
                if index.data(Qt.ItemDataRole.TextAlignmentRole) is not None:
                    try:
                        # note:
                        # Qt5 => Qt.Alignment (own type PyQt5.QtCore.Qt.Alignment) or Qt.AlignmentFlag (PyQt5.QtCore.Qt.AlignmentFlag), both can be used
                        # Qt6 => only Qt.AlignmentFlag
                        option.displayAlignment = Qt.AlignmentFlag(
                            index.data(Qt.ItemDataRole.TextAlignmentRole)
                        )
                    except:
                        # the value of Qt.ItemDataRole.TextAlignmentRole can be anything, which perhaps can't be converted to Qt.Alignment
                        pass

                pen = painter.pen()
                pen.setColor(delegate_style.text_color)
                painter.setPen(pen)

                my_text = str(index.data(Qt.ItemDataRole.DisplayRole))

                # Compute elided text (trailing "...")
                # note:
                # needed to be implemented because of subclassed paint-method without delegate to super().paint()
                # so neither setTextElideMode(...) applied to QTreeView/QTableView
                # nor option.textElideMode = Qt.TextElideMode.ElideRight work
                if delegate_style.elide_text:
                    metrics = QFontMetrics(option.font)
                    elided_text = metrics.elidedText(
                        my_text, Qt.TextElideMode.ElideRight, option.rect.width()
                    )
                    painter.drawText(option.rect, option.displayAlignment, elided_text)
                else:
                    painter.drawText(option.rect, option.displayAlignment, my_text)

            painter.restore()
        else:
            # paint without delegate:
            # super().paint(painter, option, index)
            # or don't paint at all => empty cells
            pass

    def helpEvent(
        self,
        event: QMouseEvent,
        view: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        """subclassed for ToolTips on icons

        Args:
            event (QMouseEvent)
            view (QWidget): widget where the event occured, used to hide ToolTip if the cursor is moved outside
            option (QStyleOptionViewItem): parameters to draw an item in a view widget
            index (QModelIndex): index to QStandardItem ("record") in model

        Returns:
            bool: if omitted => TypeError: invalid result from LeftSideIconsDelegateFolder.helpEvent(), a 'bool' is expected not 'NoneType'
        """
        # Rev. 2026-11-23
        delegate_style = self.styles.get(index.data(QT_ROLES.STYLE))
        if delegate_style and delegate_style.icon_idcs:
            icon_nbr = 0
            for icon_idx, check_enable_role in delegate_style.icon_idcs.items():
                icon = self.qicons.get(icon_idx)
                icon_tooltip = delegate_style.icon_tooltips.get(icon_idx)
                if icon:
                    # optional
                    if icon_tooltip:
                        icon_rect = self.get_icon_rect(index, option, icon_nbr)

                        if icon_rect.contains(event.pos()):
                            if (
                                check_enable_role
                                and index.data(check_enable_role) == False
                            ):
                                # special ToolTip if index.data(check_enable_role) is set and bool False
                                icon_tooltip = f"{icon_tooltip}<br>(currently disabled)"

                            QToolTip.showText(
                                event.globalPos(),
                                icon_tooltip,
                                view,
                                QRect(0, 0, 0, 0),
                                2500,
                            )
                            # return => break and avoid super()-delegate
                            return True

                    icon_nbr += 1
                else:
                    pass
                    # raise IndexError(f"icon #{icon_idx} not in self.qicons...")

        # ToolTip from QStandardItem.data(Qt.ItemDataRole.ToolTipRole)
        return super().helpEvent(event, view, option, index)


class LeftSideIconsDelegateFolderLayer(LeftSideIconsDelegate):
    """subclassed for LayerLib-folders and layers having different styles, identified by value of role QT_ROLES.STYLE (here: 'resource' or 'folder')"""

    # Rev. 2026-11-23

    def __init__(
        self,
        folder_padding_left: int = 0,
        folder_elide_text: bool = True,
        folder_icon_idcs: dict = {},
        layer_padding_left: int = 0,
        layer_elide_text: bool = True,
        layer_icon_idcs: dict = {},
    ):
        """constructor, forwarded to super() = LeftSideIconsDelegate

        Args:
            folder_padding_left (int, optional): padding-left for folder_style. Defaults to 0.
            folder_elide_text (bool, optional): text-elide for folder_style. Defaults to True.
            folder_icon_idcs (dict, optional): icons to be shown for folder_style. Defaults to {}.
            layer_padding_left (int, optional): padding-left for layer_style. Defaults to 0.
            layer_elide_text (bool, optional): text-elide for layer_style. Defaults to True.
            layer_icon_idcs (dict, optional): icons to be shown for layer_style. Defaults to {}.
        """
        # Rev. 2026-11-23
        super().__init__()

        # style for folder, only used in the first folder-MyStandardItem, but via setFirstColumnSpanned shown in the whole row
        # QT_ROLES.STYLE == 'folder'
        folder_icon_tooltips = {}
        folder_icon_tooltips[0] = "Show/edit folder-metadata"
        folder_icon_tooltips[1] = "Add assigned layers to map"
        folder_icon_tooltips[2] = "Remove folder and assigned layers from LayerLib..."

        folder_style = DelegateStyle(folder_icon_idcs, folder_icon_tooltips)

        folder_style.padding_left = folder_padding_left
        folder_style.elide_text = folder_elide_text
        folder_style.icon_idcs = folder_icon_idcs
        folder_style.bg_color = QColor("#D6D6D6")
        folder_style.text_color = Qt.GlobalColor.black
        folder_style.border_color = Qt.GlobalColor.lightGray
        folder_style.border_width = 1
        folder_style.highlight_border_width = 1
        folder_style.highlight_border_color = Qt.GlobalColor.black
        folder_style.highlight_bg_color = QColor("#ffbd5b")

        self.styles["folder"] = folder_style

        # style for MyStandardItem with QT_ROLES.STYLE == 'resource'
        layer_icon_tooltips = {}
        layer_icon_tooltips[0] = "Show/edit layer-metadata"
        layer_icon_tooltips[1] = "Add layer to map"
        layer_icon_tooltips[2] = "Remove layer from LayerLib..."

        layer_style = DelegateStyle(layer_icon_idcs, layer_icon_tooltips)

        layer_style.padding_left = layer_padding_left
        layer_style.elide_text = layer_elide_text
        layer_style.icon_idcs = layer_icon_idcs
        layer_style.bg_color = QColor("#ffebc6")
        layer_style.text_color = Qt.GlobalColor.black
        layer_style.border_color = Qt.GlobalColor.lightGray
        layer_style.border_width = 1
        layer_style.highlight_border_width = 1
        layer_style.highlight_border_color = Qt.GlobalColor.black
        layer_style.highlight_bg_color = QColor("#ffbd5b")

        self.styles["resource"] = layer_style


class RecursiveXMLModel(QStandardItemModel):
    """QStandardItemModel for MyQTreeView

    uses recursive XML with nodes 'folder' and 'resource'
    these nodes have a unique id-attribute and fixed sub-nodes with tags 'label', 'description' (both) and 'path' (layer)
    needed to be subclassed for drag&drop-mime-handling
    """

    # Rev. 2026-11-23
    def __init__(self, layer_lib):
        """constructor

        Args:
            layer_lib (LayerLib): back-reference to plugin
        """
        # Rev. 2026-11-23
        super().__init__()
        self.layer_lib = layer_lib


    def canDropMimeData(
        self,
        mime_data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        """re-implemented
        called from each accepted QTreeView dragEnter/dragMove/dropEvent
        must return bool for setDropIndicatorShown (selection-effect in QTreeView)


        requires
            QTreeView.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)

        note:
            accept for tool_mode "reorder" (TreeView drag&drop)
            drop is allowed everywhere in Model independend from row/column

        Args:
            mime_data (QMimeData): DropAction.mimeData()
            action (Qt.DropAction): Drop-Action which triggers this check
            row (int): row-index in model
            column (int): column-index in model
            parent (QModelIndex): index of parent in model, especially for recursive

        Returns:
            bool
        """
        # Rev. 2026-11-23
        return self.layer_lib.tool_mode == "reorder"

    def mimeData(self, idxs: list) -> QMimeData:
        """subclassed, delivers Mime LayerLib/folder_id rsp. LayerLib/resource_id for Drag&Drop-Item
        used for internal Tree-Structure-Reorder and MyCustomDropHandler for Drag&Drop to Map-Canvas

        Args:
            idxs (list): list of QgsIndex

        Returns:
            QMimeData with data LayerLib/folder_id rsp. LayerLib/resource_id thus make QStandardItem acceptable for Drag&Drop internal
            and into iface (requiring iface.registerCustomDropHandler(QgsCustomDropHandler))
        """
        # Rev. 2026-11-23

        my_mime = QMimeData()
        # encode => https://doc.qt.io/qt-6/qbytearray.html
        # note: resource_id and folder_id always are strings
        if len(idxs) > 0 and idxs[0].data(QT_ROLES.FOLDER_ID):
            folder_id = idxs[0].data(QT_ROLES.FOLDER_ID)
            my_mime.setData("LayerLib/folder_id", folder_id.encode("utf-8"))
        elif len(idxs) > 1 and idxs[1].data(QT_ROLES.RESOURCE_ID):
            resource_id = idxs[1].data(QT_ROLES.RESOURCE_ID)
            my_mime.setData("LayerLib/resource_id", resource_id.encode("utf-8"))

        return my_mime


class FlashingQLabel(QLabel):
    """QLabel with flash-functionality for temporary hints"""

    # Rev. 2026-11-23

    # how long?
    flash_total_duration_msec = 2000
    # how fast?
    flash_interval_msec = 100

    def __init__(self, parent: QWidget = None):
        """Constructor

        Args:
            parent (QWidget): Parent-Object in Qt-Hierarchy
        """
        # Rev. 2026-11-23
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(False)
        self.flash_timer.timeout.connect(self.do_flash)
        # flag-var to switch between flash_style/no_flash_style
        self.is_visible = False
        # start-time in nano-seconds
        self.timer_started_ns = None

        # keep height, if visibility is switched
        # else the entire layout begins to move...
        sp_retain = self.sizePolicy()
        sp_retain.setRetainSizeWhenHidden(True)
        self.setSizePolicy(sp_retain)

        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def start_flash(self, keep_visible: bool = True):
        """starts the flash and stores current time in self.timer_started_ns

        Args:
            keep_visible (bool, optional): keep widget visibla after flash. Defaults to True.
        """
        # Rev. 2026-11-23
        self.keep_visible = keep_visible
        self.setFocus()
        self.flash_timer.start(self.flash_interval_msec)
        self.timer_started_ns = time.perf_counter_ns()

    def do_flash(self):
        """function called every flash_interval_msec until flash_total_duration_msec is reached"""
        # Rev. 2026-11-23

        self.is_visible = not self.is_visible

        flash_time_ns = time.perf_counter_ns() - self.timer_started_ns
        if flash_time_ns < self.flash_total_duration_msec * 1e6:
            self.setVisible(self.is_visible)
        else:
            # flash_total_duration_msec is reached, stop the timer and reset the style
            self.flash_timer.stop()
            self.setVisible(self.keep_visible)


class FlashingBorderQLineEdit(QLineEdit):
    """QLineEdit with flashing borders for x-milli-seconds to signalize missing or invalid values"""

    # Rev. 2026-11-23
    # stylsheet for flash
    flash_style = "border: 2px solid red"
    # stylsheet for no flash, "" resets style to default
    no_flash_style = ""
    # how long?
    flash_total_duration_msec = 2000
    # how fast?
    flash_interval_msec = 100

    def __init__(self, parent: QWidget = None):
        """Constructor

        Args:
            parent (QWidget): Parent-Object in Qt-Hierarchy
        """
        # Rev. 2026-11-23

        super().__init__(parent)
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(False)
        self.flash_timer.timeout.connect(self.do_flash)
        # flag-var to switch between flash_style/no_flash_style
        self.is_flashing = False
        # start-time in nano-seconds
        self.timer_started_ns = None

    def start_flash(self):
        """starts the flash and stores current time in self.timer_started_ns"""
        # Rev. 2026-11-23
        self.setFocus()
        self.flash_timer.start(self.flash_interval_msec)
        self.timer_started_ns = time.perf_counter_ns()

    def do_flash(self):
        """function called every flash_interval_msec until flash_total_duration_msec is reached"""
        # Rev. 2026-11-23
        self.is_flashing = not self.is_flashing

        flash_time_ns = time.perf_counter_ns() - self.timer_started_ns
        if flash_time_ns < self.flash_total_duration_msec * 1e6:
            # toggles the styles depending on self.is_flashing
            if self.is_flashing:
                self.setStyleSheet(self.no_flash_style)
            else:
                self.setStyleSheet(self.flash_style)
        else:
            # flash_total_duration_msec is reached, stop the timer and reset the style
            self.flash_timer.stop()
            self.setStyleSheet(self.no_flash_style)


class MyToolbarSpacer(QWidget):
    """Spacer for QToolBar
    added before first => right align
    added before first and after last => center"""

    # Rev. 2026-11-23
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
