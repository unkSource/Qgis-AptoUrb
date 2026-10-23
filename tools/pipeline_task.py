# pipeline_task.py
from qgis.core import QgsTask, QgsRasterLayer, QgsProcessingFeedback
from qgis.PyQt.QtCore import pyqtSignal
from osgeo import gdal
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
import os
import processing


class PipelineTask(QgsTask):
    # Sinais para atualizar a tua UI em tempo real sem travar a tela
    log_text_browser = pyqtSignal(str)
    progress_bar = pyqtSignal(int)
    completed = pyqtSignal(bool, str)  # (Sucesso?, Caminho_Final_ou_Erro)

    def __init__(self, layer_mask_area, layer_mask, mde_input, lc_input, lc_data_table, crs_utm, temp_folder, final_raster):
        # QgsTask.CanCancel permite que o usuário cancele o processo no gerenciador do QGIS
        super().__init__("Processar raster de adequabilidade urbana", QgsTask.CanCancel)
        self.layer_mask_area = layer_mask_area
        self.layer_mask = layer_mask
        self.mde_input = mde_input
        self.lc_input = lc_input
        self.lc_data_table = lc_data_table
        self.crs_utm = crs_utm
        self.temp_folder = temp_folder
        self.final_raster = final_raster

    def run(self):
        process_feedback = QgsProcessingFeedback()
        crs_mask = self.layer_mask.crs().authid()
        try:
            # -----------------------------------------------------------------
            # [Etapa 1] Recortar o MDE.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 1] Recortando o Modelo Digital de Elelvação...")
            self.setProgress(10)

            input_source = self.mde_input
            raster_mde_cliped = os.path.join(
                self.temp_folder, "mde_raster_recortado.tif")

            processing.run("gdal:cliprasterbymasklayer", {
                'INPUT': input_source,
                'MASK': self.layer_mask,
                'NODATA': -9999,
                'ALPHA_BAND': False,
                'OPTIONS': '',
                'DATA_TYPE': 5,
                'OUTPUT': raster_mde_cliped
            }, feedback=process_feedback)

            if not os.path.exists(raster_mde_cliped):
                self.completed.emit(
                    False, "Erro ao recortar o raster do MDE!")
                return False

            self.log_text_browser.emit(
                "Raster r1ecortado do MDE gerado com sucesso!")
            # -----------------------------------------------------------------
            # [Etapa 2] Reprojetar o MDE (Teu código adaptado para segundo plano)
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit("\n[Etapa 2] Reprojetando o MDE...")
            self.setProgress(5)

            # Extrai a string de origem de forma segura na thread secundária
            mde_reprojected = os.path.join(
                self.temp_folder, "mde_reprojected.tif")

            processing.run("gdal:warpreproject",
                {
                    'INPUT': raster_mde_cliped,
                    'SOURCE_CRS': None,                 
                    'TARGET_CRS': self.crs_utm,
                    'RESAMPLING': 0,
                    'NODATA': -9999,                     
                    'TARGET_RESOLUTION': None,
                    'OPTIONS': '',
                    'DATA_TYPE': 5,
                    'TARGET_EXTENT': None,
                    'TARGET_EXTENT_CRS': None,
                    'MULTITHREADING': False,
                    'EXTRA': '-srcnodata -9999 -dstnodata -9999',
                    'OUTPUT': mde_reprojected
                },
                feedback=process_feedback
            )

            if not os.path.exists(mde_reprojected):
                self.completed.emit(False, "Falha na reprojeção do MDE via GDAL.")
                return False

            result = None  # Fecha o arquivo no HD
            self.log_text_browser.emit("MDE reprojetado com sucesso!")

            # -----------------------------------------------------------------
            # [Etapa 3] Remover imperfeições do MDE de forma 100% nativa e garantida
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 3] Preenchendo falhas (NoData) do MDE...")
            self.setProgress(15)

            mde_filled = os.path.join(self.temp_folder, "mde_filled.tif")

            processing.run("gdal:fillnodata", {
                'INPUT': mde_reprojected,
                'BAND': 1,
                'DISTANCE': 10,
                'ITERATIONS': 0,
                'MASK_LAYER': None,
                'CREATION_OPTIONS': 'PROFILE=GeoTIFF',
                'EXTRA': '',
                'OUTPUT': mde_filled   
            }, feedback=process_feedback)

            if not os.path.exists(mde_filled):
                self.completed.emit(False, "Erro ao preencher falhas do MDE.")
                return False

            self.log_text_browser.emit(
                "Depressões e falhas corrigidas com sucesso!")
            
            # -----------------------------------------------------------------
            # [EtapaS 4] Extrair segmentos de fluxo adaptados ao tamanho da área de estudo.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 4] Gerando segmentos de fluxo...")
            self.setProgress(15)
            
            flow_segment = os.path.join(
                self.temp_folder, "fluxo_segmentos.tif")

            # 2. Pega o tamanho do pixel do MDE (ex: 30 metros)
            raster = QgsRasterLayer(mde_filled, "temp")
            pixel_size = raster.rasterUnitsPerPixelX()
            # Área de 1 único pixel (ex: 900 m²)
            pixel_area = pixel_size * pixel_size

            # 3. AUTOMAÇÃO: Threshold dinâmico (ex: o canal precisa de acumular pelo menos 1% da área total)
            num_pixels_total = self.layer_mask_area / pixel_area
            threshold_dinamico = max(100, int(num_pixels_total * 0.01))

            # 4. Executa o algoritmo com o valor calculado
            processing.run("grass7:r.watershed", {
                    'elevation': mde_filled,
                    'threshold': threshold_dinamico,  # Usa o valor inteligente aqui!
                    'stream': flow_segment,
                    'GRASS_REGION_PARAMETER': None,
                    'GRASS_REGION_CELLSIZE_PARAMETER': 0
            }, feedback=process_feedback)

            if not os.path.exists(flow_segment):
                self.completed.emit(
                    False, "Erro na geração do segmentos de fluxo!")
                return False
            self.log_text_browser.emit(
                "Segmentos de fluxo gerados com sucesso!")   
            # -----------------------------------------------------------------
            # [EtapaS 5] Calcular a distância euclidiana usando o r.grow.distance do GRASS.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 5] Gerando a distância euclidiana...")
            self.setProgress(20)

            flow_distance = os.path.join(self.temp_folder, "distancia_fluxo.tif")
            flow_distance_value = os.path.join(self.temp_folder, "ids_fluxo.tif")

            # Executa o r.grow.distance nativo do GRASS
            processing.run("grass7:r.grow.distance", {
                'input': flow_segment,
                'metric': 0,               # 0 = Métrica Euclidiana Pura
                'distance': flow_distance,    # Raster de saída com as distâncias em metros
                'value': flow_distance_value,
                'GRASS_REGION_PARAMETER': None,
                'GRASS_REGION_CELLSIZE_PARAMETER': 0
            }, feedback=process_feedback)

            if not os.path.exists(flow_distance):
                self.completed.emit(False, "Erro ao gerar a distância euclidiana!")
                return False
            self.log_text_browser.emit(
                "Distância euclidiana gerado com sucesso!")
            # -----------------------------------------------------------------
            # [EtapaS 6] Classificar o raster de distância em pesos de 1 a 5.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 6] Classificando distâncias em pesos (1 a 5)...")
            self.setProgress(30)

            distance_classified = os.path.join(
                self.temp_folder, "distancia_pesos.tif")
            
            table = [
                0, 30, 5,    # 0 a 30m   -> Peso 5
                30, 50, 4,   # 30 a 50m  -> Peso 4
                50, 100, 3,  # 50 a 100m -> Peso 3
                100, 200, 2,  # 100 a 200m-> Peso 2
                200, 999999, 1  # > 200m  -> Peso 1
            ]
            processing.run("native:reclassifybytable", {
                'INPUT_RASTER': flow_distance,
                'RASTER_BAND': 1,
                'TABLE': table,
                'NO_DATA_VALUE': 0,
                # 2 = min < valor <= max (Garante as tuas faixas exatas)
                'RANGE_BOUNDARIES': 2,
                'DATA_TYPE': 0,         # Float32 para manter compatibilidade
                'OUTPUT': distance_classified
            }, feedback=process_feedback)

            if not os.path.exists(distance_classified):
                self.completed.emit(
                    False, " Erro ao gerar raster da distancia classificada!")
                return False
            self.log_text_browser.emit(
                "Raster da distancia classificada gerado com sucesso!")

            # -----------------------------------------------------------------
            # [EtapaS 7] Calcular a declividade (Slope) em percentagem a partir do MDE corrigido.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 7] Calculando declividade (Slope) em percentagem...")
            self.setProgress(35)

            slope = os.path.join(
                self.temp_folder, "declividade_percentagem.tif")
            
            processing.run("gdal:slope", {
                'INPUT': mde_filled,
                'BAND': 1,
                'SCALE': 1,
                'AS_PERCENT': True,      
                'COMPUTE_EDGES': True,
                'ZEVENBERGEN': False,
                'EXTRA': '',
                'OUTPUT': slope
            }, feedback=process_feedback)

            if not os.path.exists(slope):
                self.completed.emit(False, "Erro ao gerar raster de declividade!")
                return False
            self.log_text_browser.emit(
                "Raster de declividade gerado com sucesso!")
            # -----------------------------------------------------------------
            # [EtapaS 8] Reclassificar o raster de declividade (%) em pesos de 1 a 5.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 8] Reclassificando declividade em pesos (1 a 5)...")
            self.setProgress(40)

            slope_classified = os.path.join(
                self.temp_folder, "declividade_pesos.tif")
            
            tabela = [
                0, 3, 4, 
                3, 5, 2,
                5, 30, 1,
                30, 47, 3,
                47, 999999, 5
            ]

            processing.run("native:reclassifybytable", {
                'INPUT_RASTER': slope,
                'RASTER_BAND': 1,
                'TABLE': tabela,
                'NO_DATA_VALUE': 0,
                'RANGE_BOUNDARIES': 2,  # 2 = min < valor <= max
                'DATA_TYPE': 0,
                'OUTPUT': slope_classified
            }, feedback=process_feedback)

            if not os.path.exists(slope_classified):
                self.completed.emit(False,
                    "Erro ao gerar Raster da declividade classificado!")
                return False
            self.log_text_browser.emit(
                "Raster de declividade classificado gerado com sucesso!")
            # -----------------------------------------------------------------
            # [EtapaS 9] Reprojetar o LC de forma ultra-compacta.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 9] Reprojetando o LC...")
            self.setProgress(40)

            land_cover_reprojected = os.path.join(
                self.temp_folder, "lc_reprojected.tif")
            lc_source = self.lc_input if isinstance(
                self.lc_input, str) else self.lc_input.source()
            
            options = gdal.WarpOptions(
                dstSRS=self.crs_utm,
                resampleAlg=gdal.GRIORA_NearestNeighbour,
                srcNodata=0,
                dstNodata=0)
            result = gdal.Warp(land_cover_reprojected, 
                               lc_source, 
                               options=options)

            if result is None:
                self.completed.emit(False, "Erro ao gerar raster LC reprojetado!")
                return False
            
            result = None
            self.log_text_browser.emit(
                "Raster LC reprojetado gerado com sucesso!")
            # -----------------------------------------------------------------
            # [EtapaS 10] Reclassificar o raster de Land Cover usando os pesos do tableWidget.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 10] Reclassificando Land Cover com pesos da tabela...")
            self.setProgress(50)

            lc_classified = os.path.join(self.temp_folder, "land_cover_pesos.tif")
            
            if not self.lc_data_table:
                self.completed.emit(False, "Erro: A tabela de Uso e Cobertura de Solo está vazia ou não foi preenchida.")
                return False
            
            lc_table = []
            for id_classe, peso in self.lc_data_table.items():
                lc_table.extend([id_classe, id_classe, peso])
            
            processing.run("native:reclassifybytable", {
                'INPUT_RASTER': land_cover_reprojected,
                'RASTER_BAND': 1,
                'TABLE': lc_table,
                'NO_DATA_VALUE': 0,
                'RANGE_BOUNDARIES': 2,
                'DATA_TYPE': 0,
                'OUTPUT': lc_classified
            }, feedback=process_feedback)

            if not os.path.exists(lc_classified):
                self.completed.emit(False, "Erro ao gerar Raster de Uso e Cobertura do Solo classificado!")
                return False
            
            self.log_text_browser.emit(
                "Raster do Uso e Cobertura do Solo classificado gerado com sucesso!")
            # -----------------------------------------------------------------
            # [EtapaS 11] Fuzzificar os 3 rasters de pesos (Linear: 1->0 a 5->1).
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 11] Aplicando Fuzzificação Linear (escala 0 a 1)...")

            v_distance = os.path.join(self.temp_folder, "distancia_fuzzified.tif")
            v_slope = os.path.join(self.temp_folder, "declividade_fuzzified.tif")
            v_lc = os.path.join(self.temp_folder,"land_cover_fuzzified.tif")
            
            params_base = {
                'BAND': 1,
                'FUZZYLOWBOUND': 1,    # Peso mínimo original
                'FUZZYHIGHBOUND': 5,   # Peso máximo original
            }

            # 1. Fuzzificar Distância
            self.log_text_browser.emit(
                "   -> Fuzzificando distância de corpos hidricos...")
            processing.run("native:fuzzifyrasterlinearmembership", 
                           {
                               **params_base, 
                                'INPUT': distance_classified, 
                                'OUTPUT': v_distance
                           }, feedback=process_feedback)
            self.setProgress(53)

            # 2. Fuzzificar Declividade
            self.log_text_browser.emit(
                "   -> Fuzzificando declividade...")
            processing.run("native:fuzzifyrasterlinearmembership", 
                           {
                               **params_base, 
                                'INPUT': slope_classified, 
                                'OUTPUT': v_slope
                           }, feedback=process_feedback)
            self.setProgress(55)
            # 3. Fuzzificar Land Cover
            self.log_text_browser.emit(
                "   -> Fuzzificando uso e cobertura do solo...")
            processing.run("native:fuzzifyrasterlinearmembership", 
                           {
                               **params_base, 
                               'INPUT': lc_classified, 
                               'OUTPUT': v_lc
                           }, feedback=process_feedback)
            self.setProgress(60)
            if not os.path.exists(v_distance) and os.path.exists(v_slope) and os.path.exists(v_lc):
                self.completed.emit(False,
                    "Erro ao fuzzificar as variaveis!")
                return False
            
            self.log_text_browser.emit(
                "As três variáveis foram fuzzificadas com sucesso!")
            
            # -----------------------------------------------------------------
            # [EtapaS 12] Calcular a Média Ponderada simples usando QgsRasterCalculator nativo.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 12] Realizando a média dos rasters...")
            self.setProgress(70)

            average_raster = os.path.join(self.temp_folder, "raster_media.tif")

            lyr_dist = QgsRasterLayer(v_distance)
            lyr_slope = QgsRasterLayer(v_slope)
            lyr_lc = QgsRasterLayer(v_lc)

            # 2. Criar a lista de entradas (Raster Entries) mapeando aliases simples
            entries = []

            # Entrada A (Distância)
            entry_a = QgsRasterCalculatorEntry()
            entry_a.ref = "A@1"
            entry_a.raster = lyr_dist
            entry_a.bandNumber = 1
            entries.append(entry_a)

            # Entrada B (Declividade)
            entry_b = QgsRasterCalculatorEntry()
            entry_b.ref = "B@1"
            entry_b.raster = lyr_slope
            entry_b.bandNumber = 1
            entries.append(entry_b)

            # Entrada C (Land Cover)
            entry_c = QgsRasterCalculatorEntry()
            entry_c.ref = "C@1"
            entry_c.raster = lyr_lc
            entry_c.bandNumber = 1
            entries.append(entry_c)

            # 3. Definir a fórmula matemática limpa usando os aliases criados
            formula = "(A@1 + B@1 + C@1) / 3"

            # 4. Configurar o construtor baseado estritamente na documentação do QGIS 3.44
            calculator = QgsRasterCalculator(
                formula,                  # formulaString
                average_raster,              # outputString
                "GTiff",                  # outputFormatString
                lyr_dist.extent(),        # outputExtent
                lyr_dist.width(),         # nOutputWidth
                lyr_dist.height(),        # nOutputHeight
                entries                   # rasterEntries
            )

            # 5. Executar o cálculo matemático
            self.log_text_browser.emit(
                "Executando a media das variaveis...")
            result = calculator.processCalculation()

            # De acordo com a documentação, processCalculation() retorna 0 se for bem-sucedido
            if result != 0:
                self.completed.emit(False, "Erro ao gerar o raster da média!")
                return False
            
            self.log_text_browser.emit(
                "Raster da media gerado com sucesso!")
            # -----------------------------------------------------------------
            # [Etapa 13] Classificar o raster de média em 4 intervalos usando reclassifybytable.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False
            self.log_text_browser.emit(
                "\n[Etapa 13] Classificando o Mapa de Adequabilidade Urbana...")
            self.setProgress(85)

            raster_media_classified = os.path.join(
                            self.temp_folder, "media_raster_classificado.tif")

            tabela_reclass = [  0, 0.25, 1, 
                                0.25, 0.50, 2,
                                0.50, 0.75, 3, 
                                0.75, 1.00, 4]

            # Ao passar 'self' no feedback, o processamento nativo conversa com a tua QgsTask
            processing.run("native:reclassifybytable", {
                'INPUT_RASTER': average_raster,
                'RASTER_BAND': 1,
                'TABLE': tabela_reclass,
                'NO_DATA_VALUE': -9999,
                'RANGE_BOUNDARIES': 2,
                'DATA_TYPE': 0,
                'OUTPUT': raster_media_classified
            }, feedback=process_feedback)

            if not os.path.exists(raster_media_classified):
                self.completed.emit(
                    False, "Erro ao gerar Raster final!")
                return False
            
            self.log_text_browser.emit(
                "Raster de Aptidão urbana gerado com sucesso!")
            # -----------------------------------------------------------------
            # [Etapa Final] Recortar a camada raster da media.
            # -----------------------------------------------------------------
            if self.isCanceled():
                return False

            self.log_text_browser.emit(
                "\n[Etapa Final] Recortando a camada raster da media...")
            self.setProgress(90)

            processing.run("gdal:cliprasterbymasklayer", {
                'INPUT': raster_media_classified,
                'MASK': self.layer_mask,
                'SOURCE_CRS': self.crs_utm,
                'NODATA': -9999,
                'OPTIONS': '',
                'DATA_TYPE': 1,
                'OUTPUT': self.final_raster
            }, feedback=process_feedback)

            if not os.path.exists(self.final_raster):
                self.completed.emit(
                    False, "Erro ao recortar o raster da media!")
                return False

            self.log_text_browser.emit(
                "Raster recortado da media gerado com sucesso!")
            # -----------------------------------------------------------------
            # FIM DO PIPELINE
            # -----------------------------------------------------------------
            self.setProgress(100)
            self.completed.emit(True, self.final_raster)
            return True

        except Exception as e:
            self.completed.emit(False, str(e))
            return False