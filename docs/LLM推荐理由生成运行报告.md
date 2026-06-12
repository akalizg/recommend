# LLM 推荐理由生成运行报告

本阶段使用本地 Qwen 模型生成推荐理由。如果 Qwen 加载失败，系统自动回退模板推荐理由。

本阶段不调用 OpenAI，不调用外部在线 API，也不联网下载模型。

## 配置

本地 Qwen 模型路径：

```text
D:\Javatest\pythonweb\movierec\qwen_model
```

运行命令：

```bash
python scripts/run_reason_generation.py --use-llm true --model-path D:\Javatest\pythonweb\movierec\qwen_model
```

输出文件：

```text
data/final/recommendations_with_reasons.csv
```

## 运行报告字段

脚本运行时会打印以下信息：

```text
是否启用 Qwen
模型路径是否存在
模型是否加载成功
是否使用 GPU / CPU
失败原因
是否回退模板
生成总行数
reason_source 分布
推荐理由示例 10 条
```

## 当前运行结果

执行时间：2026-06-11

执行命令：

```bash
.\.venv\Scripts\python.exe scripts\run_reason_generation.py --use-llm true --model-path D:\Javatest\pythonweb\movierec\qwen_model
```

运行结果：

```text
是否启用 Qwen: 是
模型路径是否存在: 是
模型是否加载成功: 否
使用设备: unknown
失败原因: transformers is unavailable: No module named 'transformers'
是否回退模板: 是
生成总行数: 6100
reason_source 分布: {'template': 6100}
```

说明：本地 Qwen 模型路径已成功识别，目录中存在 `config.json`、`tokenizer.json`、`model.safetensors` 等模型文件。当前虚拟环境尚未安装 `transformers`，因此本次运行按设计自动回退到模板推荐理由，流程未中断。

推荐理由示例 10 条：

```text
1. King of Hearts (1966): 这部电影包含你常看的Comedy元素，和你的偏好比较匹配，整体评分也很高。
2. Connections (1978): 这部电影属于Documentary类型，适合作为新的观影选择，整体评分也很高。
3. Nasu: Summer in Andalusia (2003): 这部电影属于Animation类型，适合作为新的观影选择，整体评分也很高。
4. Raiders of the Lost Ark: The Adaptation (1989): 这部电影包含你常看的Action元素，和你的偏好比较匹配，整体评分也很高。
5. Jetée, La (1962): 这部电影属于Romance类型，适合作为新的观影选择，整体评分也很高。
6. Cosmos: 这部电影和你的历史偏好有一定匹配，值得一看，整体评分也很高。
7. Neon Genesis Evangelion: The End of Evangelion (1997): 这部电影包含你常看的Action元素，和你的偏好比较匹配，整体评分也很高。
8. The Big Bus (1976): 这部电影包含你常看的Action元素，和你的偏好比较匹配，整体评分也很高。
9. Three Billboards Outside Ebbing, Missouri (2017): 这部电影包含你常看的Drama元素，和你的偏好比较匹配，整体评分也很高。
10. My Sassy Girl (2001): 这部电影包含你常看的Comedy元素，和你的偏好比较匹配，整体评分也很高。
```

## 测试结果

已执行：

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_template_reason_generator.py
.\.venv\Scripts\python.exe -m pytest tests/test_llm_reason_generator.py
.\.venv\Scripts\python.exe -m pytest tests/test_generate_reasons.py
```

测试结果：

```text
tests/test_template_reason_generator.py: 2 passed
tests/test_llm_reason_generator.py: 8 passed
tests/test_generate_reasons.py: 2 passed
```
