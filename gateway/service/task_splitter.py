from models import RenderJob
from service import redis_service


def split_and_dispatch_task(filename: str, config: dict):
    """
    Splits the rendering work into individual frame tasks based on configuration.
    """
    total_frames = config.get("frames", 1)

    base_task_data = {
        "input_bucket": "uploads",
        "input_object": filename,
        "output_bucket": "renders",
        "engine": config.get("render_engine", "CYCLES"),
        "resolution_x": config.get("width", 1920),
        "resolution_y": config.get("height", 1080),
        "samples": config.get("samples", 128),
    }

    for frame_num in range(1, total_frames + 1):
        task_data = base_task_data.copy()
        task_data["start_frame"] = frame_num
        task_data["end_frame"] = frame_num

        task = RenderJob(**task_data)

        # Publish to Redis using the existing redis_service
        # Mode='json' ensures it serializes UUIDs and Enums properly
        redis_service.add_job(
            payload=task.model_dump(mode="json"), job_type=task.engine.value
        )
