#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Main-Dialog to show registered container-files, manage settings and
* inspect single container-file

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


from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QLineEdit,
    QScrollArea,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGridLayout,
    QLabel,
    QToolButton,
    QToolBar,
    QGroupBox,
    QPlainTextEdit

)

from qgis.PyQt.QtCore import Qt, QSize, QSignalBlocker

from qgis.PyQt.QtGui import QIcon, QDragMoveEvent, QDropEvent, QDragEnterEvent,QTextOption,QFontDatabase

from LayerLib.qt.MyQtWidgets import (
    MyQTreeView,
    MyQComboBox,
    MySubLayerTextBrowser,
    FlashingQLabel,
    QGroupBoxExpandable,
    ClickableQLineEdit
)

from LayerLib.tools.MyTools import (
    show_log_message,
    LayerFileParseResult,
    parse_evt_urls,
    parse_project_layer,
    parse_browser_panel_layers

    # debug_print
)

from LayerLib.tools.MyConstants import MY_DICT,ICON_DIR

from LayerLib import LayerLib


class LayerLibDialog(QDockWidget):
    """Dockable-Dialog for QGis-Plugin LayerLib"""
    # Rev. 2026-11-21

    def __init__(self, layer_lib:LayerLib, parent=None):
        """Constructor

        Args:
            layer_lib (LayerLib): Rückreferenz auf das Plugin
            parent (QWidget, optional):optional Qt-Parent-Element for Hierarchy, for docking: iface.mainWindow()
        """
        # Rev. 2026-11-21
        QDockWidget.__init__(self, parent)

        self.layer_lib = layer_lib
        self.setWindowTitle(MY_DICT.tr("LayerLibDialog_title"))
        # initialize hidden, see LayerLib.dlg_show()
        self.setVisible(False)


        main_wdg = QWidget(self)
        main_wdg.setLayout(QVBoxLayout())

        # central widget with mutiple tabs
        self.tbw_central = QTabWidget(self)

        self.tbw_central.setTabPosition(QTabWidget.TabPosition.North)

        # Tab 1: TreeView
        if True:

            lib_tab = QWidget()
            lib_tab.setLayout(QVBoxLayout())

            self.qtb_lib_tab = QToolBar()
            self.qtb_lib_tab.setIconSize(QSize(16, 16))
            self.qtb_lib_tab.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            lib_tab.layout().addWidget(self.qtb_lib_tab)

            self.qtrv_layer_lib = MyQTreeView(self.layer_lib)
            lib_tab.layout().addWidget(self.qtrv_layer_lib)

            sub_wdg = QWidget()
            sub_wdg.setLayout(QHBoxLayout())
            self.qpb_expand_all = QPushButton(
                QIcon(f"{ICON_DIR}/expand_all.svg"), ""
            )
            self.qpb_expand_all.setToolTip(MY_DICT.tr("qpb_expand_all_ttp"))
            sub_wdg.layout().addWidget(self.qpb_expand_all)

            self.qpb_collapse_all = QPushButton(
                QIcon(f"{ICON_DIR}/collapse_all.svg"), ""
            )
            self.qpb_collapse_all.setToolTip(MY_DICT.tr("qpb_collapse_all_ttp"))
            sub_wdg.layout().addWidget(self.qpb_collapse_all)

            self.qle_search = QLineEdit()
            self.qle_search.setPlaceholderText(MY_DICT.tr("qle_search_pht"))
            self.qle_search.setClearButtonEnabled(True)
            sub_wdg.layout().addWidget(self.qle_search)

            self.qpb_start_search = QPushButton(
                QIcon(f"{ICON_DIR}/search.svg"), ""
            )
            self.qpb_start_search.setToolTip(MY_DICT.tr("qpb_start_search_ttp"))
            sub_wdg.layout().addWidget(self.qpb_start_search)

            lib_tab.layout().addWidget(sub_wdg)

            lib_tab_qsa = QScrollArea(self)
            lib_tab_qsa.setWidgetResizable(True)
            lib_tab_qsa.setStyleSheet("QScrollArea {border-style: none;}")
            lib_tab_qsa.setWidget(lib_tab)

            self.tbw_central.addTab(lib_tab_qsa, MY_DICT.tr("lib_tab_lbl"))
        # Tab 2: Settings + Tools
        if True:

            settings_tab = QWidget()
            settings_tab.setLayout(QVBoxLayout())

            qgb_settings = QGroupBoxExpandable(MY_DICT.tr("qgb_settings_title"),True)
            qgb_settings.setLayout(QGridLayout())

            rc = 0
            qgb_settings.layout().addWidget(
                QLabel(MY_DICT.tr("treeview_source_path_lbl")), rc, 0
            )
            self.treeview_source_path_qle = ClickableQLineEdit(self)
            self.treeview_source_path_qle.setToolTip(
                MY_DICT.tr("treeview_source_path_qle_ttp")
            )
            self.treeview_source_path_qle.setReadOnly(True)
            qgb_settings.layout().addWidget(self.treeview_source_path_qle, rc, 1)
            self.select_treeview_xml_file_qpb = QPushButton(
                QIcon(f"{ICON_DIR}/mActionFileOpen.svg"),
                "",
            )
            # else will be triggered by any enter on the dialog
            self.select_treeview_xml_file_qpb.setToolTip(
                MY_DICT.tr("select_treeview_xml_file_qpb_ttp")
            )
            self.select_treeview_xml_file_qpb.setAutoDefault(False)
            qgb_settings.layout().addWidget(self.select_treeview_xml_file_qpb, rc, 2)

            rc += 1
            qgb_settings.layout().addWidget(
                QLabel(MY_DICT.tr("add_layer_visibility_qcbx_txt")), rc, 0
            )
            self.add_layer_visibility_qcbx = MyQComboBox(self)
            self.add_layer_visibility_qcbx.setToolTip(
                MY_DICT.tr("add_layer_visibility_qcbx_ttp")
            )
            self.add_layer_visibility_qcbx.addItem(
                MY_DICT.tr("allways_hidden_opt"), "hidden"
            )
            self.add_layer_visibility_qcbx.addItem(
                MY_DICT.tr("allways_visible_opt"), "visible"
            )
            qgb_settings.layout().addWidget(self.add_layer_visibility_qcbx, rc, 1)
            settings_tab.layout().addWidget(qgb_settings)


            qgb_tools = QGroupBoxExpandable(title=MY_DICT.tr("qgb_tools_title"))
            qgb_tools.setLayout(QGridLayout())

            rc = 0
            qgb_tools.layout().addWidget(
                QLabel(MY_DICT.tr("qle_search_txt")), rc, 0,1,2
            )

            rc += 1
            self.qle_search_path = QLineEdit()
            self.qle_search_path.setPlaceholderText(MY_DICT.tr("qle_search_path_ph_txt"))
            self.qle_search_path.setClearButtonEnabled(True)
            qgb_tools.layout().addWidget(
                self.qle_search_path, rc, 1
            )
            self.qpb_search_in_paths = QPushButton(
                QIcon(f"{ICON_DIR}/Find.svg"),
                "",
            )
            self.qpb_search_in_paths.setToolTip(MY_DICT.tr("qpb_search_in_paths_ttp"))
            qgb_tools.layout().addWidget(
                self.qpb_search_in_paths, rc, 2
            )

            rc +=1
            qgb_tools.layout().addWidget(
                QLabel(MY_DICT.tr("qle_replace_txt")), rc, 0,1,2
            )

            rc +=1
            self.qle_replace_path = QLineEdit()
            self.qle_replace_path.setPlaceholderText(MY_DICT.tr("qle_replace_path_ph_txt"))
            self.qle_replace_path.setClearButtonEnabled(True)
            qgb_tools.layout().addWidget(
                self.qle_replace_path, rc, 1
            )
            self.qpb_replace_in_paths = QPushButton(
                QIcon(f"{ICON_DIR}/FindAndReplace.svg"),
                "",
            )
            self.qpb_replace_in_paths.setToolTip(MY_DICT.tr("qpb_replace_in_paths_ttp"))
            qgb_tools.layout().addWidget(
                self.qpb_replace_in_paths, rc, 2
            )

            rc += 1
            qgb_tools.layout().addWidget(
                QLabel(MY_DICT.tr("qpb_detect_invalid_paths_txt")), rc, 0,1,2
            )
            self.qpb_detect_invalid_paths = QPushButton(
                QIcon(f"{ICON_DIR}/Find.svg"),
                "",
            )
            self.qpb_detect_invalid_paths.setToolTip(MY_DICT.tr("qpb_detect_invalid_paths_ttp"))
            qgb_tools.layout().addWidget(
                self.qpb_detect_invalid_paths, rc, 2
            )

            rc += 1
            qgb_tools.layout().addWidget(
                QLabel(MY_DICT.tr("qpb_detect_invalid_container_paths_txt")), rc, 0,1,2
            )
            self.qpb_detect_invalid_container_paths = QPushButton(QIcon(f"{ICON_DIR}/Find.svg"),"")
            self.qpb_detect_invalid_container_paths.setToolTip(MY_DICT.tr("qpb_detect_invalid_container_paths_ttp"))
            qgb_tools.layout().addWidget(
                self.qpb_detect_invalid_container_paths, rc, 2
            )

            rc += 1
            qgb_tools.layout().addWidget(
                QLabel(MY_DICT.tr("qpb_convert_paths_relative_txt")), rc, 0,1,2
            )
            self.qpb_convert_paths_relative = QPushButton(QIcon(f"{ICON_DIR}/FindAndReplace.svg"),"")
            self.qpb_convert_paths_relative.setToolTip(MY_DICT.tr("qpb_convert_paths_relative_ttp"))
            qgb_tools.layout().addWidget(
                self.qpb_convert_paths_relative, rc, 2
            )

            rc += 1
            qgb_tools.layout().addWidget(
                QLabel(MY_DICT.tr("qpb_convert_paths_absolute_txt")), rc, 0,1,2
            )
            self.qpb_convert_paths_absolute = QPushButton(QIcon(f"{ICON_DIR}/FindAndReplace.svg"),"")
            self.qpb_convert_paths_absolute.setToolTip(MY_DICT.tr("qpb_convert_paths_absolute_ttp"))
            qgb_tools.layout().addWidget(
                self.qpb_convert_paths_absolute, rc, 2
            )

            rc += 1
            qgb_tools.layout().addWidget(
                QLabel(MY_DICT.tr("qpte_result_log_txt")), rc, 0,1,2
            )

            rc += 1
            self.qpte_result_log = QPlainTextEdit()
            fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            fixed_font.setPixelSize(11)
            self.qpte_result_log.setFont(fixed_font)
            self.qpte_result_log.setWordWrapMode(QTextOption.WrapMode.NoWrap)
            qgb_tools.layout().addWidget(
                self.qpte_result_log, rc,0,1,3
            )

            settings_tab.layout().addWidget(qgb_tools)

            settings_tab.layout().addStretch()

            settings_tab_qsa = QScrollArea(self)
            settings_tab_qsa.setWidgetResizable(True)
            settings_tab_qsa.setStyleSheet("QScrollArea {border-style: none;}")
            settings_tab_qsa.setWidget(settings_tab)

            self.tbw_central.addTab(settings_tab_qsa, MY_DICT.tr("settings_tab_lbl"))

        # Tab 3: Inspect
        if True:
            inspect_tab = QWidget()
            inspect_tab.setLayout(QVBoxLayout())


            self.inspect_layer_drop_area = MySubLayerTextBrowser(self.layer_lib, self)
            self.inspect_layer_drop_area.setHtml(
                MY_DICT.tr("inspect_layer_drop_area_html")
            )
            self.inspect_layer_drop_area.drag_enter.connect(
                self.st_eval_drag_enter_event
            )
            self.inspect_layer_drop_area.drag_move.connect(
                self.st_eval_drag_move_event
            )
            self.inspect_layer_drop_area.dropped.connect(
                self.st_eval_drop_event
            )
            inspect_tab.layout().addWidget(self.inspect_layer_drop_area)

            self.tbw_central.addTab(inspect_tab, MY_DICT.tr("inspect_tab_lbl"))

        # Corner-Widget with function-icons in tbw_central accessible for all tabs
        self.qwdg_tbw_corner = QWidget()
        self.qwdg_tbw_corner.setLayout(QHBoxLayout())
        self.qwdg_tbw_corner.layout().setAlignment(Qt.AlignmentFlag.AlignRight)
        self.qwdg_tbw_corner.layout().setContentsMargins(0, 0, 0, 0)

        # show online-help
        self.qtb_show_help = QToolButton(self)
        self.qtb_show_help.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.qtb_show_help.setIcon(QIcon(f"{ICON_DIR}/plugin-help.svg"))
        self.qtb_show_help.setToolTip(MY_DICT.tr("qtb_show_help_ttp"))
        self.qwdg_tbw_corner.layout().addWidget(self.qtb_show_help)

        # toggle attach
        self.qtb_toggle_attach = QToolButton(self)
        self.qtb_toggle_attach.setCheckable(True)
        # see dlg_init(), which initializes the dialog left side docked and tabified
        self.qtb_toggle_attach.setChecked(True)
        self.qtb_toggle_attach.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.qtb_toggle_attach.setIcon(QIcon(f"{ICON_DIR}/mDockify.svg"))
        self.qtb_toggle_attach.setToolTip(MY_DICT.tr("qtb_toggle_attach_ttp"))
        self.qtb_toggle_attach.clicked.connect(self.toggle_attach)
        self.qwdg_tbw_corner.layout().addWidget(self.qtb_toggle_attach)

        self.tbw_central.setCornerWidget(
            self.qwdg_tbw_corner, corner=Qt.Corner.TopRightCorner
        )

        main_wdg.layout().addWidget(self.tbw_central)

        self.log_message_fqlbl = FlashingQLabel()
        main_wdg.layout().addWidget(self.log_message_fqlbl)

        self.setWidget(main_wdg)



    def st_eval_drag_enter_event(self, evt: QDragEnterEvent):
        """Part 1 of Drag&Drop on self.inspect_layer_drop_area: Dragged object first moved over the target widget
        connected to drag_enter-signal triggered by dragEnterEvent

        Args:
            evt (QDragMoveEvent)
        """
        # Rev. 2026-11-21
        if self.inspect_layer_drop_area.pre_check_dragdrop_event(evt):
            evt.accept()
        else:
            evt.ignore()

    def st_eval_drag_move_event(self, evt: QDragMoveEvent):
        """Part 2 of Drag&Drop on self.inspect_layer_drop_area: Dragged object moving over the target widget
        connected to drag_move-signal triggered by dragMoveEvent

        Args:
            evt (QDragMoveEvent)
        """
        # Rev. 2026-11-21
        if self.inspect_layer_drop_area.pre_check_dragdrop_event(evt):
            evt.accept()
        else:
            evt.ignore()

    def st_eval_drop_event(self, evt: QDropEvent):
        """Part 3 of Drag&Drop on self.inspect_layer_drop_area: Dragged object is dropped on the target widget
        connected to dropped-signal triggered by dropEvent

        Args:
            evt (QDropEvent)
        """
        # Rev. 2026-11-21
        self.inspect_layer_drop_area.clear()
        self.log_message_fqlbl.clear()
        self.log_message_fqlbl.setToolTip("")


        if self.inspect_layer_drop_area.pre_check_dragdrop_event(evt):

            parse_result = LayerFileParseResult()
            parse_result.add_header("Evaluate Drop-Event:", 0)

            if evt.mimeData().hasUrls():
                # Drag&Drop single local file from file-system
                parse_result.merge(parse_evt_urls(evt, self.layer_lib, 'LayerLibDialog', 0))
            elif evt.mimeData().hasFormat("application/qgis.layertree.layerdefinitions"):
                # drag&drop layer/layer-group from Layers-Panel
                # Note: This event must not be accepted, because that would remove layer from panel!
                # Note 2: User is forced to export layer as qlr-file, which is parsed afterwards
                # sole purpose: import qlr-file to Library afterwards
                parse_result.merge(parse_project_layer(evt, self.layer_lib, 'LayerLibDialog', 0))
            elif evt.mimeData().hasFormat("application/x-vnd.qgis.qgis.uri"):
                # Drop-Event from QGis-Browser-Panel
                parse_result.merge(
                    parse_browser_panel_layers(evt, self.layer_lib, 'LayerLibDialog', 0)
                )


            self.inspect_layer_drop_area.setHtml(parse_result.parse_html)
            # Note: accept drop from QGis-Layer-Panel will remove layer from project!
            if not evt.mimeData().hasFormat("application/qgis.layertree.layerdefinitions"):
                evt.accept()
            self.layer_lib.parse_cache['LayerLibDialog'] = parse_result.parse_cache
        else:
            show_log_message("WARNING", MY_DICT.tr("mime_data_not_accepted"), self.log_message_fqlbl, True)
            evt.ignore()


    def toggle_attach(self, checked: bool):
        """toggle dialog between TopLevel (free undockable window) and docked (with move and docked enabled, but floatable disabled)

        note:
        undocked with deviant behavior under QGis-3/Qt-5 vs. QGis-4/Qt-6
        and Windows vs. Linux (Windows: Dialog always above MainWindow and hidden with MainWindow-hide, no Taskbar-Icon)

        Args:
            checked (bool): checked-status of self.qtb_toggle_attach
        """
        # Rev. 2026-11-21

        if checked:
            # Dock the window inside iface.mainWindow() at last dock-position
            # convenience: store last size and position for the next toggle_attach
            # minimize/close...-icons in the dockwidget-toolbar because setFloating(False) hides dialog-title-bar
            self.setFeatures(
                QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
                | QDockWidget.DockWidgetFeature.DockWidgetClosable
                | QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )

            self.setFloating(False)
            self.show()
            self.setFocus()
            self.raise_()

        else:
            # undock the window and show normal title-bar with minimize/maximize/close-Buttons
            self.setFloating(True)

            # no minimize/close...-icons in the separate dockwidget-toolbar because they are shown in the dialog-title-bar
            # Qt-4 Windows: must be called before setWindowFlags else setWindowFlags ignored and no buttons at all
            # Qt-5 Windows: DockWidgetClosable is not shown as own icon, but the close-icon in title bar does not close the dialog
            self.setFeatures(
                QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
                | QDockWidget.DockWidgetFeature.DockWidgetClosable
            )

            # WindowStaysOnTopHint different behaviour Qt4/5 Windows/Linux, partially disturbing or not necessary => not applied here
            # duplicate Qt.WindowType.WindowCloseButtonHint, this is also shown on DockWidget-Title-Bar
            self.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowTitleHint
                | Qt.WindowType.CustomizeWindowHint
                | Qt.WindowType.WindowMinimizeButtonHint
                | Qt.WindowType.WindowMaximizeButtonHint
                | Qt.WindowType.WindowCloseButtonHint
                #| Qt.WindowType.WindowStaysOnTopHint
            )



            self.show()
            self.setFocus()


        # if called externally the check-state does not show the attach-state, but on plugin-unload the state of this button is stored in ini for next plugin-load
        with QSignalBlocker(self.qtb_toggle_attach):
            self.qtb_toggle_attach.setChecked(checked)
