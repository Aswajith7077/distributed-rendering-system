from models import RenderJob
from service import minio_service
import os


class BlenderRenderer:
    def process_job(self, job: RenderJob):
        local_blend = f"/tmp/{job.job_id}.blend"
        output_dir = f"render/{job.job_id}"

        os.makedirs(output_dir, exist_ok=True)

        # 1. Download from MinIO
        minio_service.download(job.input_bucket, job.input_object, local_blend)

        # 2. Render frames
        for frame in range(job.start_frame, job.end_frame + 1):
            render_frame(local_blend, output_dir, job, frame)

        # 3. Upload results
        for file in os.listdir(output_dir):
            minio_client.upload(
                job.output_bucket,
                f"{job.job_id}/{file}",
                os.path.join(output_dir, file)
            )

        # 4. Cleanup
        os.remove(local_blend)