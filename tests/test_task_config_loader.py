from finbound.tasks.config_loader import load_task_config


def test_load_task_config(tmp_path):
    yaml_text = """
task: f1
split: dev
limit: 5
extra_field: value
"""
    cfg_path = tmp_path / "task.yaml"
    cfg_path.write_text(yaml_text)
    cfg = load_task_config(cfg_path)
    assert cfg.task == "f1"
    assert cfg.split == "dev"
    assert cfg.limit == 5
    assert cfg.extra["extra_field"] == "value"
