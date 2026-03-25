from models.task import RenderJob
from service import redis_service


async def split_and_dispatch_task(job_id: str, filename: str, config: dict, object_name: str):
    """
    Splits the rendering work into individual frame tasks based on configuration.
    """
    frame_start = config.get("frame_start", 1)
    frame_end = config.get("frame_end", 1)
    total_frames = max(1, frame_end - frame_start + 1)
    output_type = config.get("output_type", "video")

    # Initialize the parent job in Redis
    await redis_service.initialize_job(
        job_id=job_id,
        config=config,
        total_frames=total_frames
    )

    base_task_data = {
        "job_id": job_id,
        "input_bucket": "blender-files",
        "input_object": object_name,
        "output_bucket": "blender-files",
        "output_type": output_type,
        "engine": config.get("blender_engine", "CYCLES"),
        "resolution_x": config.get("image_width", 1920),
        "resolution_y": config.get("image_height", 1080),
        "samples": config.get("blender_samples", 128),
    }

    for frame_num in range(frame_start, frame_end + 1):
        task_data = base_task_data.copy()
        task_data["start_frame"] = frame_num
        task_data["end_frame"] = frame_num

        task = RenderJob(**task_data)

        # Dispatch the individual task
        await redis_service.add_task(
            job_id=job_id,
            task_data=task.model_dump(mode="json")
        )

