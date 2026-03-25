from models import RenderJob
import os
import subprocess
import shutil
import logging

log = logging.getLogger(__name__)


class BlenderRenderer:
    def __init__(self, minio_service):
        self.minio = minio_service

    def process_job(self, job: RenderJob):
        object_name = f"jobs/{job.job_id}/input/scene.blend"
        local_dir = f"/tmp/{job.job_id}"
        local_blend = os.path.join(local_dir, "scene.blend")
        output_dir = os.path.join(local_dir, "output")

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

        finally:
            if os.path.exists(local_dir):
                shutil.rmtree(local_dir)

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
            job.engine if job.engine else "CYCLES",
            "-o",
            output_path,  # output prefix
            "-F",
            "PNG",  # format
            "-s",
            str(job.start_frame),  # start frame
            "-e",
            str(job.end_frame),  # end frame
            "-a",  # render animation
        ]

        # Optional: thread control
        if getattr(job, "threads", None):
            cmd.extend(["-t", str(job.threads)])

        try:
            result = subprocess.run(
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
