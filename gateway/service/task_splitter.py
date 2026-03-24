from models import TaskModel
from service import redis_service


def split_and_dispatch_task(filename: str, config: dict):
    """
    Splits the rendering work into individual frame tasks based on configuration.
    """
    total_frames = config.get("frames", 1)

    base_task_data = {
        "filename": filename,
        "device": config.get("device", "cpu"),
        "task_type": config.get("task_type", "blender"),
        "render_engine": config.get("render_engine", "cycles"),
        "x": config.get("x", 0),
        "y": config.get("y", 0),
        "width": config.get("width", 1920),
        "height": config.get("height", 1080),
    }

    for frame_num in range(1, total_frames + 1):
        task_data = base_task_data.copy()
        task_data["frames"] = (
            1  # Assuming spatial split isn't explicitly defined here, just 1 frame at a time
        )

        task = TaskModel(**task_data)

        # Publish to Redis using the existing redis_service
        # Mode='json' ensures it serializes UUIDs and Enums properly
        redis_service.add_job(
            payload=task.model_dump(mode="json"), job_type=task.task_type.value
        )
