#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Multiple tools for different purposes

********************************************************************

* Date                 : 2026-08-19
* Copyright            : (C) 2026 by Ludwig Kniprath
* Email                : ludwig at kni-online dot de

********************************************************************

this program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

********************************************************************
"""

# Rev. 2026-11-23
import os, sys, re, random, string, datetime, pytz, tempfile

from osgeo import gdal, ogr

from pathlib import Path

# used for QGis-Projects *.qgz
from zipfile import ZipFile, is_zipfile

import urllib.parse

from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsRasterLayer,
    QgsReadWriteContext,
    QgsMapLayer,
    QgsProject,
    QgsVectorTileLayer,
    QgsVectorLayer,
)


from typing import Any


from qgis.PyQt.QtXml import QDomNode, QDomDocument, QDomElement

from qgis.PyQt.QtCore import (
    QTextStream,
    QByteArray,
    QBuffer,
    QIODevice,
    QUrlQuery,
    QUuid,
    QUrl,
    QTimer,
)

from qgis.PyQt.QtGui import QDropEvent

from qgis.PyQt.QtWidgets import QFileDialog, QLabel, QWidget

from LayerLib import LayerLib

from LayerLib.tools.MyConstants import MY_DICT, CONTAINER_EXTENSIONS


from qgis.utils import iface


class MapLayer:
    """Helper-Class tos store metadata from maplayer-nodes
    used in extract_map_layers
    evaluated in subsequent functions"""

    # Rev. 2026-11-23
    def __init__(self):
        self.maplayer_node: QDomNode = None
        """original node from container-file"""

        self.maplayer_id: str = None
        """maplayer-id, unique in project/container-file"""

        self.layername: str = None
        """Name of that layer, not unique, can be different in maplayer and layer-tree-layer"""

        self.layer_type: str = None
        """type-attribute, vector/raster/annotation  """

        self.provider: str = None
        """content from provider-node, ogr/wms/gdal..."""

        self.datasource: str = None
        """content from datasource-node, paths/database-credentials, virtual-layer-queries..."""

        self.geometry_type: str = None
        """maplayer-geometry-attribute Point/Polygon/No geometry"""

        self.wkbType: str = None
        """maplayer-wkbType-attribute Point/PointZ/...Polygon.../MultiPolygonZ/Nogeometry"""

        self.datasource_path: str = None
        """only file-based layers (gdal/ogr), original path extracted from datasource-node, can be relative or absolute"""

        self.file_exists: bool = None
        """only file-based layers (gdal/ogr): could datasource_path be resolved absolute/relative (both tried)"""

        self.abs_path: str = None
        """only file-based layers (gdal/ogr): if datasource_path could be resolved the absolute version"""

        self.rel_path: str = None
        """only file-based layers (gdal/ogr): if datasource_path could be resolved the relative version"""

        self.project_path_type_absolute: bool = None
        """only project-files qgs/qgz and file-based layers (gdal/ogr): Project-Settings <properties><Paths><Absolute>true/false (note: must *not* fit to maplayer-datasource-paths!)"""

        self.embedded_layers: list = []
        """for virtual layers metadata-dict of the embedded layers"""

        self.virtual_query: str = None
        """for virtual layers the unquoted virtual query"""

        self.sub_layer_name: str = None
        """for vector-layers: name of the sublayer extraced from datasource-attribute, f.e. table-name in GeoPackage"""

        self.sub_layer_found: bool = None
        """for vector-layers: was this sublayer found in datasource"""

    def __str__(self):
        """stringify for debug-purpose"""
        # Rev. 2026-11-23
        result_str = ""

        # not callable ond no dunderscores
        prop_lst = [
            prop
            for prop in self.__dir__()
            if not prop[0:2] == "__" and not callable(getattr(self, prop))
        ]

        longest_item = max(prop_lst, key=len)
        max_len = len(longest_item)

        for prop_name in prop_lst:
            prop_value = getattr(self, prop_name)

            if prop_name in ["maplayer_node"]:
                if prop_value:
                    prop_value = str(dom_node_to_ba(prop_value), "utf-8")[0:100]

            # if prop_value != None:
            result_str += f"{prop_name:<{max_len}}: {prop_value}\n"

        return result_str


class ParseResult:
    """Helper-Class to store metadata in parse-xxx-results for different purposes
    stored in nested dictionary layer_lib.parse_cache[src_dialog][id]
    evaluated in subsequent functions
    """

    # Rev. 2026-11-23
    def __init__(
        self,
        type: str,
        path: str = None,
        map_layer: MapLayer = None,
        map_layers: list["MapLayer"] = None,
        dom_doc: QDomDocument = None,
        dom_node: QDomNode = None,
        maplayer_id: str = None,
        sub_layer_name: str = None,
        _left: float = None,
        _right: float = None,
        _bottom: float = None,
        _top: float = None,
        srs_wkt: str = None,
        _lat: float = None,
        _lon: float = None,
        _dir: float = None,
    ):
        """constructor

        Args:
            type (str): Type of resource, determins the available/necessary parameters for the evaluated src_action in tool_evaluate_storable_resource
            path (str, optional): Path to file or directory, often used. Defaults to None.
            map_layer (MapLayer, optional): single parsed MapLayer, see extract_map_layers
            map_layers (list(MapLayer), optional): multiple parsed MapLayer, see extract_map_layers
            dom_doc (QDomDocument, optional): DomDocument for dropped layers from Layer-Panel
            dom_node (QDomNode, optional): DomNode for single maplayer
            maplayer_id (str, optiona): Maplayer-ID in container-file or current project
            sub_layer_name (str, optional): Name of Sub-Layer inside ogr-layer (f.e. GeoPackage)
            _left (float, optional): coordinate for extent-zoom. Defaults to None.
            _right (float, optional): coordinate for extent-zoom. Defaults to None.
            _bottom (float, optional): coordinate for extent-zoom. Defaults to None.
            _top (float, optional): coordinate for extent-zoom. Defaults to None.
            srs_wkt (str, optional): projection for extent-zoom. Defaults to None.
            _lat (float, optional): coordinate for gps-point. Defaults to None.
            _lon (float, optional): coordinate for gps-point. Defaults to None.
            _dir (float, optional): image-direction for gps-point. Defaults to None.
        """
        # Rev. 2026-11-23
        # unique random id, used as key inside layer_lib.parse_cache[src_dialog]
        self.id = create_random_id()
        self.type = type
        self.path = path
        self.map_layer = map_layer
        self.map_layers = map_layers
        self.dom_doc = dom_doc
        self.dom_node = dom_node
        self.maplayer_id = maplayer_id
        self.sub_layer_name = sub_layer_name
        self._left = _left
        self._top = _top
        self._right = _right
        self._bottom = _bottom
        self.srs_wkt = srs_wkt
        self._lat = _lat
        self._lon = _lon
        self._dir = _dir

    def __str__(self):
        """stringify for debug-purpose"""
        # Rev. 2026-11-23
        result_str = ""

        # not callable ond no dunderscores
        prop_lst = [
            prop
            for prop in self.__dir__()
            if not prop[0:2] == "__" and not callable(getattr(self, prop))
        ]

        longest_item = max(prop_lst, key=len)
        max_len = len(longest_item)

        for prop_name in prop_lst:
            if prop_name in ["dom_doc", "dom_node"]:
                # stringify XML
                dom_node = getattr(self, prop_name)
                if dom_node != None:
                    prop_value = str(dom_node_to_ba(dom_node), "utf-8")[0:100]
            else:
                prop_value = getattr(self, prop_name)

            if prop_value != None:
                result_str += f"{prop_name:<{max_len}}: {prop_value}\n"

        return result_str


class LayerFileParseResult:
    """Helper-class used as mergeable return-value for parse-xxx-results"""

    # Rev. 2026-11-23

    def __init__(self):
        """Constructor"""
        # Rev. 2026-11-23
        self.parse_html: str = ""
        """Result-String displayed in Drop-Area"""

        self.parse_errors: list = []
        """Errors occured while parsing, these are also embedded in parse_html and logged"""

        self.parse_cache: dict[str, ParseResult] = {}
        """ key: unique id, value: Resource with metadata"""

    def merge(self, other: "LayerFileParseResult"):
        """merge two instances

        Args:
            other (LayerFileParseResult)
        """
        # Rev. 2026-11-23
        self.parse_html += other.parse_html
        self.parse_errors += other.parse_errors
        # merge dictionaries
        self.parse_cache |= other.parse_cache

    def add_resource(
        self,
        type: str,
        path: str = None,
        map_layer: MapLayer = None,
        map_layers: list[MapLayer] = None,
        dom_doc: QDomDocument = None,
        dom_node: QDomNode = None,
        maplayer_id: str = None,
        sub_layer_name: str = None,
        _left: float = None,
        _right: float = None,
        _bottom: float = None,
        _top: float = None,
        srs_wkt: str = None,
        _lat: float = None,
        _lon: float = None,
        _dir: float = None,
    ) -> ParseResult:
        """wrapper: creates and registers a Resource with metadata for different purposes

        Args:
            type (str): Type of resource, see Resource
            path (str, optional): Path to file or directory, often used in LayerLib.tool_evaluate_storable_resource, see Resource. Defaults to None.
            map_layer (MapLayer, optional): parsed MapLayer, see extract_map_layers
            map_layers (list(MapLayer), optional): multiple parsed MapLayer, see extract_map_layers
            dom_doc (QDomDocument, optional): DomDocument for dropped layers from Layer-Panel
            dom_node (QDomNode, optional): DomNode for single maplayer
            maplayer_id (str, optiona): Maplayer-ID in container-file or current project
            sub_layer_name (str, optional): Name of Sub-Layer inside ogr-layer (f.e. GeoPackage)
            _left (float, optional): coordinate for extent-zoom. Defaults to None.
            _right (float, optional): coordinate for extent-zoom. Defaults to None.
            _bottom (float, optional): coordinate for extent-zoom. Defaults to None.
            _top (float, optional): coordinate for extent-zoom. Defaults to None.
            srs_wkt (str, optional): projection for extent-zoom. Defaults to None.
            _lat (float, optional): coordinate for gps-point. Defaults to None.
            _lon (float, optional): coordinate for gps-point. Defaults to None.
            _dir (float, optional): image-direction for gps-point. Defaults to None.
        Returns:
            ParseResult
        """
        # Rev. 2026-11-23
        parse_result = ParseResult(
            type,
            path,
            map_layer,
            map_layers,
            dom_doc,
            dom_node,
            maplayer_id,
            sub_layer_name,
            _left,
            _right,
            _bottom,
            _top,
            srs_wkt,
            _lat,
            _lon,
            _dir,
        )
        self.parse_cache[parse_result.id] = parse_result
        return parse_result

    def add_line(self, line_content: str, indent_cnt: int = 0):
        """adds a prepended line to parse_html followed by line-break

        Args:
            line_content (str): content, splitted into sublines by "\n", linewise appended
            indent_cnt (int, optional): num of prepended tabs/blanks. Defaults to 0.
        """
        # Rev. 2026-11-23
        blank = "&nbsp;"
        tab = 3 * blank
        prepend_tab = indent_cnt * tab
        # split multilines
        sub_lines = line_content.split("\n")
        for sub_line in sub_lines:
            self.parse_html += f"{prepend_tab}{sub_line}<br>\n"

    def add_header(self, line_content: str, indent_cnt: int = 0):
        """adds a prepended header line to parse_html followed by line-break

        Args:
            line_content (str): html-content
            indent_cnt (int, optional): num of prepended tabs/blanks. Defaults to 0.
        """
        # Rev. 2026-11-23
        blank = "&nbsp;"
        tab = 3 * blank
        prepend_tab = indent_cnt * tab
        prepend_tags = "<b><i><u>"
        append_tags = "</u></i></b>"

        sub_lines = line_content.split("\n")
        for sub_line in sub_lines:
            self.parse_html += (
                f"{prepend_tab}{prepend_tags}{sub_line}{append_tags}<br>\n"
            )

    def add_error(self, line_content: str, indent_cnt: int = 0, error_hint: str = ""):
        """adds a prepended line with error to parse_html followed by line-break
        additionally append to parse_errors
        Args:
            line_content (str): content, splitted into sublines by "\n", linewise appended in bold red
            indent_cnt (int, optional): num of prepended tabs/blanks. Defaults to 0.
            error_hint (str, optional): splitted into sublines by "\n", linewise appended in gray
        """
        # Rev. 2026-11-23
        blank = "&nbsp;"
        tab = 3 * blank
        prepend_tab = indent_cnt * tab

        debug_trace = get_debug_trace("add_error")

        file_line_function = f"File/Line/Function: '{os.path.basename(debug_trace['file'])}' #{debug_trace['line']} '{debug_trace['function']}'"

        self.parse_errors.append([line_content, file_line_function])

        # split multilines
        sub_lines = line_content.split("\n")
        for sub_line in sub_lines:
            self.parse_html += f"<div style='color:red; font-weight: bold;'>{prepend_tab}{sub_line}</div>\n"

        # append debug-info
        self.parse_html += f"<div style='color:red; font-weight: bold;'>{prepend_tab}{file_line_function}</div>\n"

        if error_hint:
            sub_lines = error_hint.split("\n")
            for sub_line in sub_lines:
                self.parse_html += (
                    f"<div style='color:gray;'>{prepend_tab}{sub_line}</div>\n"
                )
        self.parse_html += "<br>"

        show_log_message("WARNING", sub_lines[0])


def show_log_message(
    error_level: str,
    message_content: Any,
    log_message_qlbl: QLabel = None,
    show_iface_message: bool = False,
):
    """show message_content in
    as log-message in QgsMessageLog (always)
    log_message_qlbl (optional)
    in iface.messageBar() (optional, especially WARNING and CRITICAL)
    adds debug-metas file-name and line-number
    different message-types are displayed with different colors/durations
    Args:
        error_level (str): INFO/SUCCESS/WARNING/CRITICAL/EXCEPTION, implemented with specific background-colors and flashing log_message_qlbl (if implemented)
        message_content (Any)
        log_message_qlbl (QLabel, optional): QLabel (or derived FlashingQLabel). Defaults to None.
        show_iface_message: bool = False additionally show message in iface.messageBar()
    """
    # Rev. 2026-11-23
    message_string = str(message_content)

    level = Qgis.MessageLevel.Info
    duration = 5
    qlbl_style = (
        "QLabel{border-style: none; background-color: transparent; color: blue;}"
    )

    if error_level == "WARNING":
        level = Qgis.MessageLevel.Warning
        duration = 10
        qlbl_style = (
            "QLabel{border-style: none; background-color: transparent; color: red;}"
        )
    elif error_level == "SUCCESS":
        level = Qgis.MessageLevel.Success
        duration = 5
        qlbl_style = (
            "QLabel{border-style: none; background-color: transparent; color: green;}"
        )
    elif error_level == "INFO":
        level = Qgis.MessageLevel.Info
        duration = 5
        qlbl_style = (
            "QLabel{border-style: none; background-color: transparent; color: blue;}"
        )
    elif error_level == "CRITICAL":
        level = Qgis.MessageLevel.Critical
        duration = 20
        qlbl_style = (
            "QLabel{border-style: none; background-color: transparent; color: red;}"
        )
    elif error_level == "EXCEPTION":
        level = Qgis.MessageLevel.Warning
        duration = 10
        qlbl_style = (
            "QLabel{border-style: none; background-color: transparent; color: red;}"
        )

    # debug-info of the last function before show_log_message
    debug_trace = get_debug_trace("show_log_message")

    file_line_function = f"File/Line/Function: '{os.path.basename(debug_trace['file'])}' #{debug_trace['line']} '{debug_trace['function']}'"

    if log_message_qlbl:
        log_message_qlbl.clear()
        log_message_qlbl.setToolTip("")
        log_message_qlbl.setText(message_string)
        log_message_qlbl.setToolTip(file_line_function)
        log_message_qlbl.setStyleSheet(qlbl_style)

        if error_level in ["WARNING", "CRITICAL", "EXCEPTION"]:
            # no normal QLabel, but a FlashingQLabel
            if hasattr(log_message_qlbl, "start_flash") and callable(
                getattr(log_message_qlbl, "start_flash")
            ):
                log_message_qlbl.start_flash()

        QTimer.singleShot(25000, lambda wdg=log_message_qlbl: clear_widget(wdg))

    # optionally show in face.messageBar()
    if show_iface_message:
        iface.messageBar().pushMessage(
            "LayerLib", message_string, level=level, duration=duration
        )

    log_string = message_string
    log_string += "\nBacktrace (index/file/line/function):"

    frame = sys._getframe(0)
    plugin_folder = str(Path(__file__).parent.parent.absolute())
    backtrace_idx = 0
    while frame:
        file = os.path.realpath(frame.f_code.co_filename).replace(plugin_folder, ".")
        function = frame.f_code.co_name
        line = frame.f_lineno
        log_string += f"\n{backtrace_idx}\t{file}\t#{line}\t{function}"
        frame = frame.f_back
        backtrace_idx += 1

    # append everything to default-QGis-Log
    QgsMessageLog.logMessage(log_string, "LayerLib", level)


def clear_widget(wdg: QWidget):
    """clears widget, used for delayed lambda in log_message_qlbl
    try/except avoids "RuntimeError: wrapped C/C++ object of type FlashingQLabel has been deleted" if running delayed after plugin and dialogs have been unloaded

    Args:
        wdg (QWidget)
    """
    # Rev. 2026-11-23
    try:
        wdg.clear()
        wdg.setToolTip("")
    except:
        pass


def get_absolute_path(check_path: str, rel_to_dir: str) -> str:
    """tries to resolve a possibly relative file-path with a directory

    Args:
        check_path (str): absolute or relative path to file (not directory!)
        rel_to_dir (str): path to directory to be combined with check_path if this is relative (first char check_path = ".")

    Raises:
        Exception: if directory in_dir_path not found

    Returns:
        str: absolute path, if existing, else None
    """
    # Rev. 2026-11-23
    if isinstance(check_path, str) and check_path != "":
        if isinstance(rel_to_dir, str) and rel_to_dir != "":
            check_path_posix = Path(check_path)
            if check_path_posix.is_file():
                # absolute existing
                return check_path_posix.as_posix()
            if check_path[1] == ":" or check_path[0] == "/":
                # absolute not existing
                return
            else:
                # check relative to in_dir_path
                in_dir_path_posix = Path(rel_to_dir)
                if in_dir_path_posix.exists():
                    if in_dir_path_posix.is_file():
                        in_dir_path_posix = in_dir_path_posix.parent
                    try:
                        file_path_abs = (in_dir_path_posix / check_path_posix).resolve()
                        if file_path_abs.is_file():
                            return file_path_abs.as_posix()
                    except Exception as e:
                        # only under windows, in unix all files have '/' as anchor
                        raise Exception(
                            f"get_absolute_path: File/Directory have different anchors/drives..."
                        )
                else:
                    raise Exception(
                        f"get_absolute_path: rel_to_dir '{rel_to_dir}' not found..."
                    )
        else:
            raise Exception(f"get_absolute_path: rel_to_dir no string or empty...")
    else:
        #raise Exception(f"get_absolute_path: check_path no string or empty...")
        return


def get_relative_path(check_path: str, relation_source_dir: str) -> str:
    """Vice verso, get relative version of check_path

    Args:
        check_path (str): absolute or almost relative to in_dir_path
        relation_source_dir (str): absolute path to directory

    Raises:
        Exception: not existing relation_source_dir/check_path

    Returns:
        str: relativ path from relation_source_dir to check_path or None (windows: different drive-letters)
    """
    # Rev. 2026-11-23
    if isinstance(relation_source_dir, str) and relation_source_dir != "":
        relation_source_dir_posix = Path(relation_source_dir)
        if relation_source_dir_posix.exists():
            if relation_source_dir_posix.is_file():
                # directory is a file => file.parent => directory
                relation_source_dir_posix = relation_source_dir_posix.parent

            # checks this path and returns the absolute version if file exists, else None
            check_path_abs = get_absolute_path(check_path, relation_source_dir)

            if check_path_abs:
                check_path_posix = Path(check_path_abs)
                try:
                    return check_path_posix.relative_to(
                        relation_source_dir_posix, walk_up=True
                    ).as_posix()
                except Exception as e:
                    # only under windows, in unix all files have '/' as anchor and can be relative
                    return
            else:
                raise Exception(
                    f"get_relative_path: check_path '{check_path}' not found..."
                )
        else:
            raise Exception(
                f"get_relative_path: relation_source_dir '{relation_source_dir}' not found..."
            )
    else:
        raise Exception(f"get_relative_path: relation_source_dir no string or empty...")


def get_valid_file(
    check_paths: list, rel_src_dir: str = None, return_dirs: bool = False
) -> str:
    """gets the first valid file/directory
    used as default for QFileDialog

    Args:
        check_paths (list): list of paths, absolute file-paths or directory paths, optionally relative to rel_src_dir
        rel_src_dir (str, optional): path to directory to be combined with each check_path if it is not absolute


    Returns:
        str: first valid/resolved/directory from check_paths, at least current user directory
    """
    # Rev. 2026-11-23
    # pre-check optional rel_src_dir
    if isinstance(rel_src_dir, str) and rel_src_dir != "":
        if os.path.exists(rel_src_dir):
            if os.path.isfile(rel_src_dir):
                # file instead of dir => use parent
                rel_src_dir = Path(rel_src_dir).parent.as_posix()

    for check_path in check_paths:
        if isinstance(check_path, str) and check_path != "":
            # detect relative path:
            # linux: first char  = '/' windows: second char  = ':'
            if not (check_path[0] == "/" or (len(check_path) > 1 and check_path[1] == ":")):
                # relative path, try combine with rel_src_dir
                try:
                    # exceptions: rel_src_dir is None, different drive-letters...
                    check_path = (
                        (Path(rel_src_dir) / Path(check_path)).resolve().as_posix()
                    )

                except Exception:
                    pass

            if os.path.exists(check_path):
                if return_dirs and os.path.isfile(check_path):
                    return Path(check_path).parent.as_posix()
                else:
                    return check_path

    # no valid directory found: return current user directory
    return Path("~").expanduser().as_posix()


def debug_print(log_obj, append_backtrace: bool = False):
    """Writes Debug-Message to console

    Args:
        log_obj: value/object/list/dict... appended stringified
        append_backtrace: optionally append backtrace to console-output
    """
    # Rev. 2026-11-23

    # strip from backtrace-output
    plugin_folder = str(Path(__file__).parent.parent.absolute())

    # get maximum string-length for f-string-adjusted formatting
    max_length_li = 0
    max_length_fn = 0
    max_length_fi = 0

    backtrace = []
    frame = sys._getframe(0)
    while frame:
        file = os.path.realpath(frame.f_code.co_filename)
        function = frame.f_code.co_name
        line = frame.f_lineno

        stripped_file = file.replace(plugin_folder, ".")
        max_length_fi = max(max_length_fi, len(stripped_file))
        max_length_li = max(max_length_li, len(str(line)))
        max_length_fn = max(max_length_fn, len(function))

        backtrace.append({"file": stripped_file, "line": line, "function": function})
        frame = frame.f_back

    max_length_fn += 8

    log_string = f"\n'{backtrace[1]['file']}' {backtrace[1]['line']} '{backtrace[1]['function']}'"

    try:

        if isinstance(log_obj, dict):
            for key, val in log_obj.items():
                log_string += f"\n{key}: {str(val)}"
        elif isinstance(log_obj, list):
            for idx, val in enumerate(log_obj):
                log_string += f"\n{idx}: {str(val)}"
        else:
            log_string += f"\n{str(log_obj)}"
    except Exception as e:
        log_string += f"debug_print-Exception: {e}"

    # enable on demand via special kwarg:
    if append_backtrace:
        log_string += "\nBacktrace (index/file/line/function):"
        for backtrace_idx, trace_step in enumerate(backtrace):
            file, function, line = map(trace_step.get, ("file", "function", "line"))
            log_string += f"\n{backtrace_idx}\t{file:<{max_length_fi}}\t#{line:<{max_length_li}}\t{function}"

    print(log_string)


def get_debug_trace(stop_trace_function: str) -> tuple:
    """returns debug-footprint (Path + Line-Number + function)

    Args:
        stop_trace_function (str): step backtrace backwards until this function occurs, then return the previous trace
        f.e. 'show_log_message' to get the trace-metas up to the function calling show_log_message
    Returns:
        dict: keys 'file', 'line', 'function'
    """
    # Rev. 2026-11-23
    backtrace = []

    # current function
    frame = sys._getframe(0)
    while frame:
        backtrace.append(
            {
                "file": os.path.realpath(frame.f_code.co_filename),
                "function": frame.f_code.co_name,
                "line": frame.f_lineno,
            }
        )
        frame = frame.f_back

    # iterate in reverse order until stop_trace_function is reached
    backtrace = list(reversed(backtrace))

    for trace_index, trace in enumerate(backtrace):
        if stop_trace_function in trace["function"]:
            return backtrace[trace_index - 1]

    # stop_trace_function is never reached
    return {"file": "?", "line": "?", "function": "?"}


def get_maplayer_node(dom_doc: QDomDocument, maplayer_id: str) -> QDomNode:
    """returns first (and only) maplayer-node for specific layer-id
    replacement for xpath

    Use-Case:
    DomDocument is a stored QGis-Project (XML, *.qgz/*.qgs) or QGis-Layer-Definition (*.qlr)
    In this XML-File are <maplayer>-Elements, having a subnode <id>maplayer_id</id>

    Args:
        dom_doc (QDomDocument or QDomElement, both implement elementsByTagName)
        maplayer_id (str): QGis-layer-id, content of id-node in maplayer-node

    Returns:
        QDomNode (or None if no node with this tag-name or id was found)
    """
    # Rev. 2026-11-23

    # note:
    # <maplayer>-parent node depending on suffix:
    # qlr => <maplayers>
    # qgs/qgz: <projectlayers>
    # therefore scan the entire document

    maplayer_nodes = dom_doc.documentElement().elementsByTagName("maplayer")
    for maplayer_node in (maplayer_nodes.at(i) for i in range(maplayer_nodes.size())):
        if (
            maplayer_node.firstChildElement("id").firstChild().toText().data()
            == maplayer_id
        ):
            return maplayer_node


def get_container_file_dom_doc(file_path: str) -> QDomDocument:
    """parses "container-file" (*.qgs/*.qlr/*.qgz) to QDomDocument
    bit complicated, since qgz is not xml, but a zipped qgs

    Args:
        file_path (str)

    Returns:
        QDomDocument (or None, no Exceptions!)
    """
    # Rev. 2026-11-23

    file_path_posix = Path(file_path)

    if file_path_posix.is_file():

        file_suffix = str.lower(file_path_posix.suffix.lstrip("."))
        if file_suffix in ["qlr", "qgs"]:
            # read files *binary* and fill QDomDocument => encoding (hopefully utf-8...) is preserved
            with open(file_path_posix.as_posix(), "rb", -1) as in_f:
                dom_doc = QDomDocument()
                dom_doc.setContent(in_f.read())
                return dom_doc

        elif file_suffix == "qgz":
            # if is_zipfile(file_path_posix.as_posix()):
            try:
                with ZipFile(file_path_posix.as_posix(), "r") as myzip:
                    # scan zipped files and return first found with qgs-extension
                    # note: qgs-filename must not match qgz-filename!
                    for zip_info in myzip.infolist():
                        if str.lower(zip_info.filename[-4:]) == ".qgs":
                            with myzip.open(zip_info, mode="r") as myfile:
                                # read => bytes => encoding (hopefully utf-8...) is preserved
                                dom_doc = QDomDocument()
                                dom_doc.setContent(myfile.read())
                                return dom_doc
                    raise Exception("No zipped qgs-file found")
            except Exception as e:
                show_log_message(
                    "ERROR",
                    f"Exception reading project-file {file_path}:  {e}]",
                    show_iface_message=True,
                )


def save_container_file_dom_doc(file_path: str, dom_doc: QDomDocument) -> bool:
    """Saves QDomDocument to existing "container-file" (*.qgs/*.qlr/*.qgz)
    bit complicated, since qgz is not xml, but a zipped qgs

    Args:
        file_path (str)
        dom_doc (QDomDocument)

    Returns:
        bool (if save was successfull, no Exceptions!)
    """
    # Rev. 2026-11-23

    file_path_posix = Path(file_path)

    if file_path_posix.is_file():

        file_suffix = str.lower(file_path_posix.suffix.lstrip("."))

        if file_suffix in ["qlr", "qgs"]:
            with open(file_path, "w+b") as in_fp_3:
                in_fp_3.write(dom_node_to_ba(dom_doc))
                return True

        elif file_suffix == "qgz":
            try:
                temp_qgz_resource_int, temp_qgz_file = tempfile.mkstemp(suffix=".qgz")

                # https://docs.python.org/3/library/zipfile.html
                # Lack in this extension: contents can not be altered
                # workaround:
                # 1. create a new temporary empty zip
                # 2. transfer (manipulated) contents from original zip to temporary zip
                # 3. overwrite original zip with temporary zip
                with ZipFile(file_path, "r") as z_org:
                    # temporary container-file
                    # 'w' => write
                    with ZipFile(temp_qgz_file, "w") as z_temp:
                        qgs_found = False
                        for zip_info in z_org.infolist():

                            if str.lower(zip_info.filename[-4:]) != ".qgs":
                                # read/write original data for not qgs-extensions
                                z_temp.writestr(zip_info, z_org.read(zip_info.filename))
                            else:
                                z_temp.writestr(zip_info, dom_node_to_ba(dom_doc))
                                qgs_found = True

                        if not qgs_found:
                            raise Exception("No zipped qgs-file found")
                # rename temporary file to original file => replace
                # in linux possible, under windows error
                # [WinError 183] Eine Datei kann nicht erstellt werden, wenn sie bereits vorhanden ist
                # FileExistsError: [WinError 183] Cannot create a file when that file already exists
                os.remove(file_path_posix.as_posix())
                os.rename(
                    temp_qgz_file,
                    file_path_posix.as_posix(),
                )
                return True
            except Exception as e:
                show_log_message(
                    "ERROR",
                    f"Exception writing project-file {file_path}:  {e}]",
                    show_iface_message=True,
                )


def ba_to_string(in_ba: bytearray | bytes | QByteArray) -> str:
    """Convert bytes to string

    avoids "'utf-8' codec can't decode byte 0xfc in position 0: invalid start byte",
    often raised by file-names containing äöü-"Umlauts" in windows

    Args:
        in_ba (bytearray | bytes | QByteArray): Note: bytes and bytearray are the same in Python
        Vice verso strings can be converted to bytes f. e. by stringvar.encode('utf-8')

    Returns:
        str: utf-8-compatible version
    """
    # Rev. 2026-11-23
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

    # replace all control-chars, here especially \00 (NUL, utf-16) and \01 SOH
    # https://www.geeksforgeeks.org/python/python-program-to-remove-all-control-characters/
    # out_str = re.sub(r'[\x00-\x1f]', '', out_str)

    # replace all control-chars except line-breaks and feeds
    # out_str = re.sub(r'[[\x00-\x1f]^[\x0a\x0d]]', '', out_str)

    # here: remove just two \00 (NUL, utf-16) and \01 SOH
    out_str = re.sub(r"[\x00\x01]", "", out_str)

    return out_str


def save_treeview_dom_doc(dom_doc: QDomDocument, file_path: str):
    """quite complicated to write QDomDocument to file...

    Args:
        dom_doc (QDomDocument): parsed and edited XML with folder/layer-treeview-structure
        file_path (str)
    """
    # Rev. 2026-11-23
    with open(file_path, "w+b") as in_fp_3:
        # prepend DOCTYPE-Declaration, which is not part of parsed dom_doc!
        # this is functionally not necessary, but delivers hints about structure/attributes... for external XML-Editors
        doctype_template = """<?xml version="1.0" encoding="UTF-8"?>
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
"""
        in_fp_3.write(doctype_template.encode())
        # append only the documentElement, else invalid xml with two "<?xml version="1.0" encoding="UTF-8"?>"
        in_fp_3.write(dom_node_to_ba(dom_doc.documentElement()))


def debug_print_dom_node(dom_node: QDomNode):
    """prints single QDomNode as string to console

    Args:
        dom_node (QDomNode)
    """
    # Rev. 2026-11-23
    debug_print(str(dom_node_to_ba(dom_node), "utf-8"))


def dom_node_to_ba(dom_node: QDomNode, indent: int = 2) -> bytearray:
    """returns QDomNode as bytearray
    (there are multiple possibilities)

    Args:
        dom_node (QDomNode)
        indent (int, optional): Indentation, default 2 (like in QGis)
    """
    # Rev. 2026-11-23
    out_ba = QByteArray()
    out_bu = QBuffer(out_ba)
    # Append WriteOnly ReadWrite
    out_bu.open(QIODevice.OpenModeFlag.WriteOnly)

    out_stream = QTextStream(out_bu)

    try:
        # PyQt 5
        out_stream.setCodec("utf-8")
    except Exception as e:
        # PyQt 6:
        from PyQt6.QtCore import QStringConverter

        out_stream.setEncoding(QStringConverter.Encoding.Utf8)

    dom_node.save(out_stream, indent, QDomNode.EncodingPolicy.EncodingFromTextStream)
    return out_ba


def get_resource_node(dom_doc: QDomDocument, resource_id: str) -> QDomNode:
    """replacement for simple xpath-query
    returns first resource-node from treeview_source_file for specific resource_id

    Use-Case:
    <?xml version="1.0" encoding="UTF-8"?>
    <folder>
        ...
        <resource id="unique_id">
            ...
        </resource>


    Args:
        dom_doc (QDomDocument): parsed and edited XML with treeview-structure (treeview_source_path)
        resource_id (str): id-attribute of resource-node

    Returns:
        QDomNode (or None if no node with this id was found)
    """
    # Rev. 2026-11-23
    resource_nodes = dom_doc.documentElement().elementsByTagName("resource")
    for resource_node in (resource_nodes.at(i) for i in range(resource_nodes.size())):
        if resource_node.toElement().attribute("id") == resource_id:
            return resource_node


def get_folder_node(dom_doc: QDomDocument, folder_id: str) -> QDomNode:
    """replacement for simple xpath-query
    returns first (and only) maplayer-container-node from treeview_source_file for specific folder_id

    Use-Case:
    <?xml version="1.0" encoding="UTF-8"?>
    <folder>
        ...
        <folder id="unique_folder_id">
            ...
        </folder>


    Args:
        dom_doc (QDomDocument): parsed and edited XML with treeview-structure (treeview_source_path)
        folder_id (str): content of id-attribute

    Returns:
        QDomNode (or None if no node with this id was found)
    """
    # Rev. 2026-11-23

    folder_nodes = dom_doc.elementsByTagName("folder")
    for folder_node in (folder_nodes.at(i) for i in range(folder_nodes.size())):
        if folder_node.toElement().attribute("id") == folder_id:
            return folder_node


def create_cdata_node(
    dom_doc: QDomDocument, tag_name: str, content: str
) -> QDomElement:
    """create QDomElement <tag_name><![CDATA[content]]</tag_name>

    Args:
        dom_doc (QDomDocument)
        tag_name (str)
        content (str)

    Returns:
        QDomElement
    """
    # Rev. 2026-11-23
    result_node = dom_doc.createElement(tag_name)
    result_node.appendChild(dom_doc.createCDATASection(content))
    return result_node


def get_unique_id(
    check_id: str,
    dom_doc: QDomDocument = None,
    tag_name: str = None,
    att_name: str = None,
) -> str:
    """converts user-defined string for usage as unique id-attribute in DomDocument
    NCName => "non-colonized name"
    see https://stackoverflow.com/questions/1631396/what-is-an-xsncname-type-and-when-should-it-be-used
    bit simplified, but more strict then demanded
    Args:
        check_id (str): the value for the id-attribute, validated/randomized
        dom_doc (QDomDocument): only necessary for check_uniqueness
        tag_name (str): tag-name to be checked, f.e. 'folder' or 'resource', only necessary for check_uniqueness
        att_name (str): id-attribut-name, f.e. 'id', only necessary for check_uniqueness
    Returns:
        str: the possibly altered id
    """
    # Rev. 2026-11-23

    # pre-validate or randomized
    unique_id = get_valid_id(check_id)[0]

    # check uniqueness with list of already used ids
    check_nodes = dom_doc.elementsByTagName(tag_name)
    used_atts = []
    for check_node in (check_nodes.at(i) for i in range(check_nodes.size())):
        used_atts.append(check_node.toElement().attribute(att_name))

    i = 1
    while unique_id in used_atts:
        # strip dunderscore and incremented integer from previous checks and append new incremented
        unique_id = re.sub(r"__[0-9]*$", "", unique_id) + "__" + str(i)
        i += 1

    return unique_id


def insert_folder_node(
    dom_doc: QDomDocument,
    new_folder_id: str,
    new_folder_label: str,
    new_folder_description: str,
    new_parent_id: str,
) -> tuple:
    """inserts new folder node
    Note: dom-doc-source-file is not saved!
    Args:
        dom_doc (QDomDocument): parsed XML-File with folder-resource-structure
        new_folder_id (str): new folder id, will be made unique and validated/randomized
        new_folder_label (str): label of folder
        new_folder_description (str): description of folder
        new_parent_id (str): will be changed to ensure validity

    Returns:
        tuple: (insert_ok:bool,folder_id:str,error_reason:str)
    """
    # Rev. 2026-11-23
    insert_ok = False
    error_reason = ""

    folder_node = dom_doc.createElement("folder")
    folder_id = get_unique_id(new_folder_id, dom_doc, "folder", "id")
    folder_node.setAttribute("id", folder_id)
    folder_node.appendChild(create_cdata_node(dom_doc, "label", new_folder_label))
    folder_node.appendChild(
        create_cdata_node(dom_doc, "description", new_folder_description)
    )

    # default: nothing selected (first option)
    parent_folder_node = dom_doc.documentElement()

    if new_parent_id is not None:
        parent_folder_node = get_folder_node(dom_doc, new_parent_id)

    if folder_node:
        if parent_folder_node:
            parent_folder_node.appendChild(folder_node)
            insert_ok = True
        else:
            error_reason = f"Parent Folder not found"
    else:
        error_reason = f"Error creting new folder-node"

    return (insert_ok, folder_id, error_reason)


def create_random_id(length: int = 16) -> str:
    """generates randomized string usable as id-attribute in XML-documents

    Args:
        length (int, optional): length of result. Defaults to 16.

    Returns:
        str, no number as first char
    """
    # Rev. 2026-11-23

    # random mix of lower chars, upper chars, numbers, length + 2 because of later remove of leading numbers
    random_string = "".join(
        random.choices(string.ascii_letters + string.digits, k=length + 2)
    )

    # remove a randomly leading number, which is invalid for XML-id-attribute
    random_string = re.sub("^[0-9]+", "", random_string)
    random_string = random_string[:length]
    return random_string


def get_valid_id(check_id: str) -> tuple:
    """validates id-attribute for usage in XML-documents with DOCTYPE-Declaration ala "<!ATTLIST folder id ID #REQUIRED>"
    no non-word-chars, no white-space-chars, no number as first char

    aditional check for uniqueness see get_unique_id

    Args:
        check_id (str) randomized if empty

    Returns:
        tuple: (checked_id:str,id_altered: bool,validation_messages:list)
    """
    # Rev. 2026-11-23
    checked_id = ""
    id_altered = False
    validation_messages = []

    if not isinstance(check_id, str) or check_id == "":
        checked_id = create_random_id()
        validation_messages.append(f"Checked ID is empty, using randomized string")
    else:
        # clone string to check alterations
        checked_id = str(check_id)

        last_checked_id = str(check_id)

        # replace white-space-characters
        checked_id = re.sub(r"\s", "_", checked_id)
        if checked_id != last_checked_id:
            validation_messages.append(f"White-spaces replaced")
            last_checked_id = str(checked_id)

        # replace non word characters
        checked_id = re.sub(r"\W", "_", checked_id)
        if checked_id != last_checked_id:
            validation_messages.append(f"Non-word-characters replaced")
            last_checked_id = str(checked_id)

        # remove numbers as first character
        checked_id = re.sub("^[0-9]+", "_", checked_id)
        if checked_id != last_checked_id:
            validation_messages.append(f"Leading numbers replaced")

    id_altered = checked_id != check_id

    return checked_id, id_altered, validation_messages


def validate_treeview_dom_doc(dom_doc: QDomDocument) -> tuple:
    """performs some checks for LayerLib.treeview_dom_doc
    checks unique ids for resources/folders
    check node-names and folder/resource Tree-Structure (parent of each folder or resource-node must be folder except the documentElement-folder-node)
    no check of tags/attributes/node-values inside folder/resource-nodes

    Note: dom_doc can be modified but is not saved!

    Args:
        dom_doc (QDomDocument): LayerLib.treeview_dom_doc

    Returns:
        tuple: (bool: dom_doc_is_valid, bool: dom_doc_modified, list: validation_messages)
    """
    # Rev. 2026-11-23
    dom_doc_is_valid = True
    dom_doc_modified = False
    validation_messages = []
    # check root-element, nodeName must be 'folder' and fitting to DOCTYPE
    if dom_doc.documentElement().nodeName() == "folder":
        # check folder-nodes
        folder_nodes = dom_doc.elementsByTagName("folder")
        folder_ids = []
        for folder_node in (folder_nodes.at(i) for i in range(folder_nodes.size())):
            folder_id = folder_node.toElement().attribute("id")

            # f.e. folder-node inside layer-node or wrong tags in dom_doc
            if (
                folder_node.toElement() != dom_doc.documentElement()
                and not folder_node.parentNode().nodeName() == "folder"
            ):
                validation_messages.append(
                    f"XML-Tree-Structure invalid for folder '{folder_id}', parent node name '{folder_node.parentNode().nodeName()}' != 'folder', folder skipped (line #{folder_node.lineNumber()})"
                )
                continue

            if not folder_id:
                new_folder_id = create_random_id()
                folder_node.toElement().setAttribute("id", new_folder_id)
                dom_doc_modified = True
                validation_messages.append(
                    f"Missing id-attribute for folder, set to '{new_folder_id}' (line #{folder_node.lineNumber()})"
                )
                folder_id = new_folder_id

            checked_folder_id, id_altered, id_validation_messages = get_valid_id(
                folder_id
            )
            validation_messages += id_validation_messages
            if id_altered:
                validation_messages.append(
                    f"Id for folder '{folder_id}' replaced by '{checked_folder_id}' (line #{folder_node.lineNumber()})"
                )
                folder_node.toElement().setAttribute("id", checked_folder_id)
                dom_doc_modified = True

                folder_id = checked_folder_id

            if folder_id in folder_ids:
                # strip dunderscore and incremented integer from previous checks
                id_prefix = re.sub(r"__[0-9]*$", "", folder_id)
                i = 0
                # append dunderscore and incremented integer
                while True:
                    i += 1
                    unique_folder_id = id_prefix + "__" + str(i)
                    if not unique_folder_id in folder_ids:
                        folder_node.toElement().setAttribute("id", unique_folder_id)
                        dom_doc_modified = True
                        validation_messages.append(
                            f"id for folder '{folder_id}' not unique, replaced by '{unique_folder_id}' (line #{folder_node.lineNumber()})"
                        )
                        folder_id = unique_folder_id
                        break

            folder_ids.append(folder_id)

        # check resource-nodes
        resource_nodes = dom_doc.elementsByTagName("resource")
        resource_ids = []
        for resource_node in (
            resource_nodes.at(i) for i in range(resource_nodes.size())
        ):
            resource_id = resource_node.toElement().attribute("id")

            # f.e. resource-node inside resource-node or wrong tags in dom_doc
            if not resource_node.parentNode().nodeName() == "folder":
                validation_messages.append(
                    f"XML-Tree-Structure invalid for resource '{resource_id}', parent node name '{resource_node.parentNode().nodeName()}' != 'folder', resource skipped (line #{resource_node.lineNumber()})"
                )
                continue

            if not resource_id:
                new_resource_id = create_random_id()
                resource_node.toElement().setAttribute("id", new_resource_id)
                dom_doc_modified = True
                validation_messages.append(
                    f"missing id-attribute for resource, set to '{new_resource_id}' (line #{resource_node.lineNumber()})"
                )
                resource_id = new_resource_id

            checked_resource_id, id_altered, id_validation_messages = get_valid_id(
                resource_id
            )
            validation_messages += id_validation_messages

            if id_altered:
                validation_messages.append(
                    f"Id for resource '{resource_id}' replaced by '{checked_resource_id}' (line #{resource_node.lineNumber()})"
                )
                resource_node.toElement().setAttribute("id", checked_resource_id)
                dom_doc_modified = True

                resource_id = checked_resource_id

            if resource_id in resource_ids:
                # strip dunderscore and incremented integer from previous checks
                id_prefix = re.sub(r"__[0-9]*$", "", resource_id)
                i = 0
                # append dunderscore and incremented integer
                while True:
                    i += 1
                    unique_resource_id = id_prefix + "__" + str(i)
                    if not unique_resource_id in resource_ids:
                        resource_node.toElement().setAttribute("id", unique_resource_id)
                        dom_doc_modified = True
                        validation_messages.append(
                            f"id for resource '{resource_id}' not unique, replaced by '{unique_resource_id}' (line #{resource_node.lineNumber()})"
                        )
                        resource_id = unique_resource_id
                        break

            resource_ids.append(resource_id)

    else:
        dom_doc_is_valid = False
        validation_messages.append(
            f"Document-Element nodeName invalid: '{dom_doc.documentElement().nodeName()}'"
        )

    return dom_doc_is_valid, dom_doc_modified, validation_messages


def alter_folder_node(
    dom_doc: QDomDocument,
    folder_id: str,
    new_folder_id: str,
    new_folder_label: str,
    new_folder_description: str,
    new_parent_id: str,
) -> tuple:
    """alters existing folder node
    Note: dom-doc-source-file is not saved!
    Args:
        dom_doc (QDomDocument): parsed XML-File with folder-resource-structure
        folder_id (str): old folder id to find node in dom_doc
        new_folder_id (str): new folder id, must be valid, see get_unique_id
        new_folder_label (str): label of folder
        new_folder_description (str): description of folder
        new_parent_id (str): will be changed to ensure validity

    Returns:
        tuple: (alter_ok:bool,new_folder_id:str,error_reason:str)
    """
    # Rev. 2026-11-23
    alter_ok = False
    error_reason = ""

    folder_node = get_folder_node(dom_doc, folder_id)

    parent_folder_node = dom_doc.documentElement()

    if folder_node:

        if folder_node != dom_doc.documentElement():
            # check if folder should be moved to itself or to sub-node, which is not allowed/possible:
            sub_folder_ids = [folder_id]
            sub_folder_nodes = folder_node.toElement().elementsByTagName("folder")
            for sub_folder_node in (
                sub_folder_nodes.at(i) for i in range(sub_folder_nodes.size())
            ):
                sub_folder_ids.append(sub_folder_node.toElement().attribute("id"))

            if new_parent_id is not None:

                if new_parent_id in sub_folder_ids:
                    error_reason = (
                        f"Can't move folder '{folder_id}' to itself or its sub-nodes"
                    )
                    return (alter_ok, error_reason)
                else:
                    parent_folder_node = get_folder_node(dom_doc, new_parent_id)

        if parent_folder_node:
            if new_folder_id != folder_id:
                new_folder_id = get_unique_id(new_folder_id, dom_doc, "folder", "id")

            folder_node.toElement().setAttribute("id", new_folder_id)

            folder_node.namedItem("label").firstChild().setNodeValue(new_folder_label)
            folder_node.namedItem("description").firstChild().setNodeValue(
                new_folder_description
            )

            if folder_node.parentNode() != parent_folder_node:

                if folder_node == dom_doc.documentElement():
                    alter_ok = True
                else:
                    if folder_node != dom_doc.documentElement():
                        folder_node.parentNode().removeChild(folder_node)
                        parent_folder_node.appendChild(folder_node)
                        alter_ok = True
                    else:
                        # no move for document-element (root-folder)
                        error_reason = "Can't move document-element"
                        alter_ok = False
            else:
                alter_ok = True
        else:
            error_reason = f"Parent Folder '{new_parent_id}' not found"
    else:
        error_reason = f"Folder '{folder_id}' not found"

    return (alter_ok, new_folder_id, error_reason)


def insert_resource_node(
    treeview_dom_doc: QDomDocument,
    new_resource_id: str,
    new_resource_label: str,
    new_resource_description: str,
    new_folder_id: str,
    new_resource_path: str,
) -> tuple:
    """insert new resource node
    Note: treeview_dom_doc is not saved!
    Args:

        treeview_dom_doc (QDomDocument)
        new_resource_id (str): new resource-id, will be made unique and valid inside treeview_dom_doc
        new_resource_label (str): label of resource
        new_resource_description (str): description of resource
        new_folder_id (str): assignment to folder
        new_resource_path (str): path to container-file
    Returns:
        tuple: (insert_ok:bool,returned_resource_id:str,error_reason:str)
    """
    # Rev. 2026-11-23
    insert_ok = False
    error_reason = ""

    resource_node = treeview_dom_doc.createElement("resource")
    resource_id = get_unique_id(new_resource_id, treeview_dom_doc, "resource", "id")
    resource_node.setAttribute("id", resource_id)
    resource_node.appendChild(
        create_cdata_node(treeview_dom_doc, "label", new_resource_label)
    )
    resource_node.appendChild(
        create_cdata_node(treeview_dom_doc, "description", new_resource_description)
    )
    resource_node.appendChild(
        create_cdata_node(treeview_dom_doc, "path", new_resource_path)
    )

    # default: nothing selected (first option)
    parent_folder_node = treeview_dom_doc.documentElement()
    if new_folder_id is not None:
        parent_folder_node = get_folder_node(treeview_dom_doc, new_folder_id)
    if resource_node:
        if parent_folder_node:
            parent_folder_node.appendChild(resource_node)
            insert_ok = True

        else:
            error_reason = f"Parent Folder '{new_folder_id}' not found"
    else:
        error_reason = f"Error creating resource-node"

    return (insert_ok, resource_id, error_reason)


def alter_resource_node(
    dom_doc: QDomDocument,
    resource_id: str,
    new_resource_id: str,
    new_resource_label: str,
    new_resource_description: str,
    new_folder_id: str,
    new_resource_path: str,
) -> tuple:
    """alters existing resource node in dom_doc
    Note: dom-doc-source-file is not saved!

    Args:
        dom_doc (QDomDocument): parsed XML-File with folder-resource-structure
        resource_id (str): old resource_id id to find node in dom_doc
        new_resource_id (str): new resource id, must be valid, see get_unique_id
        new_resource_label (str): label of resource
        new_resource_description (str): description of resource
        new_folder_id (str): assignment to folder
        new_resource_path (str): path to container-file
    Returns:
        tuple: (alter_ok:bool,new_layer_id:str,error_reason:str)
    """
    # Rev. 2026-11-23
    alter_ok = False
    error_reason = ""

    resource_node = get_resource_node(dom_doc, resource_id)

    # default: nothing selected (first option)
    parent_folder_node = dom_doc.documentElement()

    if resource_node:

        if new_folder_id is not None:
            parent_folder_node = get_folder_node(dom_doc, new_folder_id)

        if parent_folder_node:
            new_resource_id, id_altered, validation_messages = get_valid_id(
                new_resource_id
            )

            if new_resource_id != resource_id:
                new_resource_id = get_unique_id(
                    new_resource_id, dom_doc, "resource", "id"
                )
            # allready checked in EditFolderDialog

            resource_node.toElement().setAttribute("id", new_resource_id)
            resource_node.namedItem("label").firstChild().setNodeValue(
                new_resource_label
            )
            resource_node.namedItem("description").firstChild().setNodeValue(
                new_resource_description
            )

            resource_node.namedItem("path").firstChild().setNodeValue(new_resource_path)

            if resource_node.parentNode() != parent_folder_node:
                resource_node.parentNode().removeChild(resource_node)
                parent_folder_node.appendChild(resource_node)
                alter_ok = True
            else:
                alter_ok = True
        else:
            error_reason = f"Parent Folder '{new_folder_id}' not found"

    else:
        error_reason = f"Layer '{resource_id}' not found"

    return (alter_ok, new_resource_id, error_reason)





def parse_directory(
    dir_path: str, layer_lib: LayerLib, src_dialog: str, indent_cnt: int = 0
) -> LayerFileParseResult:
    """Parse dropped directory

    Args:
        dir_path (str): directory-path
        layer_lib (LayerLib): Back-reference
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()
    indent_cnt += 1
    parse_result.add_header(f"Directory:", indent_cnt)
    parse_result.add_line(f"<b>Path:</b> {dir_path}", indent_cnt + 1)

    if isinstance(dir_path, str) and os.path.isdir(dir_path):

        sr = parse_result.add_resource("directory", path=dir_path)

        parse_result.add_line(
            f"<a href='tool_evaluate_storable_resource?src_action=show_file_in_explorer&src_dialog={src_dialog}&src_id={sr.id}'>Show in explorer...</a>",
            indent_cnt + 1,
        )

        all_files = []
        for path, subdirs, files in os.walk(dir_path):
            for name in files:
                all_files.append(Path(os.path.join(path, name)))

        parse_result.add_line(
            f"Parsing {len(all_files)} files",
            indent_cnt + 1,
        )

        for idx, file_path_posix in enumerate(all_files):

            parse_result.add_line(
                f"File # {idx + 1} of {len(all_files)}",
                indent_cnt + 1,
            )

            file_suffix = str.lower(file_path_posix.suffix.lstrip("."))

            if (
                file_suffix in CONTAINER_EXTENSIONS
                or file_suffix in layer_lib.raster_extensions
                or file_suffix in layer_lib.vector_extensions
            ):
                parse_result.merge(
                    parse_file(
                        file_path_posix.as_posix(), layer_lib, src_dialog, indent_cnt
                    )
                )
            else:
                parse_result.add_line(
                    f"suffix '{file_suffix}' unsupported, skip file...", indent_cnt + 2
                )
    else:
        parse_result.add_error(f"Directory '{dir_path}' not found", indent_cnt)

    return parse_result


def parse_file(
    file_path: str, layer_lib: LayerLib, src_dialog: str, indent_cnt: int = 0
) -> LayerFileParseResult:
    """Parse dropped file (vector/raster/container)

    Args:
        file_path (str): path to file
        layer_lib (LayerLib): Back-reference
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()
    indent_cnt += 1
    parse_result.add_header(f"File:", indent_cnt)
    parse_result.add_line(f"<b>path:</b> {file_path}", indent_cnt + 1)
    if isinstance(file_path, str) and os.path.isfile(file_path):
        file_path_posix = Path(file_path)

        sr = parse_result.add_resource("file", path=file_path_posix.as_posix())

        parse_result.add_line(
            f"<a href='tool_evaluate_storable_resource?src_action=show_file_in_explorer&src_dialog={src_dialog}&src_id={sr.id}'>Show in explorer...</a>",
            indent_cnt + 1,
        )

        # remove leading point .shp => shp
        file_suffix = str.lower(file_path_posix.suffix.lstrip("."))
        parse_result.add_line(f"<b>extension:</b> {file_suffix}", indent_cnt + 1)

        if (
            file_suffix in CONTAINER_EXTENSIONS
            or file_suffix in layer_lib.raster_extensions
            or file_suffix in layer_lib.vector_extensions
        ):
            # for usage as url-parameter

            stat_metas = os.stat(file_path)

            # # st_birthtime: time of file creation in seconds, but not on linux!
            # # dt_created = datetime.datetime.fromtimestamp(stat_metas.st_birthtime).strftime('%Y-%m-%d %H:%M:%S')
            # # st_ctime: last metadata change time
            dt_created = datetime.datetime.fromtimestamp(stat_metas.st_ctime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            # st_atime: time of most recent access
            dt_access = datetime.datetime.fromtimestamp(stat_metas.st_atime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            # st_mtime: time of most recent content modification
            dt_modify = datetime.datetime.fromtimestamp(stat_metas.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # st_size: size of file, in bytes

            file_size_b = stat_metas.st_size
            file_size_kb = round(file_size_b / 1024, 2)
            file_size_mb = round(file_size_b / 1024 / 1024, 2)

            parse_result.add_line(f"<b>last-modified:</b> {dt_modify}", indent_cnt + 1)
            parse_result.add_line(f"<b>file-created:</b> {dt_created}", indent_cnt + 1)
            parse_result.add_line(f"<b>last-accessed: </b> {dt_access}", indent_cnt + 1)
            parse_result.add_line(
                f"<b>size:</b> {file_size_mb}mb ({file_size_b}b {file_size_kb}kb)",
                indent_cnt + 1,
            )

            if file_suffix in CONTAINER_EXTENSIONS:
                parse_result.merge(
                    parse_container_file(file_path, layer_lib, src_dialog, indent_cnt)
                )
            elif (
                file_suffix in layer_lib.raster_extensions
                and file_suffix in layer_lib.vector_extensions
            ):
                # ambiguous
                # try both, because both could be contained, f.e. gpkg (can hold vector or raster) or xml
                vector_ds = None
                raster_ds = None
                try:
                    vector_ds = ogr.Open(file_path_posix.as_posix(), gdal.GA_ReadOnly)
                except Exception as e:
                    pass

                try:
                    raster_ds = gdal.Open(file_path_posix.as_posix(), gdal.GA_ReadOnly)
                except Exception as e:
                    pass

                if vector_ds or raster_ds:
                    if vector_ds:
                        parse_result.merge(
                            parse_ogr_file(
                                file_path,
                                layer_lib,
                                src_dialog,
                                indent_cnt,
                            )
                        )
                    if raster_ds:
                        parse_result.merge(
                            parse_gdal_file(
                                file_path, layer_lib, src_dialog, indent_cnt
                            )
                        )
                else:
                    parse_result.add_error(
                        f"No data-sources in file '{file_path}'", indent_cnt + 1
                    )

            elif file_suffix in layer_lib.vector_extensions:

                parse_result.merge(
                    parse_ogr_file(file_path, layer_lib, src_dialog, indent_cnt)
                )

            elif file_suffix in layer_lib.raster_extensions:
                parse_result.merge(
                    parse_gdal_file(file_path, layer_lib, src_dialog, indent_cnt)
                )
        else:
            parse_result.add_error(
                f"File-Suffix '{file_suffix}' not supported", indent_cnt
            )
    else:
        parse_result.add_error(f"File '{file_path}' not found", indent_cnt)

    return parse_result


def parse_evt_url(
    url: QUrl,
    layer_lib: LayerLib,
    src_dialog: str,
    indent_cnt: int = 0,
) -> LayerFileParseResult:
    """parses dropped url, file/directory/browser-url... dropped from file-system

    url is checked for usability as layer-source in library

    here parsed: file-metadata (size, data...)
    depending on file-suffix the function forks to raster, vector or container-files

    Args:
        url (QUrl): Path to file
        layer_lib (LayerLib): access to plugin
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()
    # indent_cnt += 1
    # parse_result.add_header(f"Event-URL:", indent_cnt)

    # check if it is file or directory, not f.e. URL from Firefox...
    if url.isLocalFile():

        # qgis.PyQt.QtCore.QUrl('file:///home/...
        url_path = url.toLocalFile()
        # problem under windows:
        # path is something like /C:/Users/..., which is not usable for Path
        # simulating a file-system-root-element like in reasonable operating systems?
        if url_path[2] == ":":
            url_path = url_path.lstrip("/")

        if os.path.isfile(url_path):
            parse_result.merge(parse_file(url_path, layer_lib, src_dialog, indent_cnt))
        elif os.path.isdir(url_path):
            parse_result.merge(
                parse_directory(url_path, layer_lib, src_dialog, indent_cnt)
            )
        else:
            parse_result.add_error(f"File '{url_path}' not found", indent_cnt)

    else:
        # f.e. dropped URL from browser-address-bar
        parse_result.add_error(
            f"Non-local URL '{url}' dropped",
            indent_cnt,
            "accepted: files/directories from file-system",
        )

    return parse_result


def parse_container_file(
    file_path: str, layer_lib: LayerLib, src_dialog: str, indent_cnt: int = 0
) -> LayerFileParseResult:
    """parse qlr/qgs/qgz-File

    Args:
        file_path (str): absolute path to qlr/qgs/qgz-File
        layer_lib (LayerLib): access to plugin
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()

    indent_cnt += 1

    parse_result.add_header(
        "Container-File:",
        indent_cnt,
    )

    parse_result.add_line(f"<b>Path:</b> {file_path}", indent_cnt + 1)

    if isinstance(file_path, str) and os.path.isfile(file_path):

        file_path_posix = Path(file_path)

        file_suffix = str.lower(file_path_posix.suffix.lstrip("."))

        if file_suffix in CONTAINER_EXTENSIONS:

            sr = parse_result.add_resource(
                "container-file", path=file_path_posix.as_posix()
            )

            parse_result.add_line(
                f"<a href='tool_evaluate_storable_resource?src_action=show_file_in_explorer&src_dialog={src_dialog}&src_id={sr.id}'>Show in explorer...</a>",
                indent_cnt + 1,
            )

            parse_result.add_line(
                f"<a href='tool_evaluate_storable_resource?src_action=show_datasources&src_dialog={src_dialog}&src_id={sr.id}'>Show/Edit datasources...</a>",
                indent_cnt + 1,
            )

            try:
                dom_doc = get_container_file_dom_doc(file_path)

                parse_result.merge(
                    parse_qlr(
                        dom_doc,
                        layer_lib,
                        src_dialog,
                        indent_cnt,
                        file_path_posix.as_posix(),
                    )
                )

            except Exception as e:
                parse_result.add_error(
                    f"Exception parsing '{file_path}':\n{e}",
                    indent_cnt,
                )
        else:
            parse_result.add_error(
                f"File-Suffix '{file_suffix}' not supported", indent_cnt
            )
    else:
        parse_result.add_error(f"File '{file_path}' not found", indent_cnt)

    return parse_result


def parse_qlr(
    dom_doc: QDomDocument,
    layer_lib: LayerLib,
    src_dialog: str,
    indent_cnt: int = 0,
    container_path: str = "",
) -> LayerFileParseResult:
    """parse QDomDocument, which can come from container-file or dropped layer from QGis-Layer-Panel

    Args:
        dom_doc (QDomDocument): from container-file or dropped layer from QGis-Layer-Panel
        layer_lib (LayerLib): Reference to Plugin
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.
        container_path (str, optional): Optional for dom_doc coming from container-file to resolve relative paths. Defaults to "".

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()

    # indent_cnt += 1

    # parse_result.add_header(f"Parse qlr:", indent_cnt)

    if isinstance(container_path, str) and container_path != "":
        if not os.path.isfile(container_path):
            parse_result.add_error(f"File '{container_path}' not found", indent_cnt)
            return parse_result

    extracted_map_layers = extract_map_layers(dom_doc, container_path)

    if extracted_map_layers:
        if container_path:
            sr = parse_result.add_resource("container_path", path=container_path)
            parse_result.add_line(
                f"<a href='tool_evaluate_storable_resource?src_action=load_container_file_layers&src_dialog={src_dialog}&src_id={sr.id}'>Load Map-Layers...</a>",
                indent_cnt + 1,
            )
        else:
            # no path => layers dropped from QGis-Layer-Panel, no need to import an already existing layer, but export as qlr-file
            sr = parse_result.add_resource("dom_doc", dom_doc=dom_doc)

            parse_result.add_line(
                f"<a href='tool_evaluate_storable_resource?src_action=qlr_export&src_dialog={src_dialog}&src_id={sr.id}'>Export as Layer-Definition-File (*.qlr)...</a>",
                indent_cnt + 1,
            )

        # parse_result.add_line(
        #     f"{len(extracted_map_layers)} Maplayer:",
        #     indent_cnt + 1,
        # )

        sl_c = 0
        for maplayer_id, map_layer in extracted_map_layers.items():

            parse_result.add_line(
                f"- Maplayer # {sl_c+1} of {len(extracted_map_layers)}:",
                indent_cnt + 1,
            )
            parse_result.merge(
                parse_qlr_sub_layer(
                    map_layer,
                    layer_lib,
                    src_dialog,
                    indent_cnt + 1,
                    container_path,
                )
            )

            sl_c += 1

    else:
        parse_result.add_error("No datasources", indent_cnt)

    return parse_result


def parse_qlr_sub_layer(
    map_layer: MapLayer,
    layer_lib: LayerLib,
    src_dialog: str,
    indent_cnt: int = 0,
    container_path: str = "",
) -> LayerFileParseResult:
    """parse DomDocument, which can come from container-file or dropped layer from QGis-Layer-Panel

    Args:
        map_layer (MapLayer): see extract_map_layers
        layer_lib (LayerLib): Reference to Plugin
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): num of prepended tabs/blanks. Defaults to 0.
        container_path (str, optional): Optional for dom_doc coming from container-file to resolve relative paths. Defaults to "".

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()
    indent_cnt += 1

    # parse_result.add_header(
    #     "Parse Maplayer:",
    #     indent_cnt,
    # )

    # geometry and wkbType only for vector-layer
    keys = {
        "layer_type": "Layer-Type",
        "maplayer_id": "Layer-ID",
        "layername": "Layer-Name",
        "provider": "Provider",
        # "geometry_type": "Geometry-Type",
        "wkbType": "WKB-Type",
        "datasource": "Datasource",
        # "datasource_path": "Path",
    }

    for key, label in keys.items():
        val = getattr(map_layer, key)
        if val:
            parse_result.add_line(f"<b>{label}:</b> {val}", indent_cnt + 1)

    if map_layer.provider in ["gdal", "ogr"]:

        if map_layer.file_exists:
            parse_result.add_line(f"<b>Path:</b> {map_layer.abs_path}", indent_cnt + 1)

            sr = parse_result.add_resource("file", path=map_layer.abs_path)

            parse_result.add_line(
                f"<a href='tool_evaluate_storable_resource?src_action=show_file_in_explorer&src_dialog={src_dialog}&src_id={sr.id}'>Show in explorer...</a>",
                indent_cnt + 1,
            )

            if container_path and map_layer.file_exists and map_layer.provider == "ogr":

                sr = parse_result.add_resource("vector-file", path=map_layer.abs_path)

                parse_result.add_line(
                    f"<a href='tool_evaluate_storable_resource?src_action=load_vector_file&src_dialog={src_dialog}&src_id={sr.id}'>Show/Load Sub-Layers from '{Path(map_layer.abs_path).name}'...</a>",
                    indent_cnt + 1,
                )

            if (
                container_path
                and map_layer.file_exists
                and (not map_layer.sub_layer_name or map_layer.sub_layer_found)
            ):
                sr = parse_result.add_resource(
                    "container_path+maplayer_id",
                    path=container_path,
                    maplayer_id=map_layer.maplayer_id,
                )
                parse_result.add_line(
                    f"<a href='tool_evaluate_storable_resource?src_action=load_map_layer&src_dialog={src_dialog}&src_id={sr.id}'>Load Map-Layer '{map_layer.layername}' ...</a>",
                    indent_cnt + 1,
                )

            if map_layer.sub_layer_name and not map_layer.sub_layer_found:
                parse_result.add_error(
                    f"Sublayer '{map_layer.sub_layer_name}' not found, edit datasource",
                    indent_cnt + 1,
                )

        else:
            parse_result.add_error(
                f"File '{map_layer.datasource_path}' not found, edit datasource",
                indent_cnt + 2,
            )

    else:
        # non-file-based, hopefully can be loaded...
        if container_path:
            sr = parse_result.add_resource(
                "container_path+maplayer_id",
                path=container_path,
                maplayer_id=map_layer.maplayer_id,
            )

            parse_result.add_line(
                f"<a href='tool_evaluate_storable_resource?src_action=load_map_layer&src_dialog={src_dialog}&src_id={sr.id}'>Load Map-Layer '{map_layer.layername}' ...</a>",
                indent_cnt + 1,
            )

    return parse_result


def parse_ogr_layer(
    file_path: str,
    sub_layer_name: str,
    layer_lib: LayerLib,
    src_dialog: str,
    indent_cnt: int = 0,
) -> LayerFileParseResult:
    """Parse dropped OGR-Layer (from file-based vector-layer)

    Args:
        file_path (str): directory-path
        sub_layer_name (str): necessary for multi-layer-files, f.e. gpkg
        layer_lib (LayerLib): Back-reference
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23

    parse_result = LayerFileParseResult()

    indent_cnt += 1

    parse_result.add_header("Parse OGR-Layer (Vector-Layer):", indent_cnt)

    # parse_result.add_line(f"<b>path:</b> {file_path}", indent_cnt + 1)

    parse_result.add_line(f"<b>Layer-Name:</b> {sub_layer_name}", indent_cnt + 1)

    if isinstance(file_path, str) and os.path.isfile(file_path):

        file_path_posix = Path(file_path)

        # remove leading point .shp => shp
        file_suffix = str.lower(file_path_posix.suffix.lstrip("."))

        if file_suffix in layer_lib.vector_extensions:
            try:
                # https://gdal.org/en/stable/api/python/osgeo.ogr.html
                # https://gdal.org/en/stable/api/python/raster_api.html#osgeo.gdal.Dataset
                with ogr.Open(file_path_posix.as_posix(), gdal.GA_ReadOnly) as ds:
                    sub_layer = ds.GetLayer(sub_layer_name)

                    if sub_layer:
                        parse_result.add_line(
                            f"<b>Num Features:</b> {sub_layer.GetFeatureCount()}",
                            indent_cnt + 1,
                        )

                        feature_def = sub_layer.GetLayerDefn()

                        # better than QGis/GPKG: multiple geometry-columns supported
                        num_geom_fields = feature_def.GetGeomFieldCount()

                        if num_geom_fields:
                            parse_result.add_line(f"<b>Geometry:</b>", indent_cnt + 1)
                            for gf_idx in range(num_geom_fields):
                                geom_field_def = feature_def.GetGeomFieldDefn(gf_idx)
                                if geom_field_def.GetName():
                                    # no geom-field in shape-files
                                    parse_result.add_line(
                                        f"<b>Field:</b> {geom_field_def.GetName()}",
                                        indent_cnt + 2,
                                    )
                                parse_result.add_line(
                                    f"<b>Geom-Type:</b> {geom_field_def.GetType()} '{ogr.GeometryTypeToName(geom_field_def.GetType())}'",
                                    indent_cnt + 2,
                                )
                                srs = geom_field_def.GetSpatialRef()
                                if srs:
                                    # <class 'osgeo.osr.SpatialReference'>
                                    # f.e. "EPSG"
                                    authority_name = srs.GetAuthorityName(None)
                                    authority_code = srs.GetAuthorityCode(None)

                                    if authority_name and authority_code:
                                        # shape-files have projection-metas defined by *.prj, which have no authority_name/authority_code
                                        parse_result.add_line(
                                            f"<b>Projection:</b> {authority_name}:{authority_code} ({srs.GetName()})",
                                            indent_cnt + 2,
                                        )
                                    else:
                                        parse_result.add_line(
                                            f"<b>Projection:</b> {srs.GetName()}",
                                            indent_cnt + 2,
                                        )

                                else:
                                    parse_result.add_line(
                                        f"<b>Projection:</b> Undefined",
                                        indent_cnt + 2,
                                    )

                                # 100 => GeomType "None"
                                if (
                                    geom_field_def.GetType() != 100
                                    and sub_layer.GetFeatureCount() > 0
                                ):

                                    # multiple geometry-columns can have multiple projections and multiple extents
                                    extent = sub_layer.GetExtent(gf_idx)

                                    # noticed: GPX-layer with features return extent (0.0, 0.0, 0.0, 0.0)
                                    if (
                                        extent
                                        and extent[0] != extent[1]
                                        and extent[2] != extent[3]
                                    ):
                                        # (-7115212.98379227, 4895579.81146616, 1368239.60631786, 7805331.2230994)
                                        _left = extent[0]
                                        _right = extent[1]
                                        _bottom = extent[2]
                                        _top = extent[3]

                                        srs_wkt = None
                                        if srs:
                                            srs_wkt = srs.ExportToWkt()

                                        sr = parse_result.add_resource(
                                            "extent",
                                            None,
                                            _left=_left,
                                            _right=_right,
                                            _bottom=_bottom,
                                            _top=_top,
                                            srs_wkt=srs_wkt,
                                        )

                                        parse_result.add_line(
                                            f"<b>Extent:</b> <a href='tool_evaluate_storable_resource?src_action=show_extent&src_dialog={src_dialog}&src_id={sr.id}'>Zoom/Show Extent...</a>",
                                            indent_cnt + 2,
                                        )
                                        parse_result.add_line(
                                            f"<b>left:&nbsp;&nbsp;&nbsp;</b> {_left}",
                                            indent_cnt + 3,
                                        )
                                        parse_result.add_line(
                                            f"<b>right:&nbsp;&nbsp;</b> {_right}",
                                            indent_cnt + 3,
                                        )

                                        parse_result.add_line(
                                            f"<b>bottom:&nbsp;</b> {_bottom}",
                                            indent_cnt + 3,
                                        )

                                        parse_result.add_line(
                                            f"<b>top:&nbsp;&nbsp;&nbsp;&nbsp;</b> {_top}",
                                            indent_cnt + 3,
                                        )

                        else:
                            parse_result.add_line(
                                f"<b>Geometryless</b>", indent_cnt + 1
                            )
                    else:
                        parse_result.add_error(
                            f"Sublayer '{sub_layer_name}' not found, edit datasource",
                            indent_cnt,
                        )

            except Exception as e:
                parse_result.add_error(
                    f"Exception opening vector-file '{file_path}':\n{e}", indent_cnt
                )
        else:
            parse_result.add_error(
                f"File-Suffix '{file_suffix}' not supported", indent_cnt
            )
    return parse_result


def parse_ogr_file(
    file_path: str,
    layer_lib: LayerLib,
    src_dialog: str,
    indent_cnt: int = 0,
) -> LayerFileParseResult:
    """Parse dropped OGR-Layer-File (from file-based vector-layer)

    Args:
        file_path (str): path to vector-layer-file
        layer_lib (LayerLib): Back-reference
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()

    indent_cnt += 1

    parse_result.add_header(f"Vector-Layer-File (OGR):", indent_cnt)

    # parse_result.add_line(f"<b>path:</b> {file_path}", indent_cnt + 1)

    if isinstance(file_path, str) and os.path.isfile(file_path):

        file_path_posix = Path(file_path)

        # sr = parse_result.add_resource("file", path=file_path_posix.as_posix())

        # parse_result.add_line(
        #     f"<a href='tool_evaluate_storable_resource?src_action=show_file_in_explorer&src_dialog={src_dialog}&src_id={sr.id}'>Show in explorer...</a>",
        #     indent_cnt + 1,
        # )

        # remove leading point .shp => shp
        file_suffix = str.lower(file_path_posix.suffix.lstrip("."))

        if file_suffix in layer_lib.vector_extensions:

            try:
                # https://gdal.org/en/stable/api/python/osgeo.ogr.html
                # https://gdal.org/en/stable/api/python/raster_api.html#osgeo.gdal.Dataset
                with ogr.Open(file_path_posix.as_posix(), gdal.GA_ReadOnly) as ds:
                    sr = parse_result.add_resource(
                        "vector-file", path=file_path_posix.as_posix()
                    )

                    parse_result.add_line(
                        f"<a href='tool_evaluate_storable_resource?src_action=load_vector_file&src_dialog={src_dialog}&src_id={sr.id}'>Show/Import Sub-Layers from '{file_path_posix.name}'...</a>",
                        indent_cnt + 1,
                    )

                    parse_result.add_line(
                        f"<b>OGR-Driver:</b> {layer_lib.vector_extensions[file_suffix][1]}",
                        indent_cnt + 1,
                    )

                    parse_result.add_line(
                        f"<b>Num Sub-Layers:</b> {ds.GetLayerCount()}", indent_cnt + 1
                    )

                    sl_c = 0
                    for sub_layer in ds:
                        parse_result.add_line(
                            f"- Sub-Layer # {sl_c + 1} of {ds.GetLayerCount()}:",
                            indent_cnt + 1,
                        )
                        parse_result.merge(
                            parse_ogr_layer(
                                file_path,
                                sub_layer.GetName(),
                                layer_lib,
                                src_dialog,
                                indent_cnt + 1,
                            )
                        )
                        sl_c += 1

            except Exception as e:
                parse_result.add_error(
                    f"Exception opening vector-file '{file_path}':\n{e}", indent_cnt
                )
        else:
            parse_result.add_error(
                f"File-Suffix '{file_suffix}' not supported", indent_cnt
            )
    else:
        parse_result.add_error(
            f"File '{file_path}' not found, edit datasource", indent_cnt
        )

    return parse_result


def parse_gdal_file(
    file_path: str, layer_lib: LayerLib, src_dialog: str, indent_cnt: int = 0
) -> LayerFileParseResult:
    """Parse GDAL-file (file-based raster-layer)

    Args:
        file_path (str): path to raster-layer-file
        layer_lib (LayerLib): Back-reference
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()
    indent_cnt += 1

    parse_result.add_header(
        f"Raster-Layer-File (GDAL)",
        indent_cnt,
    )
    parse_result.add_line(f"<b>Path:</b> {file_path}", indent_cnt + 1)

    if isinstance(file_path, str) and os.path.isfile(file_path):

        file_path_posix = Path(file_path)

        # remove leading point .shp => shp
        file_suffix = str.lower(file_path_posix.suffix.lstrip("."))

        if file_suffix in layer_lib.raster_extensions:

            try:
                # https://gdal.org/en/stable/api/python/osgeo.gdal.html
                # https://gdal.org/en/stable/api/python/python_examples.html#getting-information-on-a-raster-dataset-using-dedicated-methods
                # https://gdal.org/en/stable/api/python/raster_api.html#osgeo.gdal.Open
                # True => update mode
                # False => read-only
                with gdal.Open(file_path_posix.as_posix(), gdal.GA_ReadOnly) as ds:

                    sr = parse_result.add_resource(
                        "raster-file", path=file_path_posix.as_posix()
                    )

                    parse_result.add_line(
                        f"<a href='tool_evaluate_storable_resource?src_action=show_file_in_explorer&src_dialog={src_dialog}&src_id={sr.id}'>Show in explorer...</a>",
                        indent_cnt + 1,
                    )

                    parse_result.add_line(
                        f"<a href='tool_evaluate_storable_resource?src_action=load_raster_file&src_dialog={src_dialog}&src_id={sr.id}'>Import Raster-Layer '{file_path_posix.name}'...</a>",
                        indent_cnt + 1,
                    )

                    parse_result.add_line(
                        f"<a href='tool_evaluate_storable_resource?src_action=open_with_app&src_dialog={src_dialog}&src_id={sr.id}'>Open with external app...</a>",
                        indent_cnt + 1,
                    )

                    # <osgeo.gdal.Dataset; proxy of <Swig Object of type 'GDALDatasetShadow *' at 0x70138a414ab0> >

                    # https://gdal.org/en/stable/api/python/index.html

                    # 0 => shortName, 1 => longName, 2 => extensions
                    parse_result.add_line(
                        f"<b>GDAL-Driver:</b> {layer_lib.raster_extensions[file_suffix][1]}",
                        indent_cnt + 1,
                    )

                    parse_result.add_line(
                        f"<b>Image-Width:</b> {ds.RasterXSize}", indent_cnt + 1
                    )
                    parse_result.add_line(
                        f"<b>Image-Height:</b> {ds.RasterYSize}", indent_cnt + 1
                    )

                    # f.e. exif
                    # domains = ds.GetMetadataDomainList()
                    # 'IMAGE_STRUCTURE', 'DERIVED_SUBDATASETS'
                    # for domain in domains:
                    #     metadata = ds.GetMetadata(domain)

                    srs = ds.GetSpatialRef()

                    if srs:
                        # <class 'osgeo.osr.SpatialReference'>
                        # f.e. "EPSG"
                        authority_name = srs.GetAuthorityName(None)
                        authority_code = srs.GetAuthorityCode(None)

                        if authority_name and authority_code:
                            # shape-files have projection-metas defined by *.prj, which have no authority_name/authority_code
                            parse_result.add_line(
                                f"<b>Projection:</b> {authority_name}:{authority_code} ({srs.GetName()})",
                                indent_cnt + 1,
                            )
                        else:
                            parse_result.add_line(
                                f"<b>Projection:</b> {srs.GetName()}",
                                indent_cnt + 1,
                            )

                    else:
                        parse_result.add_line(
                            f"<b>Projection:</b> Undefined",
                            indent_cnt + 1,
                        )

                    geotransform = ds.GetGeoTransform()
                    # (306999.5, 1.0, 0.0, 5647999.5, 0.0, -1.0)
                    _left = geotransform[0]
                    _top = geotransform[3]
                    res_x = geotransform[1]
                    res_y = geotransform[5]
                    if (
                        geotransform[2] == 0
                        and geotransform[4] == 0
                        and _left != 0
                        and _top != 0
                    ):
                        width = ds.RasterXSize * res_x
                        height = ds.RasterYSize * res_y
                        _right = _left + width
                        # res_y is negativ
                        _bottom = _top + height

                        srs_wkt = None
                        if srs:
                            srs_wkt = srs.ExportToWkt()

                        # same metadata as for vector-layer
                        sr = parse_result.add_resource(
                            "extent",
                            None,
                            _left=_left,
                            _right=_right,
                            _bottom=_bottom,
                            _top=_top,
                            srs_wkt=srs_wkt,
                        )

                        parse_result.add_line(
                            f"<b>Extent:</b> <a href='tool_evaluate_storable_resource?src_action=show_extent&src_dialog={src_dialog}&src_id={sr.id}'>Zoom/Show Extent...</a>",
                            indent_cnt + 1,
                        )
                        parse_result.add_line(f"<b>left:</b> {_left}", indent_cnt + 2)
                        parse_result.add_line(f"<b>top:</b> {_top}", indent_cnt + 2)
                        parse_result.add_line(f"<b>right: </b>{_right}", indent_cnt + 2)
                        parse_result.add_line(
                            f"<b>bottom: </b>{_bottom}", indent_cnt + 2
                        )

                    else:
                        pass

                    ds_meta_data = ds.GetMetadata()
                    if ds_meta_data and len(ds_meta_data) > 1:

                        # parse Image-Position from Exif
                        _lat = None
                        _lon = None
                        _alt = None
                        _dir = None

                        # regular expression for parsing lat/lon (degree, minutes, decimal-seconds) to float
                        # f.e. EXIF_GPSLatitude = "(50) (51) (48.46)"
                        p_coords = re.compile(
                            r"\(([0-9]*)\) \(([0-9]*)\) \(([0-9]*\.[0-9]*)\)"
                        )
                        # regular expression for parsing altitude and direction
                        # f.e.  EXIF_GPSImgDirection = (7.41748)
                        # p_alt = re.compile(r"\(([0-9]*\.[0-9]*)\)")
                        # bit complex to catch floats and integers
                        p_alt = re.compile(r"\(([0-9]*(\.[0-9]*)?)\)")
                        qq = QUrlQuery()

                        if "EXIF_GPSLongitude" in ds_meta_data:
                            # EXIF_GPSLongitude (6) (28) (18.51)
                            lon_str = ds_meta_data["EXIF_GPSLongitude"]
                            re_rslt = re.findall(p_coords, lon_str)
                            if re_rslt:
                                lon_tuple = re_rslt[0]
                                _lon = (
                                    float(lon_tuple[0])
                                    + float(lon_tuple[1]) / 60
                                    + float(lon_tuple[2]) / 3600
                                )

                        if "EXIF_GPSLatitude" in ds_meta_data:
                            # EXIF_GPSLatitude (50) (51) (48.46)
                            lat_str = ds_meta_data["EXIF_GPSLatitude"]
                            re_rslt = re.findall(p_coords, lat_str)
                            if re_rslt:
                                lat_tuple = re_rslt[0]
                                _lat = (
                                    float(lat_tuple[0])
                                    + float(lat_tuple[1]) / 60
                                    + float(lat_tuple[2]) / 3600
                                )

                        if "EXIF_GPSAltitude" in ds_meta_data:
                            alt_str = ds_meta_data["EXIF_GPSAltitude"]
                            re_rslt = re.findall(p_alt, alt_str)
                            if re_rslt:
                                _alt = float(re_rslt[0][0])

                        if "EXIF_GPSImgDirection" in ds_meta_data:
                            dir_str = ds_meta_data["EXIF_GPSImgDirection"]
                            re_rslt = re.findall(p_alt, dir_str)
                            if re_rslt:
                                _dir = float(re_rslt[0][0])

                        if "EXIF_DateTimeOriginal" in ds_meta_data:
                            parse_result.add_line(
                                f"<b>EXIF_DateTimeOriginal:</b>", indent_cnt + 1
                            )

                            try:

                                dt = datetime.datetime.strptime(
                                    ds_meta_data["EXIF_DateTimeOriginal"],
                                    "%Y:%m:%d %H:%M:%S",
                                )

                                parse_result.add_line(
                                    f"<b>UTC+0:</b> {dt} (without timezone, GMT)",
                                    indent_cnt + 2,
                                )

                                cet = pytz.timezone("CET")
                                # datetime.timedelta
                                offset = cet.utcoffset(dt, is_dst=True)
                                dt_plus_offset = dt + offset

                                offset_hours = offset.seconds / 60 / 60

                                parse_result.add_line(
                                    f"<b>UTC+{offset_hours:.0f}:</b> {dt_plus_offset} (with timezone, CET/CEST)",
                                    indent_cnt + 2,
                                )
                            except Exception as e:
                                pass

                        if _lat and _lon:
                            sr = parse_result.add_resource(
                                "gps_point", _lat=_lat, _lon=_lon, _dir=_dir
                            )

                            parse_result.add_line(
                                f"<b>Exif-Image-Position:</b> <a href='tool_evaluate_storable_resource?src_action=show_gps_point&src_dialog={src_dialog}&src_id={sr.id}'>Show GPS-Point...</a>",
                                indent_cnt + 1,
                            )
                            parse_result.add_line(f"<b>lat:</b> {_lat}", indent_cnt + 2)
                            parse_result.add_line(f"<b>lon:</b> {_lon}", indent_cnt + 2)
                            if _alt:
                                parse_result.add_line(
                                    f"<b>alt:</b> {_alt}", indent_cnt + 2
                                )

                            if _dir:
                                parse_result.add_line(
                                    f"<b>dir:</b> {_dir}", indent_cnt + 2
                                )

                    # parse_result.add_line(f"<b>All Exif-Tags:</b>", indent_cnt + 2)
                    # for key, value in ds_meta_data.items():
                    #     parse_result.add_line(f"{key}: {value}", indent_cnt + 3)

                    # parse_result.add_line(
                    #     f"<b>Bands:</b> {ds.RasterCount}", indent_cnt + 1
                    # )

                    # # https://gdal.org/en/stable/api/python/raster_api.html#osgeo.gdal.Dataset.RasterCount
                    # for b_idx in range(ds.RasterCount):
                    #     # index is 1-based
                    #     # https://gdal.org/en/stable/api/python/raster_api.html#osgeo.gdal.Dataset.GetRasterBand
                    #     # https://gdal.org/en/stable/doxygen/classGDALRasterBand.html

                    #     band = ds.GetRasterBand(b_idx + 1)
                    #     # params: approx_ok und force (only if there are pre-existing metadata)
                    #     stats = band.GetStatistics(False, True)
                    #     # [77.949996948242, 97.639999389648, 90.098128303274, 4.312028873861]

                    #     parse_result.add_line(
                    #         f"<b>Band {b_idx + 1}:</b>", indent_cnt + 2
                    #     )
                    #     parse_result.add_line(
                    #         f"<b>Data type:</b> {gdal.GetDataTypeName(band.DataType)}",
                    #         indent_cnt + 3,
                    #     )
                    #     # https://gdal.org/en/stable/api/python/raster_api.html#osgeo.gdal.Band.GetBlockSize
                    #     # natural block size of this band
                    #     # https://gdal.org/en/stable/api/gdalrasterband_cpp.html#_CPPv4NK14GDALRasterBand12GetBlockSizeEPiPi
                    #     # GDAL contains a concept of the natural block size of rasters so that applications can organized data access efficiently for some file formats. The natural block size is the block size that is most efficient for accessing the format. For many formats this is simple a whole scanline in which case *pnXSize is set to GetXSize(), and *pnYSize is set to 1
                    #     #
                    #     # block_width, block_height = band.GetBlockSize()

                    #     parse_result.add_line(
                    #         f"<b>min:</b> {stats[0]:.3f}", indent_cnt + 3
                    #     )
                    #     parse_result.add_line(
                    #         f"<b>max:</b> {stats[1]:.3f}", indent_cnt + 3
                    #     )

                    #     parse_result.add_line(
                    #         f"<b>mean:</b> {stats[2]:.3f}", indent_cnt + 3
                    #     )
                    #     parse_result.add_line(
                    #         f"<b>StdDev:</b> {stats[3]:.3f}", indent_cnt + 3
                    #     )

            except Exception as e:
                parse_result.add_error(
                    f"Exception opening raster-file '{file_path}':\n{e}",
                    indent_cnt,
                )
        else:
            parse_result.add_error(
                f"File-Suffix '{file_suffix}' not supported", indent_cnt
            )
    else:
        parse_result.add_error(f"File '{file_path}' not found", indent_cnt)

    return parse_result


def create_maplayer(maplayer_node: QDomNode, file_path: str = None) -> QgsMapLayer:
    """create maplayer-node extracted from *qlr/*.qgs/*.qgz or dropped from Layers-Panel
    the created Layer (type depending on layer-type) is *not* added to project
    note: each layer gets a new unique id

    Args:

        maplayer_node (QDomNode): extracted <maplayer>...</maplayer>
        file_path (str): necessary for file-based layers with relative-paths in datasource => qgz/qgs

    Returns:
        QgsMapLayer or None on error, f.e. if path to file-based layer could not be resolved
    """
    # Rev. 2026-11-23

    maplayer_node = maplayer_node.toElement().cloneNode()
    maplayer_id = maplayer_node.namedItem("id").firstChild().toText().data()

    layer_name = maplayer_node.namedItem("layername").firstChild().toText().data()

    # ensure unique layer-id, rename only on demand to keep any layer-id-based-relations
    while QgsProject.instance().mapLayer(maplayer_id):

        # New and unique ID different to the registered one

        # side-effect + problem:
        # all references in forms/field-relations (fieldConfiguration -> field -> editWidget type="RelationReference" -> config -> Option name="ReferencedLayerId")
        # will not be available, Layer-Properties > Attributes Forms will show "Invalid relation"
        # same for virtual-layer-queries
        # quite complicated to resolve...

        # https://doc.qt.io/qt-6/quuid.html
        # replace all non-word/non-ascii-characters with underscore (similar to QGis)
        layer_name_part = re.sub(r"^[a-zA-Z0-9]", "_", layer_name)
        new_id_parts = [layer_name_part]
        uuid = QUuid.createUuid()
        # qgis.PyQt.QtCore.QUuid('{5189c978-8374-4b1c-9c34-342cf4dd6e00}')
        new_id_parts += str(
            uuid.toByteArray(QUuid.StringFormat.WithoutBraces), "utf-8"
        ).split("-")
        maplayer_id = "_".join(new_id_parts)
        id_node = maplayer_node.namedItem("id")
        id_node.firstChild().toText().setData(maplayer_id)

    # <provider encoding="UTF-8">ogr</provider>
    # <provider>arcgismapserver</provider>
    # force to lowercase, because sometimes "WFS" instead of "wfs"
    provider = maplayer_node.namedItem("provider").firstChild().toText().data().lower()

    if provider in ["ogr", "gdal"]:
        # file-based datasource => check path
        # paths can be relative  or absolute to current imported layer (*.qlr/qgs/qgz)

        # absolute:
        # <datasource>/home/ludwig/Seafile/GIS Projekte und Daten/layer/Liegenschaften_GeoPortal_Export.gpkg|layername=liegenschaften_wver_laufend_gepflegt</datasource>

        # relative:
        # <datasource>../Seafile/GIS Projekte und Daten/layer/Liegenschaften_GeoPortal_Export.gpkg|layername=liegenschaften_wver_laufend_gepflegt</datasource>

        # tricky:
        # absolute/relative (default) storage is a project-setting see: Project > Properties > General > Save paths
        # note: in project-files (qgs/qgz) the Project-Settings is stored and could be parsed, but in the exported qlr-files the settings are applied to the stored paths, but not parseable in XML
        # so allways try&error...

        datasource = maplayer_node.namedItem("datasource").firstChild().toText().data()

        datasource_parts = datasource.split("|")
        datasource_path = datasource_parts[0]


        datasource_path_abs = get_absolute_path(datasource_path, file_path)

        if datasource_path_abs:
            new_datasource_path = datasource_path_abs

            # manipulate XML with absolute path
            datasource_parts[0] = new_datasource_path

            # join new path with the old clauses
            #  ../layer/GSK.gpkg|layername=gsk3c_einzugsgebiete|subset="gsk_ezg_gebkz" LIKE '282%'

            new_datasource_path = "|".join(datasource_parts)

            maplayer_node.namedItem("datasource").firstChild().toText().setData(
                new_datasource_path
            )
        else:
            # path to map_layer could not be found neither absolute nor relative!
            show_log_message(
                "WARNING",
                MY_DICT.tr(
                    "ifm_warning_data_source_path_not_found",
                    layer_name,
                    datasource_path,
                ),
                show_iface_message=True,
            )
            return

    layer_type = maplayer_node.toElement().attribute("type")

    # create new_layer with fitting type, else new_layer.readLayerXml(...) returns False
    new_layer = None
    if layer_type == "raster":
        new_layer = QgsRasterLayer()
    elif layer_type == "vector-tile":
        new_layer = QgsVectorTileLayer()
    elif layer_type == "vector":
        new_layer = QgsVectorLayer()
        new_layer.setReadExtentFromXml(True)
    else:
        # sadly QgsMapLayer is abstract and can not be instantiated
        # so omit exotic QgsMapLayer-types,
        # see https://api.qgis.org/api/classQgsMapLayer.html
        show_log_message(
            "WARNING",
            f"skipped not implemented layer-type '{layer_type}'  (contact plugin-author...)",
            show_iface_message=True,
        )

    if new_layer:

        read_successful = new_layer.readLayerXml(
            maplayer_node.toElement(), QgsReadWriteContext()
        )
        if read_successful:
            if new_layer.isValid():
                vector_flags = QgsMapLayer.LayerFlags()
                vector_flags |= QgsMapLayer.LayerFlag.Removable
                if layer_type == "vector":
                    vector_flags |= QgsMapLayer.LayerFlag.Searchable
                    vector_flags |= QgsMapLayer.LayerFlag.Identifiable
                new_layer.setFlags(vector_flags)
                return new_layer
            else:
                # f.e. wms-layers without internet
                show_log_message(
                    "WARNING",
                    "created layer not valid",
                    show_iface_message=True,
                )
        else:
            show_log_message(
                "WARNING",
                f"readLayerXml failed for '{layer_name}'",
                show_iface_message=True,
            )


def parse_project_layer(
    evt: QDropEvent, layer_lib: LayerLib, src_dialog: str, indent_cnt: int = 0
) -> LayerFileParseResult:
    """Drop-Event from QGis-Layers-Panel

    This method parses evt.mimeData and checks usability as resource in LayerLib
    (Layers-Panel supports drag of single/multiple layers/layer-groups)

    Args:
        evt (QDropEvent):
        layer_lib (LayerLib): access to plugin
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation, num of prepended tabs/blanks. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()

    indent_cnt += 1

    parse_result.add_header("Parse Project-Layers:", indent_cnt)

    if evt.mimeData().hasFormat("application/qgis.layertree.layerdefinitions"):

        qlr_xml_str = ba_to_string(
            evt.mimeData().data("application/qgis.layertree.layerdefinitions")
        )

        dom_doc = QDomDocument()

        dom_doc.setContent(qlr_xml_str)

        parse_result.merge(parse_qlr(dom_doc, layer_lib, src_dialog, indent_cnt))

        return parse_result


def parse_browser_panel_layers(
    evt: QDropEvent, layer_lib: LayerLib, src_dialog: str, indent_cnt: int = 0
) -> LayerFileParseResult:
    """Drop-Event from QGis-Browser-Panel

    This method parses evt.mimeData and checks usability as resource in LayerLib
    (only file-based ogr/gdal, but Browser-Panel supports drag of any layer-resource like wms/postgres...)

    Args:
        evt (QDropEvent):
        layer_lib (LayerLib): access to plugin
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): num of prepended tabs/blanks. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23
    parse_result = LayerFileParseResult()

    indent_cnt += 1
    parse_result.add_header(
        f"Parse Layers from Browser-Panel:",
        indent_cnt,
    )

    if evt.mimeData().hasFormat("application/x-vnd.qgis.qgis.uri"):
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

        parse_result.add_line(
            f"Parsing {len(uri_bya_parts)} items dropped from browser-panel",
            indent_cnt + 1,
        )

        for idx, bya_part in enumerate(uri_bya_parts):

            parse_result.add_line(
                f"Uri # {idx + 1} of {len(uri_bya_parts)}",
                indent_cnt + 1,
            )

            uri_decoded = ba_to_string(bya_part)

            # note: uri is seperated by colons, but windows uses ':' in paths, masked as "\:"
            # f.e. 'vector:ogr:2022-01-20 EZG Malefinkbach:C\:/temp/...'
            # workaround to get 'C:/temp/...'
            uri_decoded = uri_decoded.replace(r"\:", "#escaped_colon#")
            uri_parts = uri_decoded.split(":")
            uri_parts = [
                uri_part.replace("#escaped_colon#", ":") for uri_part in uri_parts
            ]

            uri_type = uri_parts[0]

            if uri_type in ["collection", "Xcollection", "custom", "project"]:
                # can be dropped gpkg, zip...
                file_path = uri_parts[3]
                parse_result.merge(
                    parse_file(file_path, layer_lib, src_dialog, indent_cnt)
                )
            elif uri_type in ["raster"]:
                provider = uri_parts[1]
                if provider == "gdal":
                    file_path = uri_parts[3]
                    parse_result.merge(
                        parse_file(file_path, layer_lib, src_dialog, indent_cnt)
                    )
                else:
                    # f.e. 'wms'
                    layer_name = uri_parts[2]
                    datasource = uri_parts[3]
                    geom_type = uri_parts[8]

                    parse_result.add_line(
                        f"<b>Provider:</b> {provider}", indent_cnt + 2
                    )
                    parse_result.add_line(
                        f"<b>Layer-Name:</b> {layer_name}", indent_cnt + 2
                    )
                    parse_result.add_line(
                        f"<b>Datasource:</b> {datasource}", indent_cnt + 2
                    )
                    parse_result.add_line(
                        f"<b>Geeometry-Type:</b> {geom_type}", indent_cnt + 2
                    )

                    # parse_result.add_error(
                    #     f"Provider '{provider}' not supported",
                    #     indent_cnt,
                    #     f"Only <b>file-based</b> raster-layer from browser-panel accepted!\nPlease load layer to project and try drag&amp;drop from layer-panel",
                    # )
            elif uri_type in ["vector"]:
                provider = uri_parts[1]
                if provider == "ogr":
                    uri_path = uri_parts[3]

                    # may contain more than path, f.e. ../layer/GSK.gpkg|layername=gsk3c_einzugsgebiete|subset="gsk_ezg_gebkz" LIKE '282%'
                    uri_path_parts = uri_path.split("|")
                    file_path = uri_path_parts[0]

                    sub_layer_name = ""
                    if len(uri_path_parts) > 1:
                        for uri_path_part in uri_path_parts[1:]:
                            if "layername=" in uri_path_part:
                                sub_layer_name = uri_path_part.replace("layername=", "")
                                break

                    parse_result.merge(
                        parse_file(
                            file_path,
                            layer_lib,
                            src_dialog,
                            indent_cnt,
                            sub_layer_name,
                        )
                    )
                else:
                    layer_name = uri_parts[2]
                    datasource = uri_parts[3]
                    geom_type = uri_parts[8]

                    parse_result.add_line(
                        f"<b>Provider:</b> {provider}", indent_cnt + 2
                    )
                    parse_result.add_line(
                        f"<b>Layer-Name:</b> {layer_name}", indent_cnt + 2
                    )
                    parse_result.add_line(
                        f"<b>Datasource:</b> {datasource}", indent_cnt + 2
                    )
                    parse_result.add_line(
                        f"<b>Geeometry-Type:</b> {geom_type}", indent_cnt + 2
                    )

                    # # f.e. 'postgres'
                    # parse_result.add_error(
                    #     f"Provider '{provider}' not supported",
                    #     indent_cnt,
                    #     "Only <b>file-based</b> vector-layers from browser-panel accepted!\nPlease load layer and try drag&amp;drop from layer-panel",
                    # )
            elif uri_type in ["directory"]:
                uri_path = uri_parts[3]
                parse_result.merge(
                    parse_directory(uri_path, layer_lib, src_dialog, indent_cnt)
                )

            else:
                parse_result.add_error(
                    f"URI-type '{uri_type}' not supported",
                    indent_cnt,
                    f"Only <b>file-based</b> raster/vector-layer, directories or container-files (qlr/qgs/qgz) from browser-panel accepted!\nPlease load layer and try drag&amp;drop from layer-panel",
                )

    return parse_result


def parse_evt_urls(
    evt: QDropEvent, layer_lib: LayerLib, src_dialog: str, indent_cnt: int = 0
) -> LayerFileParseResult:
    """Drop-Event can contain urls, f.e dropped from file-system
    This method checks the first url for usability as resource in LayerLib

    Args:
        evt (QDropEvent):
        layer_lib (LayerLib): access to plugin
        src_dialog (str): id of dialog where the drop occured, used for links (LayerLib.tool_evaluate_storable_resource) referencing LayerLib.parse_cache[src_dialog] 'AddResourceDialog' 'EditResourceDialog' 'LayerLibDialog'
        indent_cnt (int, optional): optical indentation. Defaults to 0.

    Returns:
        LayerFileParseResult
    """
    # Rev. 2026-11-23

    parse_result = LayerFileParseResult()
    indent_cnt += 1

    # parse_result.add_header(
    #     f"Parse Event-URLs:",
    #     indent_cnt,
    # )

    if evt.mimeData().hasUrls():
        parse_result.add_line(
            f"{len(evt.mimeData().urls())} dropped URLs:",
            indent_cnt,
        )
        urlc = 0
        for url in evt.mimeData().urls():
            parse_result.add_line(
                f"- URL # {urlc + 1} of {len(evt.mimeData().urls())}:",
                indent_cnt,
            )

            parse_result.merge(parse_evt_url(url, layer_lib, src_dialog, indent_cnt))
            urlc += 1

    return parse_result


def extract_map_layers(
    dom_doc: QDomDocument = None, container_path: str = None
) -> dict[str, MapLayer]:
    """Scans dom-doc for maplayer-nodes
    Checks the paths (relative or absolute) of file-based layers

    Note:
        can be called with dom_doc, container_path and dom_doc + container_path
        if called without dom_doc, the container_path is used to read dom_doc from container-file


    Args:
        dom_doc (QDomDocument, optional): parsed container file or dropped mime-data from Layers-Panel, if None, the container_path is used to get dom_doc from file
        container_path (str, optional): path for container-file, used to open dom_doc and to resolve absolute/relative paths to qgs/qgz-projects (depending on settings "store paths relative")

    Returns:
        dict[str,MapLayer]: dict key: maplayer_id, value: MapLayer with metas
    """
    # Rev. 2026-11-23
    extracted_map_layers = {}

    if not dom_doc:

        if os.path.isfile(container_path):
            file_suffix = str.lower(Path(container_path).suffix.lstrip("."))
            if file_suffix in CONTAINER_EXTENSIONS:
                dom_doc = get_container_file_dom_doc(container_path)
            else:
                raise Exception(
                    f"File-suffix '{file_suffix}' not supported (*.qgs/*.qgz/*.qlr)"
                )
        else:
            raise FileNotFoundError(f"File '{container_path}' not found")

    if dom_doc:
        maplayer_nodes = dom_doc.documentElement().elementsByTagName("maplayer")
        for maplayer_node in (
            maplayer_nodes.at(i) for i in range(maplayer_nodes.size())
        ):
            # vector, raster, annotation (skipped, annotations not restorable)
            layer_type = maplayer_node.toElement().attribute("type")

            # unique id in project rsp. container-file, used as key for returned dictionary extracted_map_layers
            maplayer_id = maplayer_node.namedItem("id").firstChild().toText().data()

            if layer_type != "annotation":

                map_layer = MapLayer()

                map_layer.maplayer_id = maplayer_id

                map_layer.layer_type = layer_type

                map_layer.layername = (
                    maplayer_node.namedItem("layername").firstChild().toText().data()
                )

                map_layer.datasource = (
                    maplayer_node.namedItem("datasource").firstChild().toText().data()
                )

                # force to lowercase, because sometimes "WFS" instead of "wfs"
                map_layer.provider = (
                    maplayer_node.namedItem("provider")
                    .firstChild()
                    .toText()
                    .data()
                    .lower()
                )

                map_layer.geometry_type = maplayer_node.toElement().attribute(
                    "geometry"
                )

                map_layer.wkbType = maplayer_node.toElement().attribute("wkbType")

                if map_layer.provider in ["gdal", "ogr"]:
                    # only file-based, no postgis, no virtual...
                    # Note: QGis allways uses slashes for relative/absolute paths
                    # Note 2: in QGis-Projects (qgs/qgz) one can specify 'Absolute' or 'Relative' as Project-Property
                    # stored under
                    # <properties>
                    #   <Paths>
                    #       <Absolute type="bool">false</Absolute>
                    #   </Paths>
                    # but in <datasource> both variants are storable and resolved independend from this setting

                    # may contain more than path, f.e. ../layer/GSK.gpkg|layername=gsk3c_einzugsgebiete|subset="gsk_ezg_gebkz" LIKE '282%'
                    datasource_parts = map_layer.datasource.split("|")

                    map_layer.datasource_path = datasource_parts[0]
                    if len(datasource_parts) > 1:
                        for datasource_part in datasource_parts[1:]:
                            if "layername=" in datasource_part:
                                map_layer.sub_layer_name = datasource_part.replace(
                                    "layername=", ""
                                )

                    if container_path:

                        map_layer.abs_path = get_absolute_path(
                            map_layer.datasource_path, container_path
                        )

                        if map_layer.abs_path:

                            map_layer.file_exists = True

                            # regard path absolute/relativ-settings in QGis-Projects
                            file_suffix = str.lower(Path(container_path).suffix.lstrip("."))

                            if file_suffix in ["qgs", "qgz"]:
                                # noticed: QGis (at least 3.4 under linux) doesn't change existing datasources from relative to absolute, so afterwards added layers can have other path-types as already existing layers
                                # if settings are altered, so the stored patsh can be mixed
                                # opening mixed projects directly via double-click accepts both paths (Note: QGis Splash-Screen shows "Updating recent project paths" in case of double-click-project-open)
                                # opening mixed project from already running QGis (f. e. drag&drop or open project from menu) shows dialog "Handle Unavailable Layers"

                                properties_node = dom_doc.documentElement().namedItem(
                                    "properties"
                                )
                                if not properties_node.isNull():
                                    paths_node = properties_node.namedItem("Paths")
                                    if not paths_node.isNull():
                                        absolute_node = paths_node.namedItem("Absolute")
                                        if not absolute_node.isNull():
                                            map_layer.project_path_type_absolute = (
                                                absolute_node.firstChild().toText().data()
                                                == "true"
                                            )
                        else:
                            map_layer.file_exists = False
                            pass
                    else:
                        # non file-based => paths

                        if os.path.isfile(map_layer.datasource_path):
                            map_layer.abs_path = map_layer.datasource_path
                            map_layer.file_exists = True

                    if map_layer.abs_path and container_path:
                        # get_relative_path returns None, if File/Directory have different anchors/drives
                        map_layer.rel_path = get_relative_path(
                            map_layer.abs_path, container_path
                        )

                    if map_layer.abs_path and map_layer.sub_layer_name:
                        with ogr.Open(map_layer.abs_path, gdal.GA_ReadOnly) as ds:
                            map_layer.sub_layer_found = (
                                ds.GetLayer(map_layer.sub_layer_name) is not None
                            )
                            # for sub_layer in ds:
                            #     if sub_layer_name == sub_layer.GetName():
                            #         sub_layer_found = True
                            #         break

                elif map_layer.provider in ["virtual"]:
                    # parse quite complex datasource for virtual layers

                    # strip leading '?', else the first parameter is not parsed
                    qq = QUrlQuery(map_layer.datasource.lstrip("?"))

                    virtual_query = qq.queryItemValue("query")
                    map_layer.virtual_query = urllib.parse.unquote_plus(virtual_query)

                    # in virtual-layer-dialog you can refer vector-layers
                    # by "Import" loaded project-vector-layers (resolved to absolute path)
                    # or "Add" any other valid vector-layer-source
                    # these references are independend from the current virtual-layer, but can be used in any other
                    # virtual layer by using the local_name as alias
                    embedded_layers = qq.allQueryItemValues("resource")

                    embedded_layer_metas = {}

                    for index, embedded_layer_uri in enumerate(embedded_layers):
                        embedded_layer_uri_string = urllib.parse.unquote_plus(
                            embedded_layer_uri
                        )

                        embedded_layer_parts = embedded_layer_uri_string.split(":")
                        # nur Vektor-Layer/Provider wie ogr, postgres...
                        embedded_layer_metas["provider"] = embedded_layer_parts[0]
                        # bei ogr: absolute Pfadangaben, unabhängig von Projekteinstellungen
                        embedded_layer_metas["uri"] = embedded_layer_parts[1]
                        # erste Spalte im dialog
                        embedded_layer_metas["local_name"] = embedded_layer_parts[2]
                        # letzte Spalte, aber nur bei ogr
                        embedded_layer_metas["encoding"] = embedded_layer_parts[3]

                        # note: embedded_local_name is ambiguous and not unique,
                        # therefore unpredictable, which one is used if the same local-name is defined twice and used inside the query
                        map_layer.embedded_layers.append(embedded_layer_metas)

                extracted_map_layers[maplayer_id] = map_layer

    return extracted_map_layers
