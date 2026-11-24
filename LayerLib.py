#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Store Resource-Metadata (container-file, qlr/qgs/qgz) in XML-File

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

import os, re, math, datetime

import subprocess, platform

from osgeo import gdal, ogr

import urllib.parse

from pathlib import Path

from configparser import ConfigParser

from qgis.PyQt.QtWidgets import (
    QAction,
    QFileDialog,
    QMessageBox,
    QAbstractItemView,
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
)

from qgis.PyQt.QtGui import QIcon, QColor, QDropEvent, QIcon, QColor, QDrag

# Note: qgis.PyQt will import Qt5 or Qt6 depending on installed version!
from qgis.PyQt.QtCore import (
    Qt,
    QLocale,
    QTimer,
    QItemSelectionModel,
    QUrl,
    QUrlQuery,
    QMimeData,
    QSettings,
    QModelIndex,
    QSignalBlocker,
)

from qgis.PyQt.QtXml import QDomDocument


from qgis.core import (
    QgsMapLayer,
    QgsVectorLayer,
    QgsProject,
    QgsRasterLayer,
    Qgis,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsPolygon,
    QgsLineString,
    QgsPoint,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
)

from qgis.gui import (
    QgsCustomDropHandler,
    QgsRubberBand,
    QgsVertexMarker,
    QgisInterface,
    QgsCrsSelectionWidget,
)

import webbrowser

from LayerLib.tools.MyTools import (
    # debug_print,
    # debug_print_dom_node,
    get_container_file_dom_doc,
    save_treeview_dom_doc,
    get_folder_node,
    get_resource_node,
    ba_to_string,
    get_absolute_path,
    get_relative_path,
    validate_treeview_dom_doc,
    show_log_message,
    create_maplayer,
    get_valid_file,
    dom_node_to_ba,
    get_maplayer_node,
    ParseResult,
)

from LayerLib.tools.MyConstants import MY_DICT, QT_ROLES, ICON_DIR, CONTAINER_EXTENSIONS

from LayerLib.qt.MyQtWidgets import (
    MyToolbarSpacer,
)
from LayerLib.dialogs.LayerLibDialog import LayerLibDialog
from LayerLib.dialogs.EditFolderDialog import EditFolderDialog
from LayerLib.dialogs.AddFolderDialog import AddFolderDialog
from LayerLib.dialogs.EditResourceDialog import EditResourceDialog
from LayerLib.dialogs.AddResourceDialog import AddResourceDialog
from LayerLib.dialogs.DataSourcesDialog import DataSourcesDialog
from LayerLib.dialogs.SelectSubLayerDialog import SelectSubLayerDialog
from LayerLib.dialogs.MyConfirmDialog import MyConfirmDialog


class LayerLib(object):
    """container-object for this plugin"""

    # Rev. 2026-11-23

    def __init__(self, iface: QgisInterface):
        """standard-to-implement-function for plugins, Constructor for the Plugin.

        Args:
            iface (QgisInterface): interface to running QGis-App
        """
        # Rev. 2026-11-23

        # used only for correct link to version of documentation
        # should fit to version in metadata.txt
        # see tool_show_help
        self.plugin_release = "1.0.0"

        self.iface = iface

        # currently only "reorder" implemented: interactive re-order-folder/resource-structure, add new layers from project/file-system
        self.tool_mode = None

        # Metadata for loadable Layers
        # dictionaries with extensions of supported extensions, key: extension, value: metadata (not used so far)
        # note: some extensions like gpkg can contain raster or vector-layers and are listed in both dictionaries
        # container-extensions see MyConstants.CONTAINER_EXTENSIONS

        self.raster_extensions = {}
        self.vector_extensions = {}

        # gdal preserves metadata for file-based vector- and raster-layers
        for i in range(gdal.GetDriverCount()):

            drv = gdal.GetDriver(i)
            md = drv.GetMetadata_Dict()

            d = [drv.ShortName, drv.LongName, drv.GetMetadataItem(gdal.DMD_EXTENSIONS)]

            if "DCAP_RASTER" in md:

                ext = drv.GetMetadataItem(gdal.DMD_EXTENSIONS)
                if ext:
                    # split on whitespace, possibly multiple extensions returned, f.e. 'mvt mvt.gz pbf' for 'Mapbox Vector Tiles'
                    for ext_part in ext.split():
                        self.raster_extensions[ext_part] = d

            if (
                "DCAP_VECTOR" in md
            ):  # note "if" not "elif" or "else" as some drivers can handle both raster and vector

                ext = drv.GetMetadataItem(gdal.DMD_EXTENSIONS)
                if ext:
                    for ext_part in ext.split():
                        self.vector_extensions[ext_part] = d

        # some Canvas-Grafics for layer-extents, GPS-location, GPS-direction
        # extent-rectangle
        self.rb_extent = QgsRubberBand(self.iface.mapCanvas())
        self.rb_extent.setWidth(2)
        self.rb_extent.setLineStyle(Qt.PenStyle.SolidLine)
        self.rb_extent.setStrokeColor(QColor("#ffff0000"))
        self.rb_extent.setFillColor(QColor("#450000ff"))
        self.rb_extent.hide()

        # point for georeferenced images (Jpeg with gps, exif-header lat/lon)
        self.vm_gps = QgsVertexMarker(self.iface.mapCanvas())
        self.vm_gps.setPenWidth(2)
        self.vm_gps.setIconSize(15)
        self.vm_gps.setIconType(4)
        self.vm_gps.setColor(QColor("#FFff5050"))
        self.vm_gps.hide()

        # arrow to show directory in georeferenced images (Jpeg with gps, exif-header image-directory)
        self.rb_dir = QgsRubberBand(self.iface.mapCanvas(), Qgis.GeometryType.Line)
        self.rb_dir.setWidth(2)
        self.rb_dir.setLineStyle(Qt.PenStyle.SolidLine)
        self.rb_dir.setColor(QColor("#FFff0000"))
        self.rb_dir.hide()
        # arrow-length in pixel for flashing arrow-geometry
        self.arrow_length_px = 60

        # convenience: default for file-dialogs, f.e. qlr-exports, stored/restored in ini
        self.last_user_file = Path("~").expanduser().as_posix()

        # convenience: confirm-dialog for resource/folder-deletes
        # set to False if YesToAll is selected
        # see LayerLib.dialogs.MyConfirmDialog rsp. self.my_confirm_dialog
        self.confirm_resource_delete = True
        self.confirm_folder_delete = True

        # some settings, type string, stored/restored in ini-file, see sys_read_config

        self.treeview_source_path: str = None
        """path to TreeView-XML-File"""

        self.treeview_dom_doc: QDomDocument = None
        """the parsed self.treeview_source_path"""

        # default visibility for added layers
        self.add_layer_visibility: str = "hidden"
        """default visibility for added layers"""

        # convenience: open dialog attached or floating?
        # stored in ini
        self.dialog_attached = True
        # convenience: last active tab, stored in ini
        self.dialog_active_tab_index = 0

        self.dialog_x = self.iface.mainWindow().geometry().left() + 100
        self.dialog_y = self.iface.mainWindow().geometry().top() + 100
        self.dialog_width = 400
        self.dialog_height = 600

        # restore configuration from ini
        self.sys_read_config()

        # allow drag&drop of layers (or folders with layers) from TreeView to project
        self.my_drop_handler = MyCustomDropHandler(self)
        self.iface.registerCustomDropHandler(self.my_drop_handler)

        # Log-Message-Counter
        self.lmc = 0
        self.lmc_unchecked = 0

        # Flag-Variable, if True, a little introduction is displayed
        self.first_called = True

        # dialog, created here, initially hidden, filled and showed on demand, see dlg_show
        self.my_dialog = LayerLibDialog(self, self.iface.mainWindow())
        self.dlg_init()

        # Parse-Result from inspect_layer_drop_area(s)
        # key: dialog-class, where the parse was done
        self.parse_cache = {
            "AddResourceDialog": {},
            "EditResourceDialog": {},
            "LayerLibDialog": {},
        }

        # Sub-dialogs
        # initially hidden
        self.add_folder_dialog = AddFolderDialog(self, self.my_dialog)
        self.edit_folder_dialog = EditFolderDialog(self, self.my_dialog)

        self.add_resource_dialog = AddResourceDialog(self, self.my_dialog)
        self.edit_resource_dialog = EditResourceDialog(self, self.my_dialog)

        self.data_sources_dialog = DataSourcesDialog(self, self.my_dialog)
        self.select_uri_dialog = SelectSubLayerDialog(self, self.my_dialog)

        self.select_sub_layer_dialog = SelectSubLayerDialog(self, self.my_dialog)

        self.my_confirm_dialog = MyConfirmDialog(self, self.my_dialog)

    def sys_write_config(self):
        """write current configuration to ini-file
        created on demand in self.sys_get_ini_path()
        called with plugin-unload, f.e. if project with loaded plugin is closed"""
        # Rev. 2026-11-23
        config_object = ConfigParser()
        # Keys in der ini-Datei case-sensitive (default: all lowercase)
        # subclasses ConfigParser.optionxform() which defaults to lower()
        config_object.optionxform = str
        # write only valid strings to avoid "TypeError("option values must be strings")"
        config_object["CONFIG"] = {
            "treeview_source_path": (
                self.treeview_source_path
                if isinstance(self.treeview_source_path, str)
                else ""
            ),
            "add_layer_visibility": (
                self.add_layer_visibility
                if isinstance(self.add_layer_visibility, str)
                else "hidden"
            ),
            "dialog_active_tab_index": (str(self.my_dialog.tbw_central.currentIndex())),
            # store tool-mode ('reorder') for next init
            "tool_mode": (self.tool_mode if isinstance(self.tool_mode, str) else ""),
            "last_user_file": (
                self.last_user_file if isinstance(self.last_user_file, str) else ""
            ),
        }

        # convenience
        # store attached-state as True/False-string for next init
        # independend from self.my_dialog.qtb_toggle_attach.isChecked()
        if self.my_dialog.isFloating():
            config_object["CONFIG"]["dialog_attached"] = "False"
            # position and size as integer-strings
            # note: height measured without title-bar
            config_object["CONFIG"]["dialog_x"] = str(self.my_dialog.x())
            config_object["CONFIG"]["dialog_y"] = str(self.my_dialog.y())
            config_object["CONFIG"]["dialog_width"] = str(self.my_dialog.width())
            config_object["CONFIG"]["dialog_height"] = str(self.my_dialog.height())
        else:
            config_object["CONFIG"]["dialog_attached"] = "True"

        # create ini-file if not existing
        # Exception, if file could not be opened/created
        with open(self.sys_get_ini_path(), "w") as conf:
            config_object.write(conf)

    def sys_get_ini_path(self) -> Path:
        """get path to ini-file
        contains hostname to allow multiple configs dependend on host
        f.e.:
        use QGis from homeoffice => linux or work => windows
        => same Metadata-Geopackage but Layer-Table having two fields for the platform-dependend different paths to container-files

        the ini-file is created with sys_write_config on plugin-unload

        Returns:
            Path: path to ini-file
        """
        # Rev. 2026-11-23
        import socket

        return (
            Path(os.path.dirname(__file__))
            / "user_settings"
            / f"LayerLibUserConfig@{socket.gethostname()}.ini"
        )

    def sys_read_config(self):
        """reads configuration from ini-file located in ini_path
        path to GeoPackage containing Metadata-layers and registered field-names
        the ini-file is created with sys_write_config on plugin-unload
        note: ConfigParser.read() raises no exception, if file does not exist, f.e. on very first usage
        """
        # Rev. 2026-11-23
        config_object = ConfigParser()
        # Keys in der ini-Datei case-sensitive (default: all lowercase)
        # subclasses ConfigParser.optionxform() which defaults to lower()
        config_object.optionxform = str

        config_file_names = config_object.read(self.sys_get_ini_path())

        if config_file_names:

            if config_object.has_section("CONFIG"):
                config_section = config_object["CONFIG"]

                if config_section.get("treeview_source_path") and isinstance(config_section.get("treeview_source_path"),str) and os.path.isfile(config_section.get("treeview_source_path")):
                    self.treeview_source_path = config_section.get("treeview_source_path")

                # should be string
                self.add_layer_visibility = config_section.get("add_layer_visibility")

                # bool stored as True/False-string
                self.dialog_attached = config_section.get("dialog_attached") == "True"

                if config_section.get("dialog_active_tab_index") and config_section.get("dialog_active_tab_index").isdigit():
                    self.dialog_active_tab_index = int(config_section.get("dialog_active_tab_index"))
                else:
                    self.dialog_active_tab_index = 0

                # last detached position and size:
                if config_section.get("dialog_x") and config_section.get("dialog_x").isdigit():
                    self.dialog_x = int(config_section.get("dialog_x"))
                else:
                    self.dialog_x = self.iface.mainWindow().geometry().left() + 100

                if config_section.get("dialog_y") and config_section.get("dialog_y").isdigit():
                    self.dialog_y = int(config_section.get("dialog_y"))
                else:
                    self.dialog_y = self.iface.mainWindow().geometry().top() + 100

                if config_section.get("dialog_width") and config_section.get("dialog_width").isdigit():
                    self.dialog_width = int(config_section.get("dialog_width"))
                else:
                    self.dialog_width = 400

                if config_section.get("dialog_height") and config_section.get("dialog_height").isdigit():
                    self.dialog_height = int(config_section.get("dialog_height"))
                else:
                    self.dialog_height = 600

                if config_section.get("tool_mode") and isinstance(config_section.get("tool_mode"),str):
                    self.tool_mode = config_section.get("tool_mode")

                if config_section.get("last_user_file") and isinstance(config_section.get("last_user_file"),str) and os.path.exists(config_section.get("last_user_file")):
                    self.last_user_file = config_section.get("last_user_file")

    def initGui(self):
        """standard-to-implement-function: adapt/extend GUI
        Triggered
        a. on open QGis with activated plugin (even start QGis with blank project)
        b. on plugin-initialization
        """
        # Rev. 2026-11-24
        self.qact_dlg_show = QAction(
            QIcon(f"{ICON_DIR}/ll_show_dialog.svg"),
            MY_DICT.tr("qact_txt_open_plugin_dialog"),
            self.iface.mainWindow(),
        )

        self.qact_dlg_show.triggered.connect(self.dlg_show)
        self.qact_dlg_show.setEnabled(True)
        # ToolTip for Toolbar-Icon
        self.qact_dlg_show.setToolTip(MY_DICT.tr("qact_ttp_open_plugin_dialog")),

        # add icon to plugin in toolbar and menu
        self.iface.addToolBarIcon(self.qact_dlg_show)

        self.qact_show_help = QAction(
            QIcon(f"{ICON_DIR}/plugin-help.svg"),
            MY_DICT.tr("qact_show_help_txt"),
            self.iface.mainWindow(),
        )

        self.qact_show_help.triggered.connect(self.tool_show_help)
        self.qact_show_help.setEnabled(True)
        # ToolTip for Toolbar-Icon
        self.qact_show_help.setToolTip(MY_DICT.tr("qact_show_help_ttp")),

        # also in menubar
        self.iface.addPluginToMenu("LayerLib", self.qact_dlg_show)
        self.iface.addPluginToMenu("LayerLib", self.qact_show_help)

    def sys_load_treeview_dom_doc(self, treeview_source_path: str) -> bool:
        """
        Try to load treeview_dom_doc (source for QTreeView-model-data)
        set self.treeview_source_path
        set self.treeview_dom_doc



        Args:
            treeview_source_path (str): Path to TreeView-XML-File

        Returns:
            bool: dom_doc_is_valid
        """
        # Rev. 2026-11-24
        self.treeview_dom_doc = None
        self.treeview_source_path = None
        validation_messages = []

        if isinstance(treeview_source_path, str) and treeview_source_path != "":
            if os.path.isfile(treeview_source_path):
                treeview_dom_doc = QDomDocument()

                try:
                    with open(treeview_source_path, "rb", -1) as in_f:
                        in_ba = in_f.read()

                        parse_ok, error_msg, error_line, error_col = (
                            treeview_dom_doc.setContent(in_ba)
                        )
                        if parse_ok:
                            dom_doc_is_valid, dom_doc_modified, validation_messages = (
                                validate_treeview_dom_doc(treeview_dom_doc)
                            )

                            if dom_doc_is_valid:
                                # save altered version
                                if dom_doc_modified:
                                    save_treeview_dom_doc(
                                        treeview_dom_doc, treeview_source_path
                                    )

                                self.treeview_source_path = treeview_source_path
                                self.treeview_dom_doc = treeview_dom_doc
                                return True
                        else:
                            validation_messages.append(
                                f"Error parsing TreeView-XML-File:  file '{treeview_source_path}'  error '{error_msg}'  line #{error_line - 1}"
                            )
                except Exception as e:
                    validation_messages.append(
                        f"Error parsing TreeView-XML-File:  file '{treeview_source_path}': {e}"
                    )
            else:
                validation_messages.append(
                    f"Path to TreeView-XML-File '{treeview_source_path}' not found"
                )
        else:
            validation_messages.append("Path to TreeView-XML-File empty")

        show_log_message(
            "CRITICAL",
            MY_DICT.tr(
                "treeview_dom_doc_invalid",
                treeview_source_path,
                "/".join(validation_messages),
            ),
            self.my_dialog.log_message_fqlbl,
            True,
        )
        self.my_dialog.tbw_central.setCurrentIndex(3)

    def st_select_treeview_xml_file(self):
        """User selects another XML-File"""
        # Rev. 2026-11-24
        treeview_source_path = self.create_treeview_xml_file(self.treeview_source_path)

        if treeview_source_path:
            if self.sys_load_treeview_dom_doc(treeview_source_path):
                self.dlg_refresh()
                show_log_message(
                    "SUCCESS",
                    MY_DICT.tr(
                        "settings_complete_msg",
                        self.sys_get_ini_path(),
                        self.treeview_source_path,
                    ),
                    self.my_dialog.log_message_fqlbl,
                )
                self.my_dialog.tbw_central.setCurrentIndex(0)

    def dlg_show(self):
        """show self.my_dialog
        Note:
        dialog is already initialized with __init__ but not filled with data and hidden
        """
        # Rev. 2026-11-24

        if self.first_called:
            # self.dialog_attached True (False, if restored from ini floating)
            self.my_dialog.toggle_attach(self.dialog_attached)

            if not self.dialog_attached:
                self.my_dialog.move(self.dialog_x, self.dialog_y)
                self.my_dialog.resize(self.dialog_width, self.dialog_height)

            self.iface.addTabifiedDockWidget(
                Qt.DockWidgetArea.LeftDockWidgetArea,
                self.my_dialog,
                # first match used:
                ["Layers"],
                True,
            )

            # pre-checks
            ini_path_posix = self.sys_get_ini_path()

            if (
                not ini_path_posix.is_file()
                or not isinstance(self.treeview_source_path, str)
                or not os.path.isfile(self.treeview_source_path)
            ):
                # very first use after plugin-install
                QMessageBox.about(
                    None,
                    MY_DICT.tr("first_use_dlg_title"),
                    MY_DICT.tr("first_use_dlg_msg"),
                )
                treeview_source_path = self.create_treeview_xml_file()

            else:
                treeview_source_path = self.treeview_source_path

            if self.sys_load_treeview_dom_doc(treeview_source_path):

                show_log_message(
                    "SUCCESS",
                    MY_DICT.tr(
                        "settings_complete_msg",
                        self.sys_get_ini_path(),
                        self.treeview_source_path,
                    ),
                )

            # first data-load:
            self.dlg_refresh()
            self.first_called = False
            self.my_dialog.tbw_central.setCurrentIndex(self.dialog_active_tab_index)

        else:
            # normal show, f.e. if the user has closed dialog-window (QT: dialog.close() = dialog.setVisible(False))
            self.my_dialog.setWindowState(
                self.my_dialog.windowState() & ~Qt.WindowState.WindowMinimized
                | Qt.WindowState.WindowActive
            )

            self.my_dialog.show()
            self.my_dialog.setFocus()
            self.my_dialog.raise_()

    def create_treeview_xml_file(self, prev_treeview_source_path: str = None) -> str:
        """create or select TreeView-XML-File
        Function used if no TreeView-domdoc is set (f.e. first plugin-usage)
        or if he selects another XML-File or wants to create a new one

        Returns:
            str: path to existing (not truncated) or new created TreeView-XML-File
        """
        # Rev. 2026-11-23
        default_dir = get_valid_file([prev_treeview_source_path, self.last_user_file])

        # getSaveFileName ohne "Confirm Overwrite" bei bereits vorhandener Datei
        options = QFileDialog().options() | QFileDialog.Option.DontConfirmOverwrite
        treeview_source_path, filter = QFileDialog.getSaveFileName(
            None,
            MY_DICT.tr("dlg_create_treeview_xml_file_title"),
            default_dir,
            filter="TreeView-XML-File *.xml (*.xml)",
            options=options,
        )

        if treeview_source_path:
            treeview_source_path_posix = Path(treeview_source_path)
            if treeview_source_path_posix.suffix != ".xml":
                # should not happen with above defined filter
                treeview_source_path_posix = Path(f"{treeview_source_path_posix}.xml")

            if treeview_source_path_posix.exists():
                # existing xml-file selected => don't touch
                return treeview_source_path_posix.as_posix()
            else:
                # create new file if it doesn't exist
                treeview_source_path_posix.touch()
                if treeview_source_path_posix.exists():
                    # doctype-declaration functionally not necessary, but delivers hints about structure/attributes... for external XML-Editors
                    blank_template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE folder
