import os
from urllib import request, parse
from qgis.core import QgsTask
from qgis.PyQt.QtCore import pyqtSignal

class DemDownloadTask(QgsTask):
    download_finished = pyqtSignal(str)
    download_error = pyqtSignal(str)

    def __init__(self, bbox, api_key, output_folder, layer_name):
        
        super().__init__(f"Baixar MDE ({layer_name})")
        self.bbox = bbox
        self.api_key = api_key
        self.output_tif_path = os.path.join(
            output_folder, f"MDE_{layer_name}.tif")
        self.erro_msg = ""
        self.layer_name = layer_name

    def run(self):
        url = "https://portal.opentopography.org/API/globaldem"
        params = {
            'demtype': 'SRTMGL1', 
            'outputFormat': 'GTiff', 
            'API_Key': self.api_key,
            'west': self.bbox['west'], 
            'east': self.bbox['east'],
            'south': self.bbox['south'], 
            'north': self.bbox['north']
        }
        try:
            self.setProgress(2)
            url_params = parse.urlencode(params)
            url_complete = f"{url}?{url_params}"

            request.urlretrieve(url_complete, self.output_tif_path)

            self.setProgress(5)
            return True
        except Exception as e:
            if os.path.exists(self.output_tif_path):
                os.remove(self.output_tif_path)
            self.erro_msg = str(e)
            return False

    def finished(self, result):
        if result:
            self.download_finished.emit(self.output_tif_path)
        else:
            self.download_error.emit(f"-> Erro ao baixar a imagem MDE da área '{self.layer_name}', verifique a sua internet.")
