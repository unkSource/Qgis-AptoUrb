from qgis.core import QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem

class Boundingbox:
    def __init__(self, layer_name):
        self.layer_name = layer_name

        layers = QgsProject.instance().mapLayersByName(self.layer_name)
        if not layers:
            raise ValueError(
                f"Layer '{self.layer_name}' não foi encontrada no painel de projeto do QGIS."
            )
        self.layer = layers[0]

    def get_bbox(self):
        
        original_extent = self.layer.extent()

        source_crs = self.layer.crs()
        target_crs = QgsCoordinateReferenceSystem("EPSG:4326")

        coordinate_transformer = QgsCoordinateTransform(
            source_crs, target_crs, QgsProject.instance())
        wgs84_extent = coordinate_transformer.transformBoundingBox(original_extent)

        bbox_coordinates = {
            'west': wgs84_extent.xMinimum(),
            'east': wgs84_extent.xMaximum(),
            'south': wgs84_extent.yMinimum(),
            'north': wgs84_extent.yMaximum()
        }

        return bbox_coordinates