import shutil
import os
from pathlib import Path


def create_workspace(job_id: str, template: str = None) -> Path:
    templates_root = Path(os.environ.get("TEMPLATE_DIR", "./templates/base-template-turntable")).parent.resolve()
    if template:
        if ".." in template or "/" in template:
            raise ValueError("Invalid template name")
        template_dir = (templates_root / template).resolve()
        if not str(template_dir).startswith(str(templates_root)):
            raise ValueError("Template path traversal denied")
    else:
        template_dir = templates_root / Path(os.environ.get("TEMPLATE_DIR", "./templates/base-template-turntable")).name
    workspace_dir = Path(os.environ.get("WORKSPACE_DIR", "./workspaces")) / f"job_{job_id}"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    if template_dir.exists():
        for item in template_dir.iterdir():
            dest = workspace_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
    return workspace_dir


def seed_pipeline(workspace: Path) -> Path:
    """Seed the frozen, vetted analysis pipeline into the workspace.

    Universal (not per-template) code, so it's copied for *every* job — the agent
    runs `python -m analysis.run` instead of re-authoring the kinematics each
    time. Copy (not symlink) keeps each job self-contained and stops the agent
    from mutating shared code. See workspace_lib/analysis/README.md.
    """
    seed_dir = Path(os.environ.get("WORKSPACE_LIB", "./workspace_lib")).resolve()
    src = seed_dir / "analysis"
    dest = workspace / "analysis"
    if src.exists():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    return dest


def drop_video(workspace: Path, video_bytes: bytes) -> Path:
    video_path = workspace / "input_video.mp4"
    video_path.write_bytes(video_bytes)
    return video_path


def drop_sidecar(workspace: Path, sidecar: dict) -> Path:
    import json
    sidecar_path = workspace / "sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar, indent=2))
    return sidecar_path


def delete_workspace(job_id: str) -> None:
    workspace_dir = Path(os.environ.get("WORKSPACE_DIR", "./workspaces")) / f"job_{job_id}"
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)