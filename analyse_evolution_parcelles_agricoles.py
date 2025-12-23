# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AnalyseEvolutionParcelles
                                 A QGIS plugin
 Analyse automatique de l’évolution des parcelles agricoles entre deux dates,
 avec calcul des variations de surface (par géométrie) et détection des
 parcelles disparues, conservées ou nouvelles.
                              -------------------
        begin                : 2025-11-24
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QCheckBox
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsField,
    QgsVectorFileWriter,
    Qgis,
)
from qgis import processing

from .resources import *  
from .analyse_evolution_parcelles_agricoles_dialog import AnalyseEvolutionParcellesDialog

import os
import csv


class AnalyseEvolutionParcelles:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # Traduction
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'AnalyseEvolutionParcelles_{locale}.qm')
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&Analyse de l’évolution des parcelles agricoles')
        self.first_start = None
        self.dlg = None

    def tr(self, message):
        return QCoreApplication.translate('AnalyseEvolutionParcelles', message)

    # -----------------------
    # UI helpers
    # -----------------------
    def remplir_couches(self):
        """Remplit les combos T1 et T2 avec les couches polygonales du projet."""
        self.dlg.cmbLayerT1.clear()
        self.dlg.cmbLayerT2.clear()

        for couche in QgsProject.instance().mapLayers().values():
            if isinstance(couche, QgsVectorLayer) and couche.geometryType() == QgsWkbTypes.PolygonGeometry:
                self.dlg.cmbLayerT1.addItem(couche.name(), couche.id())
                self.dlg.cmbLayerT2.addItem(couche.name(), couche.id())

    def choisir_fichier_sortie(self):
        """Boîte de dialogue pour choisir le fichier de sortie."""
        fichier, _ = QFileDialog.getSaveFileName(
            self.dlg,
            "Choisir le fichier de sortie",
            "",
            "GeoPackage (*.gpkg);;Shapefile ESRI (*.shp);;Tous les fichiers (*.*)"
        )
        if fichier:
            self.dlg.lineEditOutput_2.setText(fichier)

    def get_layers_selectionnees(self):
        """Retourne (couche_t1, couche_t2) selon les combos."""
        idx_t1 = self.dlg.cmbLayerT1.currentIndex()
        idx_t2 = self.dlg.cmbLayerT2.currentIndex()
        if idx_t1 < 0 or idx_t2 < 0:
            return None, None

        id_t1 = self.dlg.cmbLayerT1.itemData(idx_t1)
        id_t2 = self.dlg.cmbLayerT2.itemData(idx_t2)

        couche_t1 = QgsProject.instance().mapLayer(id_t1)
        couche_t2 = QgsProject.instance().mapLayer(id_t2)
        return couche_t1, couche_t2

    # -----------------------
    # Core processing helpers
    # -----------------------
    @staticmethod
    def _is_null(v):
        """Détecte un NULL PyQGIS de manière robuste."""
        if v is None:
            return True
        try:
            if isinstance(v, QVariant) and v.isNull():
                return True
        except Exception:
            pass
        if isinstance(v, str) and v.strip().upper() == "NULL":
            return True
        return False


    def _export_csv_requested(self) -> bool:
        """Retourne True si une case 'export CSV' existe dans l'UI et est cochée."""
        # Noms d'objets possibles (selon ton .ui)
        candidates = [
            "chkExportCSV", "chkExportCsv", "checkBoxExportCSV", "checkBoxExportCsv",
            "checkBox_csv", "checkBoxCSV", "cbExportCSV", "cbExportCsv",
            "chk_csv", "chkCSV", "exportCsv", "exportCSV"
        ]
        for name in candidates:
            w = getattr(self.dlg, name, None)
            if w is not None and hasattr(w, "isChecked"):
                try:
                    return bool(w.isChecked())
                except Exception:
                    pass

        # fallback: chercher un QCheckBox dont le texte contient "csv"
        try:
            for w in self.dlg.findChildren(QCheckBox):
                if "csv" in (w.text() or "").lower():
                    return bool(w.isChecked())
        except Exception:
            pass

        return False

    def _export_csv(self, layer: QgsVectorLayer, csv_path: str) -> tuple[bool, str]:
        """Exporte la table attributaire de layer en CSV."""
        try:
            # s'assurer que le dossier existe
            out_dir = os.path.dirname(csv_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            field_names = [f.name() for f in layer.fields()]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(field_names)
                for feat in layer.getFeatures():
                    row = []
                    for name in field_names:
                        val = feat[name]
                        if self._is_null(val):
                            row.append("")
                        else:
                            row.append(str(val))
                    writer.writerow(row)

            return True, csv_path
        except Exception as e:
            return False, str(e)

    def preparer_couches(self, couche_t1, couche_t2):
        """Vérifie polygones, harmonise CRS (T2 -> T1), corrige géométries."""
        if couche_t1 is None or couche_t2 is None:
            return None, None

        if couche_t1.geometryType() != QgsWkbTypes.PolygonGeometry:
            QMessageBox.critical(self.dlg, "Erreur", f"La couche T1 ({couche_t1.name()}) n'est pas une couche de polygones.")
            return None, None

        if couche_t2.geometryType() != QgsWkbTypes.PolygonGeometry:
            QMessageBox.critical(self.dlg, "Erreur", f"La couche T2 ({couche_t2.name()}) n'est pas une couche de polygones.")
            return None, None

        t1, t2 = couche_t1, couche_t2

        # Reprojection T2 si CRS différent
        if t1.crs() != t2.crs():
            try:
                t2 = processing.run(
                    "native:reprojectlayer",
                    {"INPUT": t2, "TARGET_CRS": t1.crs(), "OUTPUT": "memory:"}
                )["OUTPUT"]
            except Exception as e:
                QMessageBox.critical(self.dlg, "Erreur de reprojection", f"Impossible de reprojeter T2 vers le CRS de T1.\n\nDétail : {e}")
                return None, None

        # Fix geometries
        try:
            t1 = processing.run("native:fixgeometries", {"INPUT": t1, "OUTPUT": "memory:"})["OUTPUT"]
            t2 = processing.run("native:fixgeometries", {"INPUT": t2, "OUTPUT": "memory:"})["OUTPUT"]
        except Exception as e:
            QMessageBox.critical(self.dlg, "Erreur de correction", f"Impossible de corriger les géométries.\n\nDétail : {e}")
            return None, None

        return t1, t2

    def _save_vector(self, layer, fichier):
        """Sauvegarde robuste (GPKG/SHP) compatible QGIS 3.34+."""
        if not fichier:
            return False, "Chemin de sortie vide."

        ext = os.path.splitext(fichier)[1].lower()
        if ext == ".gpkg":
            driver = "GPKG"
        elif ext == ".shp":
            driver = "ESRI Shapefile"
        else:
            driver = "GPKG"
            fichier = fichier + ".gpkg"

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = driver
        opts.fileEncoding = "UTF-8"
        if driver == "GPKG":
            opts.layerName = os.path.splitext(os.path.basename(fichier))[0]

        res = QgsVectorFileWriter.writeAsVectorFormatV2(
            layer,
            fichier,
            QgsProject.instance().transformContext(),
            opts
        )

        # res peut être (err, msg) ou autre selon version -> on évite unpack.
        err = None
        msg = ""
        if isinstance(res, tuple):
            if len(res) >= 1:
                err = res[0]
            if len(res) >= 2:
                msg = res[1]
        else:
            err = res

        if err != QgsVectorFileWriter.NoError:
            return False, msg or "Erreur inconnue lors de l'écriture."
        return True, fichier

    def executer_analyse(self):
        """Analyse (surfaces par géométrie) via UNION."""
        couche_t1, couche_t2 = self.get_layers_selectionnees()
        if couche_t1 is None or couche_t2 is None:
            QMessageBox.critical(self.dlg, "Erreur", "Veuillez choisir une couche T1 et une couche T2.")
            return

        t1, t2 = self.preparer_couches(couche_t1, couche_t2)
        if t1 is None or t2 is None:
            return

        # UNION
        try:
            union_layer = processing.run(
                "native:union",
                {
                    "INPUT": t1,
                    "OVERLAY": t2,
                    "INPUT_FIELDS": [],
                    "OVERLAY_FIELDS": [],
                    "OVERLAY_FIELDS_PREFIX": "T2_",
                    "OUTPUT": "memory:union",
                },
            )["OUTPUT"]
        except Exception as e:
            QMessageBox.critical(self.dlg, "Erreur", f"Impossible de faire l'union.\n\nDétail : {e}")
            return

        provider = union_layer.dataProvider()

        # Champs résultats
        provider.addAttributes([
            QgsField("surf_T1", QVariant.Double),
            QgsField("surf_T2", QVariant.Double),
            QgsField("var_abs", QVariant.Double),
            QgsField("var_pct", QVariant.Double),
            QgsField("statut", QVariant.String),
        ])
        union_layer.updateFields()
        fields = union_layer.fields()

        idx_surf_t1 = fields.indexFromName("surf_T1")
        idx_surf_t2 = fields.indexFromName("surf_T2")
        idx_var_abs = fields.indexFromName("var_abs")
        idx_var_pct = fields.indexFromName("var_pct")
        idx_statut = fields.indexFromName("statut")

        # Présence T1/T2: utilise AN / T2_AN si disponible (BDPPAD)
        has_an = fields.indexFromName("AN") != -1
        has_t2_an = fields.indexFromName("T2_AN") != -1

        seuil = float(self.dlg.spinBox.value())

        changes = {}
        for f in union_layer.getFeatures():
            geom = f.geometry()
            if geom is None or geom.isEmpty():
                continue

            area = float(geom.area())

            if has_an:
                present_t1 = not self._is_null(f["AN"])
            else:
                present_t1 = True

            if has_t2_an:
                present_t2 = not self._is_null(f["T2_AN"])
            else:
                present_t2 = False
                for name in fields.names():
                    if name.startswith("T2_") and not self._is_null(f[name]):
                        present_t2 = True
                        break

            surf_t1 = area if present_t1 else 0.0
            surf_t2 = area if present_t2 else 0.0

            var_abs = surf_t2 - surf_t1
            var_pct = (var_abs / surf_t1 * 100.0) if surf_t1 > 0 else (100.0 if surf_t2 > 0 else 0.0)

            if surf_t1 == 0.0 and surf_t2 > 0.0:
                statut = "nouvelle"
            elif surf_t1 > 0.0 and surf_t2 == 0.0:
                statut = "disparue"
            else:
                if abs(var_pct) < seuil:
                    statut = "conservee"
                elif var_pct > 0:
                    statut = "augmente"
                else:
                    statut = "diminuee"

            changes[f.id()] = {
                idx_surf_t1: surf_t1,
                idx_surf_t2: surf_t2,
                idx_var_abs: var_abs,
                idx_var_pct: var_pct,
                idx_statut: statut,
            }

        provider.changeAttributeValues(changes)

        # Sauvegarde (vecteur) + (optionnel) export CSV
        fichier = self.dlg.lineEditOutput_2.text().strip()
        if not fichier:
            self.iface.messageBar().pushMessage(
                "Erreur",
                "Veuillez choisir un fichier de sortie.",
                level=Qgis.Critical,
                duration=6,
            )
            return

        export_csv = self._export_csv_requested()

        # Si l'utilisateur a choisi un .csv, on crée le vecteur en .gpkg à côté
        ext = os.path.splitext(fichier)[1].lower()
        if ext == ".csv":
            csv_path = fichier
            vector_path = os.path.splitext(fichier)[0] + ".gpkg"
        else:
            vector_path = fichier
            csv_path = os.path.splitext(fichier)[0] + ".csv"

        ok, info = self._save_vector(union_layer, vector_path)
        if not ok:
            QMessageBox.critical(self.dlg, "Erreur", f"Échec de sauvegarde.\n\nDétail : {info}")
            return

        # Ajouter au projet
        nom_couche = os.path.splitext(os.path.basename(info))[0]
        union_layer.setName(nom_couche)
        QgsProject.instance().addMapLayer(union_layer)

        self.iface.messageBar().pushMessage(
            "Analyse terminée",
            f"Couche '{nom_couche}' créée (surfaces par géométrie) et sauvegardée.",
            level=Qgis.Success,
            duration=8,
        )

        # Export CSV si demandé
        if export_csv:
            ok_csv, info_csv = self._export_csv(union_layer, csv_path)
            if ok_csv:
                self.iface.messageBar().pushMessage(
                    "Export CSV",
                    f"CSV créé : {info_csv}",
                    level=Qgis.Info,
                    duration=6,
                )
            else:
                self.iface.messageBar().pushMessage(
                    "Export CSV",
                    f"Échec de l'export CSV : {info_csv}",
                    level=Qgis.Warning,
                    duration=8,
                )

        # Fermer le panneau
        try:
            self.dlg.accept()
        except Exception:
            self.dlg.close()

    # -----------------------
    # QGIS plugin boilerplate
    # -----------------------
    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = ':/plugins/analyse_evolution_parcelles_agricoles/icon.png'
        self.add_action(
            icon_path,
            text=self.tr("Analyse de l’évolution des parcelles agricoles"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )
        self.first_start = True

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&Analyse de l’évolution des parcelles agricoles'), action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        if self.first_start is True or self.dlg is None:
            self.first_start = False
            self.dlg = AnalyseEvolutionParcellesDialog()
            self.dlg.btnBrowseOutput.clicked.connect(self.choisir_fichier_sortie)

        self.remplir_couches()

        # éviter multiples connexions
        try:
            self.dlg.pushButton_2.clicked.disconnect()
        except Exception:
            pass
        self.dlg.pushButton_2.clicked.connect(self.executer_analyse)

        self.dlg.show()
        self.dlg.exec_()
