from .blender import BlenderRenderer
from service import minio_service


blender_renderer = BlenderRenderer(minio_service=minio_service)


__all__ = [
    'blender_renderer'
]