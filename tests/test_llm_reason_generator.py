from __future__ import annotations

import importlib


def test_llm_reason_generator_importable():
    module = importlib.import_module("reason.llm_reason_generator")
    assert hasattr(module, "QwenReasonGenerator")


def test_default_model_path():
    from reason.llm_reason_generator import DEFAULT_LOCAL_LLM_PATH

    assert DEFAULT_LOCAL_LLM_PATH == r"D:\Javatest\pythonweb\movierec\qwen_model"


def test_use_llm_false_returns_template_reason():
    from reason.llm_reason_generator import QwenReasonGenerator

    row = {"template_reason": "这部电影和你的偏好匹配，值得一看。"}
    result = QwenReasonGenerator().generate(row, use_llm=False)
    assert result["final_reason"] == row["template_reason"]
    assert result["llm_reason"] == ""
    assert result["reason_source"] == "template"


def test_missing_model_path_falls_back_to_template(tmp_path):
    from reason.llm_reason_generator import QwenReasonGenerator

    missing = tmp_path / "missing-qwen"
    result = QwenReasonGenerator(missing).generate({"template_reason": "类型匹配你的偏好。"}, use_llm=True)
    assert result["final_reason"]
    assert result["reason_source"] == "template"


def test_existing_path_load_failure_falls_back_to_template(tmp_path):
    from reason.llm_reason_generator import QwenReasonGenerator

    model_dir = tmp_path / "bad-qwen"
    model_dir.mkdir()
    result = QwenReasonGenerator(model_dir).generate({"template_reason": "类型匹配你的偏好。"}, use_llm=True)
    assert result["final_reason"]
    assert result["reason_source"] == "template"


def test_qwen_success_sets_qwen_source(monkeypatch):
    from reason.llm_reason_generator import QwenReasonGenerator

    generator = QwenReasonGenerator()
    monkeypatch.setattr(generator, "load_model", lambda: True)
    monkeypatch.setattr(generator, "_generate_raw", lambda prompt: "推荐理由：这部电影类型贴合你的喜好，评分也比较稳定。")

    result = generator.generate({"template_reason": "类型匹配你的偏好。"}, use_llm=True)
    assert result["llm_reason"] == "这部电影类型贴合你的喜好，评分也比较稳定。"
    assert result["final_reason"] == result["llm_reason"]
    assert result["reason_source"] == "qwen"


def test_invalid_qwen_output_falls_back(monkeypatch):
    from reason.llm_reason_generator import QwenReasonGenerator

    generator = QwenReasonGenerator()
    monkeypatch.setattr(generator, "load_model", lambda: True)
    monkeypatch.setattr(generator, "_generate_raw", lambda prompt: "导演和主演表现很好。")

    result = generator.generate({"template_reason": "类型匹配你的偏好。"}, use_llm=True)
    assert result["final_reason"] == "类型匹配你的偏好。"
    assert result["reason_source"] == "template"


def test_reason_source_values_are_limited():
    from reason.llm_reason_generator import QwenReasonGenerator

    result = QwenReasonGenerator().generate({"template_reason": "类型匹配你的偏好。"}, use_llm=False)
    assert result["reason_source"] in {"qwen", "template"}
