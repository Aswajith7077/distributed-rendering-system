from models import RenderJob
from models import Acknowledgement
import os
import subprocess
import shutil
import logging

log = logging.getLogger(__name__)


class BlenderRenderer:
    def __init__(self, minio_service):
        self.minio = minio_service

    def _get_valid_engine(self, engine: str) -> str:
        """Get valid render engine, fallback to CYCLES if invalid"""
        # List of supported engines in order of preference
        supported_engines = ["CYCLES", "BLENDER_EEVEE_NEXT", "EEVEE", "BLENDER_WORKBENCH"]

        # Normalize engine name
        if engine:
            engine = engine.upper()

        # Check if requested engine is supported
        if engine in supported_engines:
            return engine

        # Fallback to CYCLES for compatibility
        log.warning(f"Engine '{engine}' not supported, falling back to CYCLES")
        return "EEVEE"

    def process_job(self, job: dict):
        import uuid

        job = RenderJob(**job)
        object_name = f"jobs/{job.job_id}/input/scene.blend"

        # Isolate local directory per-task to prevent WinError 32 lock collisions
        # when multiple local workers process frames for the same job.
        task_uuid = uuid.uuid4().hex
        local_dir = f"/tmp/{job.job_id}_{task_uuid}"

        # Use proper path joining for cross-platform compatibility
        local_blend = os.path.join(local_dir, "scene.blend")
        output_dir = os.path.join(local_dir, "output")

        result = None

        os.makedirs(output_dir, exist_ok=True)
        log.info(f"Created local directories: {local_dir}")

        try:
            # 1. Download
            self.minio.download(object_name, local_blend)
            log.info(f"Downloaded file from MinIO: {object_name} to {local_blend}")

            # 2. Render (IMPORTANT FIX)
            self.render_range(local_blend, output_dir, job)
            log.info(f"Rendered frames {job.start_frame} → {job.end_frame}")

            # 3. Upload
            for file_name in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file_name)

                object_name = f"jobs/{job.job_id}/output/{file_name}"

                with open(file_path, "rb") as f:
                    self.minio.upload_file(
                        file_obj=f,
                        object_name=object_name,
                        content_type="image/png",
                    )

            result = {"status": "done", "job_id": job.job_id}

        except Exception as e:
            log.error(f"Error processing job: {e}")
            result = {"status": "failed", "job_id": job.job_id, "error": str(e)}

        finally:
            if os.path.exists(local_dir):
                shutil.rmtree(local_dir)

        return Acknowledgement(**result)

    def render_range(self, local_blend, output_dir, job):
        """
        Render a range of frames using a single Blender process (efficient).
        """

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Use absolute paths (important inside Docker)
        local_blend = os.path.abspath(local_blend)
        output_dir = os.path.abspath(output_dir)

        # Blender output prefix (Blender auto adds frame numbers)
        output_path = os.path.join(output_dir, "frame_")
        log.info(f"Blender output path: {output_path}")

        cmd = [
            "blender",
            "-b",
            local_blend,  # headless mode
            "-noaudio",
            "-E",
            self._get_valid_engine(job.engine),
            "-o",
            output_path,  # output prefix
            "-F",
            "PNG",  # format
            "-s",
            str(job.start_frame),  # start frame
            "-e",
            str(job.end_frame),  # end frame
            "--python-expr",
            """
import bpy
# Set render settings for better compatibility
scene = bpy.context.scene
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '8'

# Add a default camera if none exists
if not bpy.data.objects.get('Camera'):
    # Create camera data
    camera_data = bpy.data.cameras.new(name='Camera')
    camera_object = bpy.data.objects.new('Camera', camera_data)
    
    # Link camera to scene
    bpy.context.collection.objects.link(camera_object)
    
    # Set camera as active camera
    bpy.context.scene.camera = camera_object
    
    # Position camera
    camera_object.location = (7, -7, 5)
    camera_object.rotation_euler = (0.785, 0, 0.785)  # 45 degrees in X and Z

# Ensure scene has proper lighting
if not any(obj.type == 'LIGHT' for obj in bpy.data.objects):
    # Add default light
    bpy.ops.object.light_add(type='SUN', location=(5, 5, 5))
    sun = bpy.context.active_object
    sun.energy = 3.0

print("Added default camera and lighting to scene")
            """,
            "-a",  # render animation
        ]

        # Optional: thread control
        if getattr(job, "threads", None):
            cmd.extend(["-t", str(job.threads)])

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

            log.info(f"Rendered frames {job.start_frame} → {job.end_frame}")

        except subprocess.CalledProcessError as e:
            log.error("Blender render failed")
            log.error(f"STDOUT:\n{e.stdout}")
            log.error(f"STDERR:\n{e.stderr}")

            raise Exception(
                f"Render failed for job {job.job_id} "
                f"frames {job.start_frame}-{job.end_frame}"
            )