[
    <!ELEMENT folder (label,description,(folder*,resource*)*)>
    <!ELEMENT resource (label,description,path)>
    <!ELEMENT label (#PCDATA)>
    <!ELEMENT description (#PCDATA)>
    <!ELEMENT path (#PCDATA)>
    <!ATTLIST folder id ID #REQUIRED>
    <!ATTLIST resource id ID #REQUIRED>
]>
<folder id='root'>
    <label><![CDATA[Root]]></label>
    <description><![CDATA[Top-Level Folder]]></description>
</folder>"""

                    treeview_source_path_posix.write_bytes(blank_template.encode())
                    return treeview_source_path_posix.as_posix()

    def dlg_init(self) -> LayerLibDialog:
        """initialize dialog (connect signals, register functions...)
        Note:
        dialog is initialized with __init__, but has no data and is hidden"""
        # Rev. 2026-11-23

        # spacer in front to achieve right alignment
        self.my_dialog.qtb_lib_tab.addWidget(MyToolbarSpacer())

        self.qact_toggle_tool_mode = QAction(
            QIcon(f"{ICON_DIR}/reorder_structure.svg"),
            "Toggle Tool-Mode",
            self.my_dialog,
        )
        self.qact_toggle_tool_mode.setToolTip(MY_DICT.tr("qtb_toggle_tool_mode_ttp"))
        self.qact_toggle_tool_mode.setCheckable(True)

        self.qact_toggle_tool_mode.toggled.connect(self.sys_set_tool_mode)
        self.my_dialog.qtb_lib_tab.addAction(self.qact_toggle_tool_mode)

        self.qact_new_folder = QAction(
            QIcon(f"{ICON_DIR}/new_folder.svg"), "New Folder", self.my_dialog
        )
        self.qact_new_folder.setToolTip(MY_DICT.tr("qtb_new_folder_ttp"))

        self.qact_new_folder.triggered.connect(self.st_create_folder)
        self.my_dialog.qtb_lib_tab.addAction(self.qact_new_folder)

        self.qact_new_layer = QAction(
            QIcon(f"{ICON_DIR}/new_container.svg"), "New Layer", self.my_dialog
        )
        self.qact_new_layer.setToolTip(MY_DICT.tr("qtb_add_resource_ttp"))
        self.qact_new_layer.triggered.connect(self.st_create_resource)

        self.my_dialog.qtb_lib_tab.addAction(self.qact_new_layer)

        self.qact_refresh = QAction(
            QIcon(f"{ICON_DIR}/mActionRefresh.svg"),
            "Refresh dialog",
            self.my_dialog,
        )
        self.qact_refresh.setToolTip(MY_DICT.tr("qtb_refresh_ttp"))
        self.qact_refresh.triggered.connect(self.dlg_refresh)

        self.my_dialog.qtb_lib_tab.addAction(self.qact_refresh)

        self.my_dialog.qtb_show_help.clicked.connect(self.tool_show_help)

        self.my_dialog.qpb_expand_all.clicked.connect(self.st_expand_all)
        self.my_dialog.qpb_collapse_all.clicked.connect(self.st_collapse_all)


        self.my_dialog.treeview_source_path_qle.pressed.connect(self.st_select_treeview_xml_file)

        self.my_dialog.qpb_start_search.clicked.connect(self.st_search_in_qtrv)
        self.my_dialog.qle_search.returnPressed.connect(self.st_search_in_qtrv)

        self.my_dialog.select_treeview_xml_file_qpb.pressed.connect(
            self.st_select_treeview_xml_file
        )

        self.my_dialog.add_layer_visibility_qcbx.currentIndexChanged.connect(
            self.dlg_settings_to_config
        )

        self.my_dialog.qtrv_layer_lib.dropped.connect(self.st_eval_qtrv_drop_event)

        self.my_dialog.qtrv_layer_lib.delegates[0].cell_button_pressed.connect(
            self.st_qtrv_layer_lib_cell_button_pressed
        )
        self.my_dialog.qtrv_layer_lib.delegates[1].cell_button_pressed.connect(
            self.st_qtrv_layer_lib_cell_button_pressed
        )

        self.my_dialog.qpb_detect_invalid_paths.pressed.connect(
            self.st_detect_invalid_paths
        )
        self.my_dialog.qpb_detect_invalid_container_paths.pressed.connect(
            self.st_detect_invalid_container_paths
        )
        self.my_dialog.qle_search_path.returnPressed.connect(self.st_search_in_paths)
        self.my_dialog.qpb_search_in_paths.pressed.connect(self.st_search_in_paths)

        self.my_dialog.qle_replace_path.returnPressed.connect(self.st_replace_in_paths)
        self.my_dialog.qpb_replace_in_paths.pressed.connect(self.st_replace_in_paths)

        self.my_dialog.qpb_convert_paths_relative.pressed.connect(
            self.st_convert_paths_relative
        )

        self.my_dialog.qpb_convert_paths_absolute.pressed.connect(
            self.st_convert_paths_absolute
        )

        self.my_dialog.inspect_layer_drop_area.anchorClicked.connect(
            self.tool_evaluate_storable_resource
        )
        # drag-events are connected and handled in dialog

        self.dlg_show_tool_mode()

    def st_qtrv_layer_lib_cell_button_pressed(
        self, model_idx: QModelIndex, icon_nbr: int, icon_idx: int
    ):
        """QTreeView-functionalities:
        connected to cell_button_pressed-signal triggered by click on icon from delegate

        Args:
            model_idx (QModelIndex): get data from QStandardItem where the icon was clicked
            icon_nbr (int): number of icon
            icon_idx (int): key of item in dictionary delegate.qIcons
        """
        # Rev. 2026-11-23

        if model_idx.column() == 0:
            folder_id = model_idx.data(QT_ROLES.FOLDER_ID)
            resource_id = model_idx.data(QT_ROLES.RESOURCE_ID)
            if folder_id:
                if icon_nbr == 0:
                    self.edit_folder_dialog.enable_update(folder_id)
                    self.edit_folder_dialog.show()
                    self.edit_folder_dialog.setFocus()
                    self.edit_folder_dialog.raise_()
                elif icon_nbr == 1:
                    # if model_idx.data(QT_ROLES.EDITABLE):
                    if self.tool_mode == "reorder":
                        self.st_remove_folder_from_library(folder_id)
            elif resource_id:
                if icon_nbr == 0:
                    self.edit_resource_dialog.enable_update(resource_id)
                    self.edit_resource_dialog.show()
                    self.edit_resource_dialog.setFocus()
                    self.edit_resource_dialog.raise_()
                elif icon_nbr == 1:
                    if model_idx.data(QT_ROLES.ENABLED):
                        self.st_load_resource_layers(resource_id)
                elif icon_nbr == 2:
                    # if model_idx.data(QT_ROLES.EDITABLE):
                    if self.tool_mode == "reorder":
                        self.st_remove_resource_from_library(resource_id)

    def st_search_in_paths(self):
        """Search in path-attributes of LayerLib-contents"""
        # Rev. 2026-11-23
        self.my_dialog.qpte_result_log.clear()
        self.my_dialog.qpte_result_log.appendPlainText(f"Search in resource-paths:")

        # clear current selection, perhaps from previous call
        if self.my_dialog.qtrv_layer_lib.model():
            self.my_dialog.qtrv_layer_lib.selectionModel().clear()

            search_value = self.my_dialog.qle_search_path.text()
            if search_value != "":
                column_settings = [
                    [
                        2,
                        Qt.ItemDataRole.DisplayRole,
                        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
                    ],
                ]

                found_idcs = self.my_dialog.qtrv_layer_lib.select_by_value(
                    column_settings, search_value, -1
                )

                if found_idcs:
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"Found '{search_value}' in {len(found_idcs)} resources (selected in TreeView)"
                    )
                else:
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"No resources with '{search_value}'"
                    )
            else:
                self.my_dialog.qpte_result_log.appendPlainText(
                    f"No search-value entered"
                )

    def st_replace_in_paths(self):
        """
        search and replace in path-attributes of LayerLib-contents
        """
        # Rev. 2026-11-23
        self.my_dialog.qpte_result_log.clear()
        self.my_dialog.qpte_result_log.appendPlainText(
            f"Search and replace in resource-paths:"
        )

        # clear current selection, perhaps from previous call
        if self.my_dialog.qtrv_layer_lib.model():
            self.my_dialog.qtrv_layer_lib.selectionModel().clear()
            search_value = self.my_dialog.qle_search_path.text()
            # may be ''
            replace_value = self.my_dialog.qle_replace_path.text()
            if search_value != "":

                column_settings = [
                    [
                        2,
                        Qt.ItemDataRole.DisplayRole,
                        Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
                    ],
                ]

                found_idcs = self.my_dialog.qtrv_layer_lib.select_by_value(
                    column_settings, search_value, -1
                )

                if found_idcs:
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"Found {len(found_idcs)} resources with '{search_value} (selected in TreeView)"
                    )
                    # security check before replacement
                    dialog_result = QMessageBox.question(
                        None,
                        MY_DICT.tr("dlg_confirm_replace_in_paths_title"),
                        MY_DICT.tr(
                            "dlg_confirm_replace_in_paths_text",
                            search_value,
                            len(found_idcs),
                            replace_value,
                        ),
                        buttons=QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                        defaultButton=QMessageBox.StandardButton.No,
                    )

                    if dialog_result == QMessageBox.StandardButton.Yes:
                        # same procedure, but now traversing the treeview_dom_doc instead of search in QTreeView...
                        # ... and with replace now
                        search_value_esc = re.escape(search_value)
                        resource_nodes = self.treeview_dom_doc.elementsByTagName(
                            "resource"
                        )
                        replace_resource_ids = []
                        for resource_node in (
                            resource_nodes.at(i) for i in range(resource_nodes.size())
                        ):
                            resource_id = resource_node.toElement().attribute("id")

                            resource_path = (
                                resource_node.namedItem("path")
                                .firstChild()
                                .toText()
                                .data()
                            )

                            if re.search(search_value_esc, resource_path):

                                new_resource_path = re.sub(
                                    search_value_esc, replace_value, resource_path
                                )
                                resource_node.namedItem(
                                    "path"
                                ).firstChild().setNodeValue(new_resource_path)
                                replace_resource_ids.append(resource_id)

                        save_treeview_dom_doc(
                            self.treeview_dom_doc, self.treeview_source_path
                        )
                        self.dlg_refresh_qtrv()
                        QTimer.singleShot(
                            100,
                            lambda replace_layer_ids=replace_resource_ids: self.my_dialog.qtrv_layer_lib.select_resources(
                                replace_layer_ids
                            ),
                        )
                        self.my_dialog.qpte_result_log.appendPlainText(
                            f"Found and replaced '{search_value}' -> '{replace_value}' in {len(found_idcs)} resources (selected in TreeView)"
                        )

                else:
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"No resources with '{search_value}'"
                    )
            else:
                self.my_dialog.qpte_result_log.appendPlainText(
                    f"No search-value entered"
                )

    def st_convert_paths_relative(self):
        """Convert all paths in Library relative to Treview-XML-File
        especially usefull for libraries used on Linux and Windows
        """
        # Rev. 2026-11-23
        self.my_dialog.qpte_result_log.clear()
        self.my_dialog.qpte_result_log.appendPlainText(
            f"Convert absolute paths to relative paths in library-resources:"
        )

        # clear current selection, perhaps from previous call
        if self.my_dialog.qtrv_layer_lib.model():
            self.my_dialog.qtrv_layer_lib.selectionModel().clear()
            # get a fresh version of treeview_dom_doc to reflect current state
            # self.dlg_refresh_qtrv()
            resource_nodes = self.treeview_dom_doc.elementsByTagName("resource")

            replace_resource_ids = []

            for resource_node in (
                resource_nodes.at(i) for i in range(resource_nodes.size())
            ):
                resource_id = resource_node.toElement().attribute("id")
                resource_label = (
                    resource_node.namedItem("label").firstChild().toText().data()
                )

                resource_path = (
                    resource_node.namedItem("path").firstChild().toText().data()
                )
                # avoid "TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'QVariant'"
                # backslashes should not occure, since paths are allways updated/inserted "as_posix"
                # but treeview-xml-file could be edited manually
                resource_path = resource_path.replace("\\", "/")

                abs_path = get_absolute_path(resource_path, self.treeview_source_path)

                if abs_path:
                    if abs_path == resource_path:
                        replace_resource_ids.append(resource_id)
                else:
                    # all layers without or empty <path></path> rsp. <path><![CDATA[]]></path> or not found paths
                    self.my_dialog.qpte_result_log.appendPlainText(f" - Invalid path:")
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"      resource '{resource_label}'"
                    )
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"      path '{resource_path}'"
                    )

            if replace_resource_ids:
                QTimer.singleShot(
                    100,
                    lambda replace_layer_ids=replace_resource_ids: self.my_dialog.qtrv_layer_lib.select_resources(
                        replace_layer_ids
                    ),
                )
                self.my_dialog.qpte_result_log.appendPlainText(
                    f"Found {len(replace_resource_ids)} resources with absolute paths (selected in TreeView)"
                )
                # security check before replacement
                dialog_result = QMessageBox.question(
                    None,
                    MY_DICT.tr("dlg_confirm_convert_paths_relative_title"),
                    MY_DICT.tr(
                        "dlg_confirm_convert_paths_relative_txt",
                        len(replace_resource_ids),
                    ),
                    buttons=QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    defaultButton=QMessageBox.StandardButton.No,
                )

                if dialog_result == QMessageBox.StandardButton.Yes:
                    # same procedure, but with replacement
                    resource_nodes = self.treeview_dom_doc.elementsByTagName("resource")
                    replace_resource_ids = []
                    for resource_node in (
                        resource_nodes.at(i) for i in range(resource_nodes.size())
                    ):
                        resource_id = resource_node.toElement().attribute("id")

                        resource_path = (
                            resource_node.namedItem("path").firstChild().toText().data()
                        )

                        # backslashes should not occure, since paths are allways updated/inserted "as_posix", also in windows
                        # but treeview-xml-file could be edited manually
                        resource_path = resource_path.replace("\\", "/")
                        abs_path = get_absolute_path(
                            resource_path, self.treeview_source_path
                        )
                        if abs_path:
                            if abs_path == resource_path:
                                rel_path = get_relative_path(
                                    abs_path, self.treeview_source_path
                                )
                                if rel_path:
                                    resource_node.namedItem(
                                        "path"
                                    ).firstChild().setNodeValue(rel_path)
                                    replace_resource_ids.append(resource_id)
                                else:
                                    self.my_dialog.qpte_result_log.appendPlainText(
                                        f" - path not convertable, different anchors/drives:"
                                    )
                                    self.my_dialog.qpte_result_log.appendPlainText(
                                        f"      resource '{resource_label}'"
                                    )
                                    self.my_dialog.qpte_result_log.appendPlainText(
                                        f"      path '{resource_path}'"
                                    )

                        else:
                            self.my_dialog.qpte_result_log.appendPlainText(
                                f" - Path-convert-exception:"
                            )
                            self.my_dialog.qpte_result_log.appendPlainText(
                                f"      resource '{resource_label}'"
                            )
                            self.my_dialog.qpte_result_log.appendPlainText(
                                f"      path '{resource_path}'"
                            )

                    save_treeview_dom_doc(
                        self.treeview_dom_doc, self.treeview_source_path
                    )
                    self.dlg_refresh_qtrv()

                    QTimer.singleShot(
                        100,
                        lambda replace_layer_ids=replace_resource_ids: self.my_dialog.qtrv_layer_lib.select_resources(
                            replace_layer_ids
                        ),
                    )
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"Found and altered {len(replace_resource_ids)} resources with absolute paths (selected in TreeView)"
                    )

            else:
                self.my_dialog.qpte_result_log.appendPlainText("No resources found")

    def st_convert_paths_absolute(self):
        """Convert all paths in Library absolute to Treview-XML-File"""
        # Rev. 2026-11-23
        self.my_dialog.qpte_result_log.clear()
        self.my_dialog.qpte_result_log.appendPlainText(
            f"Convert relative paths to absolute paths in library-resources:"
        )

        # clear current selection, perhaps from previous call
        if self.my_dialog.qtrv_layer_lib.model():
            self.my_dialog.qtrv_layer_lib.selectionModel().clear()

            # get a fresh version of treeview_dom_doc to reflect current state
            # self.dlg_refresh_qtrv()
            resource_nodes = self.treeview_dom_doc.elementsByTagName("resource")

            replace_resource_ids = []

            for layer_node in (
                resource_nodes.at(i) for i in range(resource_nodes.size())
            ):
                resource_id = layer_node.toElement().attribute("id")
                resource_label = (
                    layer_node.namedItem("label").firstChild().toText().data()
                )

                resource_path = (
                    layer_node.namedItem("path").firstChild().toText().data()
                )
                # avoid "TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'QVariant'"
                # backslashes should not occure, since paths are allways updated/inserted "as_posix"
                # but treeview-xml-file could be edited manually
                resource_path = resource_path.replace("\\", "/")

                abs_path = get_absolute_path(resource_path, self.treeview_source_path)
                if abs_path:
                    if abs_path != resource_path:
                        replace_resource_ids.append(resource_id)
                else:
                    # all layers without or empty <path></path> rsp. <path><![CDATA[]]></path> or not found paths
                    self.my_dialog.qpte_result_log.appendPlainText(f" - Invalid path:")
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"      resource '{resource_label}'"
                    )
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"      path '{resource_path}'"
                    )

            if replace_resource_ids:
                QTimer.singleShot(
                    100,
                    lambda replace_layer_ids=replace_resource_ids: self.my_dialog.qtrv_layer_lib.select_resources(
                        replace_layer_ids
                    ),
                )
                self.my_dialog.qpte_result_log.appendPlainText(
                    f"Found {len(replace_resource_ids)} resources with absolute paths (selected in TreeView)"
                )
                # security check before replacement
                dialog_result = QMessageBox.question(
                    None,
                    MY_DICT.tr("dlg_confirm_convert_paths_absolute_title"),
                    MY_DICT.tr(
                        "dlg_confirm_convert_paths_absolute_txt",
                        len(replace_resource_ids),
                    ),
                    buttons=QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    defaultButton=QMessageBox.StandardButton.No,
                )

                if dialog_result == QMessageBox.StandardButton.Yes:
                    # same procedure, but with replacement
                    resource_nodes = self.treeview_dom_doc.elementsByTagName("resource")
                    replace_resource_ids = []
                    for layer_node in (
                        resource_nodes.at(i) for i in range(resource_nodes.size())
                    ):
                        resource_id = layer_node.toElement().attribute("id")

                        resource_path = (
                            layer_node.namedItem("path").firstChild().toText().data()
                        )

                        # backslashes should not occure, since paths are allways updated/inserted "as_posix"
                        # but treeview-xml-file could be edited manually
                        resource_path = resource_path.replace("\\", "/")
                        abs_path = get_absolute_path(
                            resource_path, self.treeview_source_path
                        )
                        if abs_path:
                            if abs_path != resource_path:
                                layer_node.namedItem("path").firstChild().setNodeValue(
                                    abs_path
                                )
                                replace_resource_ids.append(resource_id)

                        else:
                            self.my_dialog.qpte_result_log.appendPlainText(
                                f" - path not convertable:"
                            )
                            self.my_dialog.qpte_result_log.appendPlainText(
                                f"      resource '{resource_label}'"
                            )
                            self.my_dialog.qpte_result_log.appendPlainText(
                                f"      path '{resource_path}'"
                            )

                    save_treeview_dom_doc(
                        self.treeview_dom_doc, self.treeview_source_path
                    )
                    self.dlg_refresh_qtrv()
                    QTimer.singleShot(
                        100,
                        lambda replace_layer_ids=replace_resource_ids: self.my_dialog.qtrv_layer_lib.select_resources(
                            replace_layer_ids
                        ),
                    )

                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"Found and altered {len(replace_resource_ids)} resources with relative paths (selected in TreeView)"
                    )
            else:
                self.my_dialog.qpte_result_log.appendPlainText("No resources found")

    def st_detect_invalid_paths(self):
        """LayerLib-Contents are references to files (qgs/qgz/qlr/vector/raster)
        the stored (absolute or relative) path is important
        invalid-paths can occur, if the referenced files are moved/deleted, or if the folder structure is altered,
        or (in my case) the treeview-file is synced in the cloud and used (with the same folder-structure) in windows and linux,
        c:/users/my_name/.../my_project.qgz (the plugin stores paths always .as_posix() => forward slashes also on windows)
        vs.
        /home/my_name/.../my_project.qgz
        This function checks all path-attributes and selects the invalid ones in TreeView
        """
        # Rev. 2026-11-23
        self.my_dialog.qpte_result_log.clear()
        self.my_dialog.qpte_result_log.appendPlainText(
            f"Detect invalid paths in library-resources:"
        )

        # clear current selection, perhaps from previous call
        if self.my_dialog.qtrv_layer_lib.model():
            self.my_dialog.qtrv_layer_lib.selectionModel().clear()

            # get a fresh version of treeview_dom_doc to reflect current state
            # self.dlg_refresh_qtrv()
            resource_nodes = self.treeview_dom_doc.elementsByTagName("resource")
            # all resources-ids with invalid path => file not found
            invalid_path_resource_ids = {}

            for resource_node in (
                resource_nodes.at(i) for i in range(resource_nodes.size())
            ):
                resource_id = resource_node.toElement().attribute("id")

                file_path = resource_node.namedItem("path").firstChild().toText().data()
                # avoid "TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'QVariant'"
                try:

                    # backslashes should not occure, since paths are allways updated/inserted "as_posix"
                    # but treeview-xml-file could be edited manually
                    file_path = file_path.replace("\\", "/")

                    if not get_absolute_path(file_path, self.treeview_source_path):
                        invalid_path_resource_ids[resource_id] = file_path

                except Exception as e:
                    # layer_label = layer_node.namedItem("label").firstChild().toText().data()
                    # all layers without or empty <path></path> rsp. <path><![CDATA[]]></path> or not found paths
                    # self.my_dialog.qpte_result_log.appendPlainText(f" - Invalid path:")
                    # self.my_dialog.qpte_result_log.appendPlainText(f"      resource '{layer_label}'")
                    # self.my_dialog.qpte_result_log.appendPlainText(f"      path '{file_path}'")
                    # self.my_dialog.qpte_result_log.appendPlainText(f"      Error '{e}'")
                    invalid_path_resource_ids[resource_id] = file_path

            if invalid_path_resource_ids:
                QTimer.singleShot(
                    100,
                    lambda invalid_path_layer_ids=list(
                        invalid_path_resource_ids.keys()
                    ): self.my_dialog.qtrv_layer_lib.select_resources(
                        invalid_path_layer_ids
                    ),
                )
                self.my_dialog.qpte_result_log.appendPlainText(
                    f"Found {len(invalid_path_resource_ids)} resources with invalid paths (selected in TreeView)"
                )
            else:
                self.my_dialog.qpte_result_log.appendPlainText(
                    "No resources with invalid paths found"
                )

    def st_detect_invalid_container_paths(self):
        """container-files (qlg/qgz/qlr) store paths to their layers in the datasource-attribute
        File-based datasources are checked here (most QGis-Users know the dialog with the layers that can't be found when opening older projects...)
        This function opens the container-files, searches for file-based datasources and checks the path and selects the container-files with invalid ones in TreeView
        """
        # Rev. 2026-11-23

        self.my_dialog.qpte_result_log.clear()
        self.my_dialog.qpte_result_log.appendPlainText(
            "Detect resources/container-files with invalid datasource-paths:"
        )

        # clear current selection, perhaps from previous call
        if self.my_dialog.qtrv_layer_lib.model():
            self.my_dialog.qtrv_layer_lib.selectionModel().clear()

            # get a fresh version of treeview_dom_doc to reflect current state
            # self.dlg_refresh_qtrv()

            resource_nodes = self.treeview_dom_doc.elementsByTagName("resource")

            # resource-ids of container-files with invalid datasource-path
            # key: resource_id
            # value: invalid path
            datasource_not_found_resource_ids = {}

            for resource_node in (
                resource_nodes.at(i) for i in range(resource_nodes.size())
            ):
                resource_id = resource_node.toElement().attribute("id")
                resource_label = (
                    resource_node.namedItem("label").firstChild().toText().data()
                )
                resource_path = (
                    resource_node.namedItem("path").firstChild().toText().data()
                )

                # avoid "TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'QVariant'"
                if isinstance(resource_path, str) and resource_path != "":

                    resource_path_abs = get_absolute_path(
                        resource_path, self.treeview_source_path
                    )
                    if resource_path_abs:
                        resource_path_posix = Path(resource_path_abs)

                        file_suffix = str.lower(resource_path_posix.suffix.lstrip("."))
                        if file_suffix in CONTAINER_EXTENSIONS:
                            try:
                                dom_doc = get_container_file_dom_doc(
                                    resource_path_posix.as_posix()
                                )

                                maplayer_nodes = dom_doc.elementsByTagName("maplayer")
                                for maplayer_node in (
                                    maplayer_nodes.at(i)
                                    for i in range(maplayer_nodes.size())
                                ):
                                    maplayer_id = (
                                        maplayer_node.namedItem("id")
                                        .firstChild()
                                        .toText()
                                        .data()
                                    )

                                    maplayer_name = (
                                        maplayer_node.namedItem("layername")
                                        .firstChild()
                                        .toText()
                                        .data()
                                    )
                                    # force to lowercase, because sometimes "WFS" instead of "wfs"
                                    provider = (
                                        maplayer_node.namedItem("provider")
                                        .firstChild()
                                        .toText()
                                        .data()
                                        .lower()
                                    )
                                    if provider in ["ogr", "gdal"]:

                                        # file-based datasource => check path
                                        datasource = (
                                            maplayer_node.namedItem("datasource")
                                            .firstChild()
                                            .toText()
                                            .data()
                                        )

                                        # may contain more than path, f.e. ../layer/GSK.gpkg|layername=gsk3c_einzugsgebiete|subset="gsk_ezg_gebkz" LIKE '282%'
                                        datasource_parts = datasource.split("|")
                                        datasource_path = datasource_parts[0]

                                        datasource_path_abs = get_absolute_path(
                                            datasource_path, resource_path_abs
                                        )

                                        if not datasource_path_abs:

                                            if (
                                                not resource_id
                                                in datasource_not_found_resource_ids
                                            ):
                                                datasource_not_found_resource_ids[
                                                    resource_id
                                                ] = []
                                            datasource_not_found_resource_ids[
                                                resource_id
                                            ].append(datasource_path)
                                            self.my_dialog.qpte_result_log.appendPlainText(
                                                f" - Datasource not found:"
                                            )
                                            self.my_dialog.qpte_result_log.appendPlainText(
                                                f"      resource '{resource_label}'"
                                            )
                                            self.my_dialog.qpte_result_log.appendPlainText(
                                                f"      maplayer '{maplayer_name}'"
                                            )
                                            self.my_dialog.qpte_result_log.appendPlainText(
                                                f"      datasource-Path '{datasource_path}'"
                                            )
                                    else:
                                        # provider not file based, f.e. database-connection => no check
                                        pass
                            except Exception as e:
                                # qlr/qgs/qgz-file could not be parsed, f.e. manipulated and invalid xml
                                self.my_dialog.qpte_result_log.appendPlainText(
                                    f" - File not parseable:"
                                )
                                self.my_dialog.qpte_result_log.appendPlainText(
                                    f"      resource '{resource_label}'"
                                )
                                self.my_dialog.qpte_result_log.appendPlainText(
                                    f"      maplayer '{maplayer_name}'"
                                )
                                self.my_dialog.qpte_result_log.appendPlainText(
                                    f"      Error '{e}'"
                                )
                        else:
                            # no container-file, no datasource-problems
                            pass
                    else:
                        self.my_dialog.qpte_result_log.appendPlainText(
                            f" - File not found:"
                        )
                        self.my_dialog.qpte_result_log.appendPlainText(
                            f"      resource '{resource_label}'"
                        )
                        self.my_dialog.qpte_result_log.appendPlainText(
                            f"      maplayer '{maplayer_name}'"
                        )
                        self.my_dialog.qpte_result_log.appendPlainText(
                            f"      path '{resource_path}'"
                        )

                else:
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f" - Missing path attribute:"
                    )
                    self.my_dialog.qpte_result_log.appendPlainText(
                        f"      resource '{resource_label}'"
                    )

            if datasource_not_found_resource_ids:
                self.my_dialog.qpte_result_log.appendPlainText(
                    f"Found {len(datasource_not_found_resource_ids)} resources/container-files with invalid datasource-paths (selected in TreeView)"
                )
                QTimer.singleShot(
                    100,
                    lambda datasource_not_found_layer_ids=list(
                        datasource_not_found_resource_ids.keys()
                    ): self.my_dialog.qtrv_layer_lib.select_resources(
                        datasource_not_found_layer_ids
                    ),
                )
            else:
                self.my_dialog.qpte_result_log.appendPlainText(
                    "No resources/container-files with invalid datasource-paths detected"
                )

    def st_eval_qtrv_drop_event(
        self, evt: QDropEvent, evt_val: str, evt_val_type: str, evt_idx: QModelIndex
    ):
        """slot for self.my_dialog.qtrv_layer_lib.dropped
        Note:
            signal only emitted for valid drag-objects (QTreeView-internal layers/folder) and self.tool_mode == "reorder",
            so no more check here
            evt is already accepted/rejected

        Args:
            evt (QDropEvent): the event itself
            evt_val (str): the event-value (resource_id/folder_id/resource_path)
            evt_val_type (str): resource_id/folder_id/resource_path
            evt_idx (QModelIndex): index, where the event happened (column 0 => QT_ROLES.FOLDER_ID or QT_ROLES.RESOURCE_ID)
        """
        # Rev. 2026-11-23

        # sometimes occuring and disturbing side-effect:
        # dropping something on folder/resource can start new drag (reorder folder or resource)
        QDrag.cancel()
        # https://doc.qt.io/qt-6.12/qdrag.html#cancel:
        # Cancels a drag operation initiated by Qt.
        # Note: This is currently implemented on Windows and X11.
        # and not under Qt6 + linux/wayland...?

        if evt_idx.data(QT_ROLES.FOLDER_ID):
            # dropped on folder-item
            drop_folder_id = evt_idx.data(QT_ROLES.FOLDER_ID)
        else:
            # dropped on resource-item => use parent folder
            drop_folder_id = evt_idx.parent().data(QT_ROLES.FOLDER_ID)

        if evt_val_type == "resource_path":
            # dropped valid resource from file-system or QGis-browser-panel
            # single-file, local-file, file-exists, correct-suffix... already checked
            self.my_dialog.qtrv_layer_lib.open_folder(drop_folder_id)

            resource_path = evt_val
            self.add_resource_dialog.enable_insert(resource_path, drop_folder_id)
            self.add_resource_dialog.show()
            self.add_resource_dialog.setFocus()
            self.add_resource_dialog.raise_()
        elif evt_val_type == "folder_id":
            # internal reorder of folder
            drag_folder_id = evt_val
            drag_folder_node = get_folder_node(self.treeview_dom_doc, drag_folder_id)
            drop_folder_node = get_folder_node(self.treeview_dom_doc, drop_folder_id)
            if drag_folder_node and drop_folder_node:
                drag_folder_label = (
                    drag_folder_node.namedItem("label").firstChild().toText().data()
                )
                drop_folder_label = (
                    drop_folder_node.namedItem("label").firstChild().toText().data()
                )
                # check 1: if folder should be moved to itself or to sub-node, which is not allowed/possible (prevents also move of root-node):
                sub_folder_ids = [drag_folder_id]
                sub_folder_nodes = drag_folder_node.toElement().elementsByTagName(
                    "folder"
                )
                for sub_folder_node in (
                    sub_folder_nodes.at(i) for i in range(sub_folder_nodes.size())
                ):
                    sub_folder_ids.append(sub_folder_node.toElement().attribute("id"))

                if drop_folder_id not in sub_folder_ids:
                    # check 2: move folder to parent-folder-node (would not change structure)
                    parent_folder_id = (
                        drag_folder_node.toElement()
                        .parentNode()
                        .toElement()
                        .attribute("id")
                    )
                    if drop_folder_id != parent_folder_id:

                        self.my_dialog.log_message_fqlbl.clear()
                        drag_folder_node.parentNode().removeChild(drag_folder_node)
                        drop_folder_node.appendChild(drag_folder_node)
                        save_treeview_dom_doc(
                            self.treeview_dom_doc,
                            self.treeview_source_path,
                        )
                        self.dlg_refresh_qtrv()
                        QTimer.singleShot(
                            100,
                            lambda drop_folder_id=drop_folder_id: self.my_dialog.qtrv_layer_lib.open_folder(
                                drop_folder_id
                            ),
                        )

                    else:
                        show_log_message(
                            "INFO",
                            f"No need to move folder '{drag_folder_label}' to same parent-folder '{drop_folder_label}'...",
                            self.my_dialog.log_message_fqlbl,
                            True,
                        )
                else:
                    show_log_message(
                        "WARNING",
                        f"Can't move folder '{drag_folder_label}' to itself or sub-nodes",
                        self.my_dialog.log_message_fqlbl,
                        True,
                    )

        elif evt_val_type == "resource_id":
            # internal reorder of resource
            resource_id = evt_val
            resource_node = get_resource_node(self.treeview_dom_doc, resource_id)
            drop_folder_node = get_folder_node(self.treeview_dom_doc, drop_folder_id)
            if resource_node and drop_folder_node:
                resource_label = (
                    resource_node.namedItem("label").firstChild().toText().data()
                )
                drop_folder_label = (
                    drop_folder_node.namedItem("label").firstChild().toText().data()
                )

                parent_folder_id = (
                    resource_node.toElement().parentNode().toElement().attribute("id")
                )

                if drop_folder_id != parent_folder_id:

                    resource_node.parentNode().removeChild(resource_node)
                    drop_folder_node.appendChild(resource_node)
                    save_treeview_dom_doc(
                        self.treeview_dom_doc,
                        self.treeview_source_path,
                    )
                    self.dlg_refresh_qtrv()
                    QTimer.singleShot(
                        100,
                        lambda drop_folder_id=drop_folder_id: self.my_dialog.qtrv_layer_lib.open_folder(
                            drop_folder_id
                        ),
                    )

                else:
                    show_log_message(
                        "INFO",
                        f"No need to move resource '{resource_label}' to same parent-folder '{drop_folder_label}'...",
                        self.my_dialog.log_message_fqlbl,
                        True,
                    )

        elif evt_val_type == "layerdefinitions":
            # drag&drop from QGis-Layers-Panel
            qlr_xml_str = evt_val
            dom_doc = QDomDocument()
            dom_doc.setContent(qlr_xml_str)
            container_path = self.tool_qlr_export(dom_doc)
            if container_path:
                self.add_resource_dialog.enable_insert(
                    container_path,
                    drop_folder_id,
                )
                self.add_resource_dialog.show()
                self.add_resource_dialog.setFocus()
                self.add_resource_dialog.raise_()

    def st_expand_all(self):
        """expand all folder_items"""
        # Rev. 2026-11-23
        # note: self.my_dialog.qtrv_layer_lib.expandAll() would expand all resource-items with populated QTextBrowser
        if self.my_dialog.qtrv_layer_lib.model():
            folder_items = self.my_dialog.qtrv_layer_lib.extract_recursive_items(
                None,
                0,
                QT_ROLES.FOLDER_ID,
            )
            for folder_item in folder_items:
                self.my_dialog.qtrv_layer_lib.setExpanded(folder_item.index(), True)

    def st_collapse_all(self):
        """collapse qtrv_layer_lib"""
        # Rev. 2026-11-23
        self.my_dialog.qtrv_layer_lib.collapseAll()

    def tool_select_resource_by_id(self, resource_id: str):
        """select single resource in qtrv_layer_lib, opens all parent folders

        Args:
            resource_id (str): ID of resource
        """
        # Rev. 2026-11-23
        self.my_dialog.tbw_central.setCurrentIndex(0)
        self.my_dialog.qtrv_layer_lib.select_resource(resource_id)

    def tool_select_folder_by_id(self, folder_id: str):
        """select single folder in qtrv_layer_lib, opens all parent folders

        Args:
            folder_id (str): ID of folder
        """
        # Rev. 2026-11-23
        self.my_dialog.tbw_central.setCurrentIndex(0)
        self.my_dialog.qtrv_layer_lib.select_folder(folder_id)

    def st_search_in_qtrv(self):
        """searches resources in QTreeView by value, compared against DisplayRole in all columns
        result is selected, folders are opened"""
        # Rev. 2026-11-23

        # trim all leading blanks
        search_value = self.my_dialog.qle_search.text().strip()

        if search_value != "":
            column_settings = [
                [
                    0,
                    Qt.ItemDataRole.DisplayRole,
                    Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
                ],
                [
                    1,
                    Qt.ItemDataRole.DisplayRole,
                    Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
                ],
                [
                    2,
                    Qt.ItemDataRole.DisplayRole,
                    Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive,
                ],
            ]

            self.my_dialog.qtrv_layer_lib.select_by_value(
                column_settings, search_value, -1
            )
        else:
            show_log_message(
                "INFO",
                MY_DICT.tr("ifm_info_no_search_value"),
                self.my_dialog.log_message_fqlbl,
                True,
            )

    def dlg_refresh(self):
        """refresh qtrv_layer_lib and settings-tab"""
        # Rev. 2026-11-23
        self.dlg_refresh_settings_tab()
        self.dlg_refresh_qtrv()

    def sys_set_tool_mode(self, checked: bool):
        """toggles tool_mode "reorder" / None
        tool_mode affects RecursiveXMLModel.canDropMimeData() and modifies drag&drop in QTreeView
        Args:
            checked (bool): checked-status from checkable button
        """
        # Rev. 2026-11-23

        self.tool_mode = None

        if self.treeview_dom_doc:
            if checked:
                self.tool_mode = "reorder"

        self.dlg_show_tool_mode()

    def dlg_show_tool_mode(self):
        """show/apply tool-mode in dialog"""
        # Rev. 2026-11-23

        # refresh the trash-icons dependend on tool_mode
        editable_items = self.my_dialog.qtrv_layer_lib.extract_recursive_items(
            None,
            0,
            QT_ROLES.EDITABLE,
        )

        for item in editable_items:
            item.setData(self.tool_mode == "reorder", QT_ROLES.EDITABLE)

        with QSignalBlocker(self.qact_toggle_tool_mode):
            self.qact_toggle_tool_mode.setChecked(self.tool_mode == "reorder")

        if self.tool_mode == "reorder":
            # enable drag&drop
            self.my_dialog.qtrv_layer_lib.viewport().setAcceptDrops(True)
            self.my_dialog.qtrv_layer_lib.setDragDropMode(
                QAbstractItemView.DragDropMode.DragDrop
            )
            # symbolize target with marker
            self.my_dialog.qtrv_layer_lib.setDropIndicatorShown(True)
            # necessary to get target-folder for internal reorder
            self.my_dialog.qtrv_layer_lib.setMouseTracking(True)
        else:
            # disable drag&drop
            self.my_dialog.qtrv_layer_lib.viewport().setAcceptDrops(False)
            self.my_dialog.qtrv_layer_lib.setDragDropMode(
                QAbstractItemView.DragDropMode.DragOnly
            )
            self.my_dialog.qtrv_layer_lib.setDropIndicatorShown(False)
            self.my_dialog.qtrv_layer_lib.setMouseTracking(False)

    def dlg_settings_to_config(self, idx: int = None):
        """read settings-widgets and write to config-ini-file
        triggered by add_layer_visibility_qcbx

        Args:
            idx (int): index of triggered option
        """
        # Rev. 2026-11-23
        self.add_layer_visibility = (
            self.my_dialog.add_layer_visibility_qcbx.currentData()
        )
        self.sys_write_config()

    def dlg_refresh_settings_tab(self):
        """Refresh Settings-Tab in dialog"""
        # Rev. 2026-11-23

        if self.my_dialog:
            # note: treeview_source_path_qle is read-only
            self.my_dialog.treeview_source_path_qle.blockSignals(True)
            self.my_dialog.treeview_source_path_qle.clear()
            if self.treeview_source_path and os.path.isfile(self.treeview_source_path):
                self.my_dialog.treeview_source_path_qle.setText(
                    self.treeview_source_path
                )
            self.my_dialog.treeview_source_path_qle.blockSignals(False)

            self.my_dialog.add_layer_visibility_qcbx.blockSignals(True)
            self.my_dialog.add_layer_visibility_qcbx.select_option(
                self.add_layer_visibility
            )
            self.my_dialog.add_layer_visibility_qcbx.blockSignals(False)

    def dlg_refresh_qtrv(self):
        """Refresh QTreeView:
        load/reload data from self.treeview_source_path
        import to qtrv_layer_lib.model
        """
        # Rev. 2026-11-23
        self.qact_toggle_tool_mode.setEnabled(False)
        self.qact_new_folder.setEnabled(False)
        self.qact_new_layer.setEnabled(False)
        self.qact_refresh.setEnabled(False)

        if self.sys_load_treeview_dom_doc(self.treeview_source_path):

            self.qact_toggle_tool_mode.setEnabled(True)
            self.qact_new_folder.setEnabled(True)
            self.qact_new_layer.setEnabled(True)
            self.qact_refresh.setEnabled(True)

            self.my_dialog.qtrv_layer_lib.load_data(self.treeview_dom_doc)

    def st_remove_resource_from_library(self, resource_id):
        """delete registered qgs/qgz/qlr-resource from XML-File via self.resource_id after confirmation"""
        # Rev. 2026-11-23
        resource_node = get_resource_node(self.treeview_dom_doc, resource_id)
        if resource_node:
            resource_label = (
                resource_node.namedItem("label").firstChild().toText().data()
            )

            delete_confirmed = False

            if self.confirm_resource_delete:
                self.my_confirm_dialog.enable_delete_resource(resource_id)

                dialog_result = self.my_confirm_dialog.exec()

                if dialog_result == 1:
                    delete_confirmed = True

                elif dialog_result == 2:
                    delete_confirmed = True
                    # do not ask again...
                    self.confirm_resource_delete = False
            else:
                delete_confirmed = True

            if delete_confirmed:
                resource_node.parentNode().removeChild(resource_node)
                save_treeview_dom_doc(self.treeview_dom_doc, self.treeview_source_path)
                show_log_message(
                    "INFO",
                    MY_DICT.tr("layer_removed_from_library", resource_label),
                    self.my_dialog.log_message_fqlbl,
                )
                self.dlg_refresh_qtrv()
                if self.edit_resource_dialog.resource_id == resource_id:
                    self.edit_resource_dialog.reset_dlg()
                    self.edit_resource_dialog.close()

        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("metadata_for_resource_missing", resource_id),
                self.my_dialog.log_message_fqlbl,
                True,
            )

    def st_remove_folder_from_library(self, folder_id):
        """delete folder and contents (sub-folder, resources) from XML-File via self.folder_id after confirmation"""
        # Rev. 2026-11-23
        folder_node = get_folder_node(self.treeview_dom_doc, folder_id)
        if folder_node:

            if folder_node != self.treeview_dom_doc.documentElement():
                # root-folder can't be deleted
                folder_label = (
                    folder_node.namedItem("label").firstChild().toText().data()
                )

                delete_confirmed = False

                if self.confirm_folder_delete:

                    self.my_confirm_dialog.enable_delete_folder(folder_id)

                    dialog_result = self.my_confirm_dialog.exec()

                    if dialog_result == 1:
                        delete_confirmed = True

                    elif dialog_result == 2:
                        delete_confirmed = True
                        # do not ask again...
                        self.confirm_folder_delete = False
                else:
                    delete_confirmed = True

                if delete_confirmed:

                    folder_node.parentNode().removeChild(folder_node)
                    save_treeview_dom_doc(
                        self.treeview_dom_doc, self.treeview_source_path
                    )
                    show_log_message(
                        "INFO",
                        MY_DICT.tr("folder_removed_from_library", folder_label),
                        self.my_dialog.log_message_fqlbl,
                    )
                    self.dlg_refresh_qtrv()

                    if self.edit_folder_dialog.folder_id == folder_id:
                        self.edit_folder_dialog.reset_dlg()
                        self.edit_folder_dialog.close()

            else:
                # should not happen, Push-Button disabled
                show_log_message(
                    "WARNING",
                    MY_DICT.tr("root_folder_not_deletable"),
                    self.my_dialog.log_message_fqlbl,
                    True,
                )
        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("folder_not_found", folder_id),
                self.my_dialog.log_message_fqlbl,
                True,
            )

    def st_create_folder(self):
        """opens dialog to create new folder in XML-File"""
        # Rev. 2026-11-23
        # convenience: use current selection in TreeView as default-selection for folder_qcbx-QComboBox in EditFolderDialog
        self.add_folder_dialog.enable_insert(self.my_dialog.qtrv_layer_lib.get_selected_folder_id())
        self.add_folder_dialog.show()
        self.add_folder_dialog.setFocus()
        self.add_folder_dialog.raise_()

    def st_create_resource(self):
        """opens dialog to create new resource in XML-File"""
        # Rev. 2026-11-23
        # convenience: use current selection in TreeView as default-selection for folder_qcbx-QComboBox in EditFolderDialog
        self.add_resource_dialog.enable_insert(
            folder_id=self.my_dialog.qtrv_layer_lib.get_selected_folder_id()
        )
        self.add_resource_dialog.show()
        self.add_resource_dialog.setFocus()
        self.add_resource_dialog.raise_()

    def tool_evaluate_storable_resource(self, url: QUrl):
        """triggered by self.inspect_layer_drop_area.anchorClicked

        mutiple actions called via hyperlink:
            show_datasources
            load_container_file_layers
            add_resource_to_library
            load_map_layer
            load_vector_sub_layer
            show_extent
            load_vector_file
            show_gps_point
            load_raster_file

        Args:
            url (QUrl): see https://doc.qt.io/qt-6/qurl.html
                <a href='tool_evaluate_storable_resource?src_action=...&src_dialog=...&src_id=...'>

        """
        # Rev. 2026-11-23

        # https://doc.qt.io/qt-6/qurlquery.html
        # The QUrlQuery class provides a way to manipulate a key-value pairs in a URL's query.

        # https://docs.python.org/3/library/urllib.parse.html
        # quote_plus/unquote_plus escapes/re-converts special characters by  %xx-escapes for usage in a URL
        # should not be necessary here, since only two string-parameters are expected

        qq = QUrlQuery(url)

        # evaluated action for the stored Resource
        src_action:str = urllib.parse.unquote_plus(qq.queryItemValue("src_action"))

        # which source-dialog has parsed? Key in self.parse_cache
        src_dialog:str = urllib.parse.unquote_plus(qq.queryItemValue("src_dialog"))

        # source-id, autogenerated unique key in self.parse_cache[src_dialog]
        src_id:str = urllib.parse.unquote_plus(qq.queryItemValue("src_id"))

        parse_result = None
        if self.parse_cache.get(src_dialog):
            if self.parse_cache[src_dialog].get(src_id):
                parse_result: ParseResult = self.parse_cache[src_dialog][src_id]

        if parse_result:
            if src_action == "show_datasources":
                # resource.path = path to container-file
                self.data_sources_dialog.enable_update(
                    parse_result.path, parse_result.maplayer_id
                )
                self.data_sources_dialog.show()
                self.data_sources_dialog.setFocus()
                self.data_sources_dialog.raise_()


            elif src_action == "load_map_layer":
                # load a layer by path + layer-id
                # path required for container-files with relative datasource-paths

                try:
                    dom_doc = get_container_file_dom_doc(parse_result.path)
                    maplayer_node = get_maplayer_node(dom_doc, parse_result.maplayer_id)
                    if maplayer_node:
                        new_layer = create_maplayer(maplayer_node, parse_result.path)
                        if new_layer and new_layer.isValid():
                            self.tool_add_maplayer_to_project(new_layer)
                        else:
                            # maplayer_name = maplayer_node.namedItem("layername").firstChild().toText().data()
                            show_log_message(
                                "WARNING",
                                MY_DICT.tr(
                                    "ifm_warning_layer_not_created",
                                    parse_result.maplayer_id,
                                ),
                                self.my_dialog.log_message_fqlbl,
                                True,
                            )
                    else:
                        show_log_message(
                            "WARNING",
                            f"No MapLayer with ID '{parse_result.maplayer_id}' in '{parse_result.path}'",
                            self.my_dialog.log_message_fqlbl,
                            True,
                        )
                except Exception as e:
                    show_log_message(
                        "WARNING",
                        MY_DICT.tr("error_parsing_container_file", parse_result.path, e),
                        self.my_dialog.log_message_fqlbl,
                        True,
                    )

            elif src_action == "show_extent":
                # same params for vector and raster-layer

                source_crs = QgsCoordinateReferenceSystem()
                if parse_result.srs_wkt:
                    # PROJCS["ETRS89 / UTM zone 32N",GEOGCS["ETRS89".....
                    source_crs = QgsCoordinateReferenceSystem("WKT:" + parse_result.srs_wkt)

                if not source_crs.isValid():
                    dialog = QDialog()
                    dialog.setWindowTitle(MY_DICT.tr("SelectProjectionDialog_title"))
                    layout = QVBoxLayout()
                    dialog.setLayout(layout)
                    cd_widget = QgsCrsSelectionWidget()
                    layout.addWidget(cd_widget)
                    button_box = QDialogButtonBox(
                        QDialogButtonBox.Ok | QDialogButtonBox.Cancel
                    )
                    button_box.accepted.connect(dialog.accept)
                    button_box.rejected.connect(dialog.reject)
                    layout.addWidget(button_box)
                    result = dialog.exec()
                    source_crs = cd_widget.crs()

                if source_crs.isValid():
                    target_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                    trsf_src_to_trg = QgsCoordinateTransform(
                        source_crs, target_crs, QgsProject.instance()
                    )
                    if trsf_src_to_trg.isValid():
                        ul_p = QgsPoint(parse_result._left, parse_result._top)
                        ur_p = QgsPoint(parse_result._right, parse_result._top)
                        lr_p = QgsPoint(parse_result._right, parse_result._bottom)
                        ll_p = QgsPoint(parse_result._left, parse_result._bottom)

                        geom = QgsGeometry(
                            QgsPolygon(QgsLineString([ul_p, ur_p, lr_p, ll_p, ul_p]))
                        )

                        geom.transform(trsf_src_to_trg)

                        self.iface.mapCanvas().setExtent(geom.boundingBox())

                        self.iface.mapCanvas().zoomByFactor(1.1)
                        self.iface.mapCanvas().refresh()
                        self.rb_extent.setToGeometry(geom, None)
                        self.rb_extent.show()
                        self.iface.mapCanvas().flashGeometries([geom])
                        QTimer.singleShot(5000, self.cvs_hide_temp_map_graphics)
                    else:
                        show_log_message(
                            "WARNING",
                            "no transformation available",
                            self.my_dialog.log_message_fqlbl,
                            True,
                        )
            elif src_action == "load_raster_file":
                if os.path.isfile(parse_result.path):
                    path_posix = Path(parse_result.path)

                    # remove leading point .shp => shp
                    file_suffix = str.lower(path_posix.suffix.lstrip("."))
                    if file_suffix in self.raster_extensions:
                        try:
                            new_layer = QgsRasterLayer(
                                path_posix.as_posix(), path_posix.name, "gdal"
                            )
                            if new_layer and new_layer.isValid():
                                self.tool_add_maplayer_to_project(new_layer)
                            else:
                                show_log_message(
                                    "WARNING",
                                    MY_DICT.tr(
                                        "ifm_warning_layer_not_created",
                                        path_posix.as_posix(),
                                    ),
                                    self.my_dialog.log_message_fqlbl,
                                    True,
                                )

                        except Exception as e:
                            show_log_message(
                                "WARNING",
                                MY_DICT.tr(
                                    "error_opening_raster_file",
                                    parse_result.path,
                                    e,
                                ),
                                self.my_dialog.log_message_fqlbl,
                                True,
                            )
                    else:
                        show_log_message(
                            "WARNING",
                            MY_DICT.tr(
                                "file_suffix_not_supported",
                                file_suffix,
                            ),
                            self.my_dialog.log_message_fqlbl,
                            True,
                        )
            elif src_action == "load_vector_file":
                self.tool_load_vector_file_layers(parse_result.path)

            elif src_action == "load_vector_sub_layer":
                if os.path.isfile(parse_result.path):
                    path_posix = Path(parse_result.path)

                    # remove leading point .shp => shp
                    file_suffix = str.lower(path_posix.suffix.lstrip("."))
                    if file_suffix in self.vector_extensions:
                        try:
                            with ogr.Open(
                                path_posix.as_posix(), gdal.GA_ReadOnly
                            ) as ds:
                                sub_layer_found = False
                                for sub_layer in ds:
                                    if sub_layer.GetName() == parse_result.sub_layer_name:
                                        uri = (
                                            path_posix.as_posix()
                                            + "|layername="
                                            + parse_result.sub_layer_name
                                        )

                                        new_layer = QgsVectorLayer(
                                            uri, parse_result.sub_layer_name, "ogr"
                                        )

                                        if new_layer and new_layer.isValid():
                                            self.tool_add_maplayer_to_project(new_layer)
                                        else:
                                            show_log_message(
                                                "WARNING",
                                                MY_DICT.tr(
                                                    "ifm_warning_layer_not_created",
                                                    uri,
                                                ),
                                                self.my_dialog.log_message_fqlbl,
                                                True,
                                            )

                                        sub_layer_found = True

                                if not sub_layer_found:
                                    show_log_message(
                                        "WARNING",
                                        MY_DICT.tr(
                                            "sub_layer_not_found",
                                            parse_result.sub_layer_name,
                                        ),
                                        self.my_dialog.log_message_fqlbl,
                                        True,
                                    )

                        except Exception as e:
                            show_log_message(
                                "WARNING",
                                MY_DICT.tr(
                                    "error_opening_vector_file",
                                    path_posix.as_posix(),
                                    e,
                                ),
                                self.my_dialog.log_message_fqlbl,
                                True,
                            )
                    else:
                        show_log_message(
                            "WARNING",
                            MY_DICT.tr(
                                "file_suffix_not_supported",
                                file_suffix,
                            ),
                            self.my_dialog.log_message_fqlbl,
                            True,
                        )
            elif src_action == "add_resource_to_library":
                self.add_resource_dialog.enable_insert(
                    parse_result.path,
                    self.my_dialog.qtrv_layer_lib.get_selected_folder_id(),
                )
                self.add_resource_dialog.show()
                self.add_resource_dialog.setFocus()
                self.add_resource_dialog.raise_()

            elif src_action == "qlr_export":

                container_path = self.tool_qlr_export(parse_result.dom_doc)
                if container_path:
                    dialog_result = QMessageBox.question(
                        None,
                        MY_DICT.tr("dlg_reimport_qlr_title"),
                        MY_DICT.tr(
                            "dlg_reimport_qlr_txt",
                            container_path,
                        ),
                        buttons=QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                        defaultButton=QMessageBox.StandardButton.Yes,
                    )

                    if dialog_result == QMessageBox.StandardButton.Yes:
                        self.add_resource_dialog.enable_insert(
                            container_path,
                            self.my_dialog.qtrv_layer_lib.get_selected_folder_id(),
                        )
                        self.add_resource_dialog.show()
                        self.add_resource_dialog.setFocus()
                        self.add_resource_dialog.raise_()



            elif src_action == "show_gps_point":
                # lat/lon-GPS-Coordinates (EPSG:4326), optional image-direction

                self.cvs_hide_temp_map_graphics()
                source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
                target_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                trsf_src_to_trg = QgsCoordinateTransform(
                    source_crs,
                    target_crs,
                    QgsProject.instance(),
                )

                if trsf_src_to_trg.isValid():
                    geom = QgsGeometry.fromPoint(QgsPoint(parse_result._lon, parse_result._lat))

                    if geom.isGeosValid():
                        geom.transform(trsf_src_to_trg)

                        self.iface.mapCanvas().setCenter(geom.asPoint())
                        self.vm_gps.setCenter(geom.asPoint())
                        self.vm_gps.show()

                        if isinstance(parse_result._dir, float):
                            # construct rotated Arrow-Symbol
                            # sadly no simple way to add
                            dir_rad = parse_result._dir / 180 * math.pi

                            # arrow-length in map-units depending on canvas-crs
                            arrow_length_mu = (
                                self.arrow_length_px
                                * self.iface.mapCanvas().mapUnitsPerPixel()
                            )

                            # use already transformed point in canvas-crs
                            x_0 = geom.asPoint().x()
                            y_0 = geom.asPoint().y()

                            x_a = x_0 + arrow_length_mu / 20 * math.sin(dir_rad)
                            y_a = y_0 + arrow_length_mu / 20 * math.cos(dir_rad)

                            p_a = QgsPointXY(x_a, y_a)

                            x_d = x_0 + arrow_length_mu * math.sin(dir_rad)
                            y_d = y_0 + arrow_length_mu * math.cos(dir_rad)
                            p_d = QgsPointXY(x_d, y_d)

                            x_e = x_d + arrow_length_mu / 4 * math.sin(
                                dir_rad + math.pi * 7 / 8
                            )
                            y_e = y_d + arrow_length_mu / 4 * math.cos(
                                dir_rad + math.pi * 7 / 8
                            )
                            p_e = QgsPointXY(x_e, y_e)

                            x_f = x_0 + arrow_length_mu * 0.9 * math.sin(dir_rad)
                            y_f = y_0 + arrow_length_mu * 0.9 * math.cos(dir_rad)
                            p_f = QgsPointXY(x_f, y_f)

                            x_g = x_d + arrow_length_mu / 4 * math.sin(
                                dir_rad - math.pi * 7 / 8
                            )
                            y_g = y_d + arrow_length_mu / 4 * math.cos(
                                dir_rad - math.pi * 7 / 8
                            )
                            p_g = QgsPointXY(x_g, y_g)

                            arrow_geom = QgsGeometry.fromPolylineXY(
                                [p_a, p_d, p_e, p_f, p_g, p_d]
                            )

                            if arrow_geom.isGeosValid():
                                self.rb_dir.setToGeometry(arrow_geom)
                                self.rb_dir.show()

                        self.iface.mapCanvas().refresh()
                        # sadly flashing arrow_geom will flash too much (line + vertices)
                        self.iface.mapCanvas().flashGeometries([geom])

                        QTimer.singleShot(15000, self.cvs_hide_temp_map_graphics)

                else:
                    show_log_message(
                        "WARNING",
                        "no transformation available",
                        self.my_dialog.log_message_fqlbl,
                        True,
                    )
            elif src_action == "load_container_file_layers":
                self.tool_load_container_layers(parse_result.path)

            else:
                show_log_message(
                    "WARNING",
                    f"src_action '{src_action}' not implemented...",
                    self.my_dialog.log_message_fqlbl,
                    True,
                )

    def tool_qlr_export(self,dom_doc:QDomDocument):
        """Exports dom-document to qlr-file

        Args:
            dom_doc (QDomDocument): dropped layer(s)/group(s) from QGis-Layers-Panel

        Returns:
            str: path of created qlr-file
        """
        # convenience: try to get a file-name for qlr-file from dropped contents
        fn = None

        layer_tree_group_nodes = dom_doc.elementsByTagName(
            "layer-tree-group"
        )

        for layer_tree_group_node in (
            layer_tree_group_nodes.at(i)
            for i in range(layer_tree_group_nodes.size())
        ):
            # first group-name
            group_name = layer_tree_group_node.toElement().attribute("name")
            if group_name:
                fn = group_name
                break

        if not fn:
            # second approach: extract file-name from possible existing layer-tree-layer
            layer_tree_layer_nodes = dom_doc.elementsByTagName(
                "layer-tree-layer"
            )
            for layer_tree_layer_node in (
                layer_tree_layer_nodes.at(i)
                for i in range(layer_tree_layer_nodes.size())
            ):
                # first layer-name
                layer_name = layer_tree_layer_node.toElement().attribute("name")
                if layer_name:
                    fn = layer_name
                    break
        if not fn:
            # third approach: extract file-name from allways existing maplayer
            map_layer_nodes = dom_doc.elementsByTagName("maplayer")
            for maplayer_node in (
                map_layer_nodes.at(i) for i in range(map_layer_nodes.size())
            ):
                # first layer-name
                layer_name = (
                    maplayer_node.namedItem("layername")
                    .firstChild()
                    .toText()
                    .data()
                )
                if layer_name:
                    fn = layer_name
                    break

        if not fn:
            # format: %Y-%m-%d
            fn = f"{datetime.date.today()} export.qlr"

        # replace problematic characters for file-names
        # see https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
        # "The following reserved characters:"
        replace_chars = [
            "<",  # less than
            ">",  # greater than
            ":",  # colon
            '"',  # double quote
            "/",  # forward slash
            "\\",  # backslash
            "|",  # vertical bar or pipe
            "?",  # question mark
            "*",  # asterisk
        ]
        big_regex = re.compile("|".join(map(re.escape, replace_chars)))
        # re.compile('<|>|:|"|/|\\\\|\\||\\?|\\*')

        fn = big_regex.sub("_", fn)

        default_dir = get_valid_file(
            [self.last_user_file, self.treeview_source_path],
            self.treeview_source_path,
        )

        default_fn = f"{default_dir}/{fn}.qlr"

        container_path, filter = QFileDialog.getSaveFileName(
            None,
            MY_DICT.tr("export_project_layer_to_qlr_title"),
            default_fn,
            filter="QGis-Layer-Definition-File (*.qlr)",
        )
        if container_path:
            with open(container_path, mode="w+b") as f:
                f.write(dom_node_to_ba(dom_doc))
                show_log_message(
                    "SUCCESS",
                    MY_DICT.tr("qlr_exported_to", container_path),
                    self.my_dialog.log_message_fqlbl,
                    True,
                )
                return container_path

    def tool_add_maplayer_to_project(self, maplayer: QgsMapLayer):
        """wrapper for addMapLayer, with adds the layer to project and then sets the visibility depending on self.add_layer_visibility

        Args:
            new_layer (QgsMapLayer): new created layer, should be valid (no check new_layer.isValid())
        """
        # Rev. 2026-11-24
        if maplayer.isValid():
            QgsProject.instance().addMapLayer(maplayer)

            ltr_layer = QgsProject.instance().layerTreeRoot().findLayer(maplayer.id())

            if ltr_layer:
                ltr_layer.setItemVisibilityChecked(self.add_layer_visibility == "visible")
                # default: expanded
                ltr_layer.setExpanded(False)

                show_log_message(
                    "SUCCESS",
                    MY_DICT.tr("ifm_success_sub_layer_added", maplayer.name()),
                    self.my_dialog.log_message_fqlbl,
                    True,
                )
            else:
                # should not happen
                show_log_message(
                    "WARNING",
                    MY_DICT.tr("ifm_warning_layer_not_added", maplayer.name()),
                    self.my_dialog.log_message_fqlbl,
                    True,
                )
        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("ifm_warning_layer_not_added", maplayer.name()),
                self.my_dialog.log_message_fqlbl,
                True,
            )

    def st_add_layers_by_folder_id(self, folder_id: str):
        """add all layers from folder with recursion

        Args:
            folder_id (str)
        """
        # Rev. 2026-11-24
        folder_node = get_folder_node(self.treeview_dom_doc, folder_id)
        if folder_node:
            layer_nodes = folder_node.toElement().elementsByTagName("resource")
            for layer_node in (layer_nodes.at(i) for i in range(layer_nodes.size())):
                resource_id = layer_node.toElement().attribute("id")
                self.st_load_resource_layers(resource_id)


    def tool_load_vector_file_layers(self, file_path_abs: str):
        """Adds layers from vector-layer-file to project
        Shows select-sub-layer-dialog, if there are mutliple layers (gpkg)

        Args:
            file_path_abs (str): Path to vector-file
        """
        file_path_posix = Path(file_path_abs)
        if file_path_posix.is_file():
            # remove leading point .shp => shp
            file_suffix = str.lower(file_path_posix.suffix.lstrip("."))
            if file_suffix in self.vector_extensions:

                try:
                    with ogr.Open(file_path_posix.as_posix(), gdal.GA_ReadOnly) as ds:
                        # @TOTHINK: allways show sub-layer-select-dialog even if there is only one in file?
                        selected_layer_names = []
                        # if ds.GetLayerCount()  > 1:
                        self.select_uri_dialog.feed_vector_layer_file(file_path_abs)
                        dlg_result = self.select_uri_dialog.exec()

                        if dlg_result:
                            for row_nbr in range(
                                self.select_uri_dialog.sublayer_select_qlw.model().rowCount()
                            ):
                                idx = self.select_uri_dialog.sublayer_select_qlw.model().index(
                                    row_nbr, 0
                                )

                                # CheckStateRole => 10,
                                item_checked = (
                                    Qt.CheckState(
                                        idx.data(Qt.ItemDataRole.CheckStateRole)
                                    )
                                    == Qt.CheckState.Checked
                                )
                                if item_checked:
                                    selected_layer_names.append( idx.data(
                                        Qt.ItemDataRole.DisplayRole
                                    ))

                        # else:
                        #     for lyr in ds:
                        #         selected_sub_layer_names.append(lyr.GetName())

                        for selected_layer_name in selected_layer_names:
                            selected_uri = f"{file_path_posix.as_posix()}|layername={selected_layer_name}"
                            new_layer = QgsVectorLayer(
                                selected_uri, selected_layer_name, "ogr"
                            )
                            if new_layer and new_layer.isValid():
                                self.tool_add_maplayer_to_project(new_layer)
                            else:
                                show_log_message(
                                    "WARNING",
                                    MY_DICT.tr(
                                        "ifm_warning_layer_not_created",
                                        selected_layer_name,
                                    ),
                                    self.my_dialog.log_message_fqlbl,
                                    True,
                                )

                except Exception as e:
                    show_log_message(
                        "WARNING",
                        MY_DICT.tr(
                            "error_opening_vector_file",
                            file_path_posix.as_posix(),
                            e,
                        ),
                        self.my_dialog.log_message_fqlbl,
                        True,
                    )
            else:
                show_log_message(
                    "WARNING",
                    MY_DICT.tr(
                        "file_suffix_not_supported",
                        file_suffix,
                    ),
                    self.my_dialog.log_message_fqlbl,
                    True,
                )
        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("file_not_found", file_path_abs),
                self.my_dialog.log_message_fqlbl,
                True,
            )

    def tool_load_container_layers(self, file_path_abs: str):
        """Adds layers from container-file to project
        Shows select-sub-layer-dialog, if there are mutliple layers

        Args:
            file_path_abs (str): Path to container-file
        """
        # Rev. 2026-11-24
        file_path_posix = Path(file_path_abs)
        if file_path_posix.is_file():
            # remove leading point .shp => shp
            file_suffix = str.lower(file_path_posix.suffix.lstrip("."))
            if file_suffix in CONTAINER_EXTENSIONS:
                self.select_uri_dialog.feed_container_file(file_path_abs)
                dlg_rslt = self.select_uri_dialog.exec()

                if dlg_rslt:
                    selected_maplayer_ids = []

                    for row_nbr in range(
                        self.select_uri_dialog.sublayer_select_qlw.model().rowCount()
                    ):
                        idx = self.select_uri_dialog.sublayer_select_qlw.model().index(
                            row_nbr, 0
                        )

                        # CheckStateRole => 10,
                        item_checked = (
                            Qt.CheckState(idx.data(Qt.ItemDataRole.CheckStateRole))
                            == Qt.CheckState.Checked
                        )
                        if item_checked:
                            # maplayer-id stored in UserRole, maplayer-name in DisplayRole
                            selected_maplayer_ids.append(idx.data(Qt.ItemDataRole.UserRole))

                    if selected_maplayer_ids:
                        dom_doc = get_container_file_dom_doc(file_path_abs)
                        for maplayer_id in selected_maplayer_ids:
                            maplayer_node = get_maplayer_node(dom_doc, maplayer_id)
                            if maplayer_node:
                                new_layer = create_maplayer(maplayer_node, file_path_abs)
                                if new_layer and new_layer.isValid():
                                    self.tool_add_maplayer_to_project(new_layer)
                                else:
                                    show_log_message(
                                        "WARNING",
                                        MY_DICT.tr("ifm_warning_layer_not_created", maplayer_id),
                                        self.my_dialog.log_message_fqlbl,
                                        True,
                                    )
                            else:
                                show_log_message(
                                    "WARNING",
                                    f"No MapLayer with ID '{maplayer_id}' in '{file_path_abs}'",
                                    self.my_dialog.log_message_fqlbl,
                                    True,
                                )

            else:
                show_log_message(
                    "WARNING",
                    MY_DICT.tr(
                        "file_suffix_not_supported",
                        file_suffix,
                    ),
                    self.my_dialog.log_message_fqlbl,
                    True,
                )
        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("file_not_found", file_path_abs),
                self.my_dialog.log_message_fqlbl,
                True,
            )

    def st_load_resource_layers(self, resource_id: str) -> tuple:
        """Adds layers from registered resource-file

        Args:
            resource_id (str): id in self.treeview_dom_doc
        """
        # Rev. 2026-11-24
        resource_node = get_resource_node(self.treeview_dom_doc, resource_id)

        if resource_node:

            file_path = resource_node.namedItem("path").firstChild().toText().data()
            # avoid "TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'QVariant'"
            if isinstance(file_path, str) and file_path != "":

                file_path_abs = get_absolute_path(file_path, self.treeview_source_path)
                if file_path_abs:
                    file_path_posix = Path(file_path_abs)
                    # remove leading point .shp => shp
                    file_suffix = str.lower(file_path_posix.suffix.lstrip("."))
                    if file_suffix in CONTAINER_EXTENSIONS:
                        # nothing else can be registered in Library
                        self.tool_load_container_layers(file_path_abs)
                    else:
                        show_log_message(
                            "WARNING",
                            MY_DICT.tr(
                                "file_suffix_not_supported",
                                file_suffix,
                            ),
                            self.my_dialog.log_message_fqlbl,
                            True,
                        )

                else:
                    show_log_message(
                        "WARNING",
                        MY_DICT.tr(
                            "file_not_found",
                            file_path,
                        ),
                        self.my_dialog.log_message_fqlbl,
                        True,
                    )
            else:

                show_log_message(
                    "WARNING",
                    MY_DICT.tr("layer_file_not_registered", resource_id),
                    self.my_dialog.log_message_fqlbl,
                    True,
                )
        else:
            show_log_message(
                "WARNING",
                MY_DICT.tr("metadata_for_resource_missing", resource_id),
                self.my_dialog.log_message_fqlbl,
                True,
            )

    def tool_show_help(self):
        """connected to self.my_dialog.qtb_show_help.clicked
        opens documentation from Internet matching to language and self.plugin_release"""
        # Rev. 2026-11-24

        # two versions implemented: de (german) and en (all other languages)
        # uses QGIs>Settings>Options>General>Override System Locale or QLocale.system().name()

        if QSettings().value("locale/overrideFlag", type=bool):
            lcid = QSettings().value("locale/userLocale", "en_US")
        else:
            # take settings from system-locale, independent from current app
            lcid = QLocale.system().name()

        # lcid is a string composed of language, underscore and country
        # for the translation the language is sufficient:
        # 'de_DE', 'de_AT', 'de_CH', 'de_BE', 'de_LI'... -> 'de'
        # 'en_US', 'en_GB'... -> 'en'

        # only en or de implemented as documentation, all other get the english version:
        language = lcid[0:2] if lcid[0:2] in ["en", "de"] else "en"

        url = f"http://kni-online.de/LayerLib/Release%20{self.plugin_release}/index.{language}.html"
        webbrowser.open_new_tab(url)

    def unload(self):
        """standard-to_implement-function for each plugin:
        reset the GUI
        triggered by plugin-deactivation, project-close, QGis-Quit
        each instruction encapsulated with try...except to ensure no orphans after uninstall, if anything happens
        """
        # Rev. 2026-11-24

        try:
            self.sys_write_config()
        except Exception as e:
            pass

        try:
            self.iface.removeToolBarIcon(self.qact_dlg_show)
        except Exception as e:
            pass

        try:
            self.iface.removePluginMenu("LayerLib", self.qact_dlg_show)
            self.iface.removePluginMenu("LayerLib", self.qact_show_help)
        except Exception as e:
            pass

        try:
            if self.my_dialog:
                self.my_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                self.my_dialog.close()
                del self.my_dialog
        except Exception as e:
            pass

        try:
            if self.edit_folder_dialog:

                self.edit_folder_dialog.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True
                )
                self.edit_folder_dialog.close()
                del self.edit_folder_dialog
        except Exception as e:
            pass

        try:
            if self.add_folder_dialog:

                self.add_folder_dialog.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True
                )
                self.add_folder_dialog.close()
                del self.add_folder_dialog
        except Exception as e:
            pass

        try:
            if self.edit_resource_dialog:

                self.edit_resource_dialog.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True
                )
                self.edit_resource_dialog.close()
                del self.edit_resource_dialog
        except Exception as e:
            pass

        try:
            if self.add_resource_dialog:

                self.add_resource_dialog.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True
                )
                self.add_resource_dialog.close()
                del self.add_resource_dialog
        except Exception as e:
            pass

        try:
            if self.select_uri_dialog:

                self.select_uri_dialog.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True
                )
                self.select_uri_dialog.close()
                del self.select_uri_dialog
        except Exception as e:
            pass

        try:
            if self.data_sources_dialog:
                self.data_sources_dialog.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True
                )
                self.data_sources_dialog.close()
                del self.data_sources_dialog
        except Exception as e:
            pass

        try:
            if self.my_confirm_dialog:

                self.my_confirm_dialog.setAttribute(
                    Qt.WidgetAttribute.WA_DeleteOnClose, True
                )
                self.my_confirm_dialog.close()
                del self.my_confirm_dialog
        except Exception as e:
            pass

        try:
            self.iface.unregisterCustomDropHandler(self.my_drop_handler)
        except Exception as e:
            pass

        # hide *and* remove canvas-graphics, they are *not* garbage-collected and deleted with self!
        self.cvs_hide_temp_map_graphics()
        self.iface.mapCanvas().scene().removeItem(self.rb_extent)
        self.iface.mapCanvas().scene().removeItem(self.vm_gps)
        self.iface.mapCanvas().scene().removeItem(self.rb_dir)


    def cvs_hide_temp_map_graphics(self):
        """hide grafics from last usage"""
        # Rev. 2026-11-24
        self.rb_extent.hide()
        self.vm_gps.hide()
        self.rb_dir.hide()


class MyCustomDropHandler(QgsCustomDropHandler):
    """subclassed QgsCustomDropHandler, which is applied to LayerLib.iface to handle drag&drop from LayerLib-MyQTreeView
    see registerCustomDropHandler/unregisterCustomDropHandler
    """
    # Rev. 2026-11-24

    def __init__(self, layer_lib: LayerLib):
        """constructor

        Args:
            layer_lib (LayerLib): back-reference to initialized plugin
        """
        # Rev. 2026-11-24
        super().__init__()
        self.layer_lib = layer_lib

    def canHandleMimeData(self, mime_data: QMimeData) -> bool:
        """subclassed function to handle plugin-used mimes "LayerLib/folder_id" or "LayerLib/resource_id"

        Args:
            mime_data (QMimeData): dropped mime

        Returns:
            bool: True => can handle, False => can not handle such Mime
        """
        # Rev. 2026-11-24
        if mime_data.data("LayerLib/folder_id") or mime_data.data(
            "LayerLib/resource_id"
        ):
            # special case for this plugin, mime_data of such type is defined in RecursiveXMLModel.mimeData()
            return True
        else:
            # handle to default-iface to allow "normal"-drag&drop of layers from FIlesystem or Browser-Panel
            return super().canHandleMimeData(mime_data)

    def handleMimeDataV2(self, mime_data):
        """subclassed function, triggered after drop
        here: add single resource or all resources from folder to project

        Args:
            mime_data (QMimeData): dropped mime

        Returns:
            bool: True => can handle, False => can not handle such Mime
        """
        # Rev. 2026-11-24
        if mime_data.data("LayerLib/folder_id"):
            folder_id = ba_to_string(mime_data.data("LayerLib/folder_id"))
            self.layer_lib.st_add_layers_by_folder_id(folder_id)
            return True
        elif mime_data.data("LayerLib/resource_id"):
            resource_id = ba_to_string(mime_data.data("LayerLib/resource_id"))
            self.layer_lib.st_load_resource_layers(resource_id)
            return True
        else:
            # handle to default-iface to allow "normal"-drag&drop of layers from Filesystem or Browser-Panel
            return super().handleMimeDataV2(mime_data)

