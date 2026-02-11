# =================================================================
# Computes a buffer around an input GeoJSON geometry.
# Supports Point, LineString, Polygon, and Multi* types.
# =================================================================

import json
import logging
from typing import Any, Tuple

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

PROCESS_METADATA = {
    'version': '1.0.0',
    'id': 'geometry-buffer',
    'title': 'Geometry Buffer',
    'description': (
        'Computes a buffer of a given distance around an input GeoJSON '
        'geometry. Returns the buffered geometry as GeoJSON.'
    ),
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': ['buffer', 'geometry', 'geospatial', 'ogc'],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'Shapely buffer docs',
        'href': 'https://shapely.readthedocs.io/en/stable/reference/shapely.buffer.html',
        'hreflang': 'en-US',
    }],
    'inputs': {
        'geometry': {
            'title': 'Input Geometry',
            'description': 'A GeoJSON geometry object (Point, LineString, Polygon, etc.)',
            'schema': {
                'type': 'object',
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'keywords': ['geometry', 'geojson'],
        },
        'distance': {
            'title': 'Buffer Distance',
            'description': 'Buffer distance in the units of the input CRS (degrees for WGS84)',
            'schema': {
                'type': 'number',
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'keywords': ['distance', 'radius'],
        },
        'resolution': {
            'title': 'Resolution',
            'description': 'Number of segments used to approximate a quarter circle (default: 16)',
            'schema': {
                'type': 'integer',
                'default': 16,
            },
            'minOccurs': 0,
            'maxOccurs': 1,
            'keywords': ['resolution', 'segments'],
        },
    },
    'outputs': {
        'buffered_geometry': {
            'title': 'Buffered Geometry',
            'description': 'The resulting buffered GeoJSON geometry',
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/json',
            },
        },
    },
    'example': {
        'inputs': {
            'geometry': {
                'type': 'Point',
                'coordinates': [0.0, 0.0],
            },
            'distance': 1.0,
            'resolution': 16,
        },
    },
}


class GeometryBufferProcessor(BaseProcessor):
    def __init__(self, processor_def: dict):
        super().__init__(processor_def, PROCESS_METADATA)

    def execute(self, data: dict, outputs=None) -> Tuple[str, Any]:
        """
        :param data: dict with keys 'geometry', 'distance', and optional 'resolution'
        :returns: tuple of (mimetype, result_dict)
        """
        mimetype = 'application/json'

        geometry_input = data.get('geometry')
        if geometry_input is None:
            raise ProcessorExecuteError('Missing required input: geometry')

        distance = data.get('distance')
        if distance is None:
            raise ProcessorExecuteError('Missing required input: distance')

        try:
            distance = float(distance)
        except (TypeError, ValueError):
            raise ProcessorExecuteError('distance must be a number')

        resolution = int(data.get('resolution', 16))

        # --- Convert GeoJSON to Shapely geometry ---
        try:
            from shapely.geometry import shape, mapping
        except ImportError:
            raise ProcessorExecuteError(
                'shapely is required but not installed')

        try:
            geom = shape(geometry_input)
        except Exception as err:
            raise ProcessorExecuteError(
                f'Invalid GeoJSON geometry: {err}')

        LOGGER.info(
            f'Buffering {geom.geom_type} by distance={distance}, '
            f'resolution={resolution}'
        )

        # --- Compute buffer ---
        buffered = geom.buffer(distance, resolution=resolution)

        # --- Build output ---
        result = {
            'type': 'Feature',
            'geometry': mapping(buffered),
            'properties': {
                'input_geometry_type': geom.geom_type,
                'buffer_distance': distance,
                'buffer_resolution': resolution,
                'result_geometry_type': buffered.geom_type,
                'result_area': buffered.area,
            },
        }

        return mimetype, result

    def __repr__(self) -> str:
        return f'<GeometryBufferProcessor> {self.name}'