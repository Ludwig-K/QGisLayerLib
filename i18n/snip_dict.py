#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
********************************************************************

* Part of the QGis-Plugin LayerLib:
* Dictionary, currently english/german
* Uses XML-File "Snippets.xml" with translations, File must be
* inside the current directory
* Note:
* snip_dict_editor.py contains Stand-Alone QApplication
* to maintain the translations
* replacement for Qt Linguist

********************************************************************

* Date                 : 2026-11
* Copyright            : (C) 2026 by Ludwig Kniprath
* Email                : ludwig at kni minus online dot de

********************************************************************

this program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

********************************************************************
"""

# Rev. 2026-11-21

import os, re
from qgis.PyQt.QtXml import QDomDocument
from pathlib import Path

from qgis.PyQt.QtCore import QSettings, QLocale



class SnipDict:
    """
    replacement for Qt Linguist rsp. QtCore.QCoreApplication.translate(...), which is hard to maintain and has problems with markups
    used for all kinds of Qt-GUI-Strings e.g. ToolTips, Labels, messages...
    translations are supported via lcid
    Uses a single XML-File instead of previous storage in SQlite-DB/Table
    """
    # Rev. 2026-11-21

    def __init__(self):
        """constructor
        parses XML-File and stores snippets in dictionary, key: snip_key, value: translation (language dependend en/de)

        Raises:
            Exception: dialogs and messages are not usable without translation
        """
        # Rev. 2026-11-21
        # dictionary of parsed snippets, key: snip_key, value: translated content for locale
        self.tr_dict = {}

        # Default-Wert, falls für die aktuelle Sprachumgebung keine Übersetzung vorliegt
        # für diese Sprache müssen dann auch Übersetzungen vorhanden sein
        # <trans lan="en">...</trans>
        self.default_language = "en"

        # file-name and path hard coded, here relative to current file
        snippets_path = (Path(os.path.dirname(__file__)) / "Snippets.xml").as_posix()

        snippets_path_posix = Path(snippets_path)

        if snippets_path_posix.is_file():

            self.snippets_dom_doc = QDomDocument()

            with open(snippets_path_posix.as_posix(), 'rb', -1) as in_f:
                # can raise exceptions, f.e. if there are control-characters in the xml-file
                parse_ok, error_msg, error_line, error_col = (
                    self.snippets_dom_doc.setContent(in_f.read())
                )

                if parse_ok:

                    # locale = system-locale, independent from current app
                    lcid = QLocale.system().name()
                    # or optional deviating locale from QtCore.QSettings(),
                    if QSettings().value("locale/overrideFlag", type=bool):
                        lcid = QSettings().value("locale/userLocale", "en_US")

                    # lcid is a string composed of language, underscore and country
                    # for the translation the language is sufficient:
                    # 'de_DE', 'de_AT', 'de_CH', 'de_BE', 'de_LI'... -> 'de'
                    # 'en_US', 'en_GB'... -> 'en'
                    lcid_language = lcid[0:2]

                    snippet_nodes = self.snippets_dom_doc.elementsByTagName("snippet")
                    for snippet_node in (
                        snippet_nodes.at(i) for i in range(snippet_nodes.size())
                    ):
                        snip_key = snippet_node.toElement().attribute("snip_key")

                        translations = {}

                        child_nodes = snippet_node.childNodes()

                        for node_idx in range(child_nodes.size()):
                            child_node = child_nodes.at(node_idx)
                            if child_node.nodeName() == "trans":
                                lan = child_node.toElement().attribute("lan")
                                snip_content = child_node.firstChild().toText().data()
                                # re-replace CDEnd, see SnipDictEditor.create_snippet_node
                                snip_content = re.sub("##CDEnd##", "]]>", snip_content)
                                translations[lan] = snip_content

                        if lcid_language in translations:
                            # language-dependend translation, if found
                            snip_content = translations[lcid_language]
                        elif self.default_language in translations:
                            # Default-Translation...
                            snip_content = translations[self.default_language]
                        else:
                            # or dummy, shown in dialogs/widgets/messages, better than Exception
                            snip_content = f"?[{snip_key}] translation?"

                        self.tr_dict[snip_key] = snip_content
                else:
                    raise Exception(
                        f"LayerLib: parsing SnippetsPath '{snippets_path}' failed in line #{error_line}: {error_msg}"
                    )
        else:
            raise Exception(
                f"LayerLib: parsing SnippetsPath '{snippets_path}' failed: file not found"
            )

    def tr(self, snip_key, *embeds) -> str:
        """
        returns the translated snippet from self.tr_dict

        Args:
            snip_key (str): key, for which the function searches in the snippet-dictionoary
            embeds (list): any number of arguments, which are stringified and embedded into the template via format-like wildcards {0} {1}...

        Returns:
            str: translated content with replacements ("?[{snip_key}]?" if the key is not found)
        """
        # Rev. 2026-11-21
        snip_content = self.tr_dict.get(snip_key, f"?[{snip_key}]?")
        for index, value in enumerate(embeds):
            snip_content = snip_content.replace(f"{{{index}}}", str(value))
        return snip_content
