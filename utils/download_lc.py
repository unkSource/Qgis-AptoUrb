import os
import urllib.request
from qgis.core import QgsTask, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsPointXY
from qgis.PyQt.QtCore import pyqtSignal

class EsrilcDownloadTask(QgsTask):
    download_finished = pyqtSignal(str, str)
    download_error = pyqtSignal(str)

    def __init__(self, bbox, output_folder, layer_name, year):
        super().__init__(f"Baixar Uso do Solo ({layer_name})")
        self.bbox, self.output_folder, self.layer_name = bbox, output_folder, layer_name
        self.path = output_folder
        self.year = year
        self.erro_msg = "Erro ao tentar baixar, verifique a sua internet!"

    def run(self):
        try:
            if self.isCanceled():
                return False
            
            self.setProgress(10)
            
            # 1. Transforma a BBOX para EPSG:3857
            xf = QgsCoordinateTransform(QgsCoordinateReferenceSystem(
                "EPSG:4326"), QgsCoordinateReferenceSystem("EPSG:3857"), QgsProject.instance())
            sw = xf.transform(QgsPointXY(self.bbox['west'], self.bbox['south']))
            ne = xf.transform(QgsPointXY(self.bbox['east'], self.bbox['north']))

            self.setProgress(30)

            mosaic_rule = f'{{"mosaicMethod":"esriMosaicAttribute","where":"Year = {self.year}","sortField":"Year","sortValue":0}}'

            # 2. URL e tamanho do raster
            w = max(100, int((ne.x() - sw.x()) / 10.0))
            h = max(100, int((ne.y() - sw.y()) / 10.0))
            if w > 4000 or h > 4000:
                self.erro_msg = f"Infelizmente a área do arquivo a ser baixado é de {w}x{h} px e é acima do limite permitido, clique no botão (Detalhes)!"
                return False
            url = "https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer/exportImage"

            params = {
                'bbox': f"{self.bbox['west']},{self.bbox['south']},{self.bbox['east']},{self.bbox['north']}",
                'bboxSR': '4326',
                'imageSR': '4326',
                'size': f"{w},{h}",
                'format': 'tiff',
                'pixelType': 'U8',
                'mosaicRule': mosaic_rule,
                'f': 'image'
            }
            
            self.setProgress(50)

            url_params = urllib.parse.urlencode(params)
            url_complete = f"{url}?{url_params}"

            # 3. Download e gravação direta em 1 linha
            urllib.request.urlretrieve(url_complete, self.path)
            self.setProgress(100)
            return True
        except Exception as e:
            if os.path.exists(self.path):
                os.remove(self.path)
            #self.erro_msg = str(e)
            return False

    def finished(self, result):
        if result:
            self.download_finished.emit(self.path, f"Imagem LC 10m - {self.layer_name}_{self.year}")
        else: 
            self.download_error.emit(self.erro_msg)
