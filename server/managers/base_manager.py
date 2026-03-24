import json
import os
import shutil
from abc import ABC, abstractmethod


class BaseManager(ABC):
    def __init__(self, workflow_path: str = "workflow.json"):
        self.workflow_path = workflow_path
        self.__load_workflow()

    def __load_workflow(self) -> None:
        self.workflow = None
        with open(self.workflow_path, "r") as f:
            self.workflow = json.load(f)


    def _clean_tiles_dir(self, tiles_dir: str) -> None:
        if os.path.exists(tiles_dir):
            shutil.rmtree(tiles_dir)

    @abstractmethod
    def run_render(
        self,
        workers_override: int | None = None,
        rows_override: int | None = None,
        cols_override: int | None = None,
        verbose: bool = True,
        on_job_start=None,
        on_tile_complete=None,
    ) -> dict:
        pass