# MMR_离线评估_消融实验阶段运行报告

## 本阶段完成内容

本阶段在 XGBoost Top50 精排结果之后，完成：

```text
标准 MMR 多样性重排
离线指标评估
消融实验分析
统一运行脚本
测试脚本
说明文档
```

新增脚本：

```text
rank/mmr_rerank.py
evaluate/offline_metrics.py
evaluate/ablation_eval.py
scripts/run_mmr_eval_stage.py
```

新增测试：

```text
tests/test_mmr_rerank.py
tests/test_offline_metrics.py
tests/test_ablation_eval.py
```

## 输出文件

```text
data/rank/ranked_top10_mmr.csv
data/eval/offline_metrics.csv
data/eval/eval_summary.json
data/eval/ablation_metrics.csv
data/eval/ablation_summary.md
```

## 运行命令

```bash
python scripts/run_mmr_eval_stage.py
```

本次运行成功完成：

```text
MMR rerank XGBoost Top50
Evaluate offline metrics
Build ablation evaluation
```

## ranked_top10_mmr.csv 行数

```text
ranked_top10_mmr.csv: 6100
user count: 610
average recommendations per user: 10.0000
average diversity score during MMR output: 0.909618
```

## offline_metrics.csv 指标表

```text
model_name           k   precision  recall    ndcg      hit_rate  coverage  diversity
ALS                  5   0.001105   0.005525  0.003952  0.005525  0.034285  0.736658
ALS                  10  0.000552   0.005525  0.003952  0.005525  0.053685  0.755697
ALS                  20  0.000691   0.013812  0.006017  0.013812  0.081913  0.771980
ALS                  50  0.001105   0.055249  0.014202  0.055249  0.142579  0.800849
ItemCF               5   0.009917   0.049587  0.029960  0.049587  0.036748  0.767696
ItemCF               10  0.008540   0.085399  0.041365  0.085399  0.062205  0.785532
ItemCF               20  0.008815   0.176309  0.063964  0.176309  0.111271  0.800804
ItemCF               50  0.004959   0.247934  0.077889  0.247934  0.224902  0.813781
ALS+ItemCF_Merged    5   0.008264   0.041322  0.029986  0.041322  0.040751  0.732485
ALS+ItemCF_Merged    10  0.004132   0.041322  0.029986  0.041322  0.058510  0.763425
ALS+ItemCF_Merged    20  0.002479   0.049587  0.032003  0.049587  0.085814  0.776808
ALS+ItemCF_Merged    50  0.001102   0.055096  0.033207  0.055096  0.148532  0.800919
XGBoost_Top50        5   0.000000   0.000000  0.000000  0.000000  0.024225  0.656052
XGBoost_Top50        10  0.000275   0.002755  0.000918  0.002755  0.038493  0.695954
XGBoost_Top50        20  0.000413   0.008264  0.002269  0.008264  0.065798  0.746663
XGBoost_Top50        50  0.002259   0.112948  0.022551  0.112948  0.155204  0.792778
XGBoost_MMR_Top10    5   0.001653   0.008264  0.003509  0.008264  0.029255  0.973715
XGBoost_MMR_Top10    10  0.001377   0.013774  0.005134  0.013774  0.047526  0.918096
XGBoost_MMR_Top10    20  0.000689   0.013774  0.005134  0.013774  0.047526  0.918096
XGBoost_MMR_Top10    50  0.000275   0.013774  0.005134  0.013774  0.047526  0.918096
```

## ablation_metrics.csv 指标表

```text
variant              precision  recall    ndcg      hit_rate  coverage  diversity  main_observation
ALS                  0.000552   0.005525  0.003952  0.005525  0.053685  0.755697  ALS single-channel recall baseline.
ItemCF               0.008540   0.085399  0.041365  0.085399  0.062205  0.785532  ItemCF single-channel recall baseline.
ALS+ItemCF_Merged    0.004132   0.041322  0.029986  0.041322  0.058510  0.763425  Compared with ALS, merged recall improves Recall@10 by +0.035797.
XGBoost_Top50        0.000275   0.002755  0.000918  0.002755  0.038493  0.695954  Compared with merged recall, XGBoost does not improve Precision/NDCG at K=10.
XGBoost_MMR_Top10    0.001377   0.013774  0.005134  0.013774  0.047526  0.918096  Compared with XGBoost Top50, MMR improves Diversity@10 by +0.222142.
```

## XGBoost_Top50 与 XGBoost_MMR_Top10 对比

@10 对比：

```text
XGBoost_Top50 Precision@10: 0.000275
XGBoost_MMR_Top10 Precision@10: 0.001377

XGBoost_Top50 Recall@10: 0.002755
XGBoost_MMR_Top10 Recall@10: 0.013774

XGBoost_Top50 NDCG@10: 0.000918
XGBoost_MMR_Top10 NDCG@10: 0.005134

XGBoost_Top50 Diversity@10: 0.695954
XGBoost_MMR_Top10 Diversity@10: 0.918096
```

本次 MMR 相比 XGBoost Top50 提升了 Diversity@10，同时 Precision、Recall、NDCG 也略有提升。但由于测试集正样本稀少，这个相关性提升应谨慎解读。

## MMR 对 Diversity 的影响

```text
Diversity@10 提升: +0.222142
```

结论：标准 MMR 基于电影类型相似度显著提升了推荐列表多样性，符合本阶段目标。

## 测试结果

已执行：

```bash
pytest tests/test_mmr_rerank.py
pytest tests/test_offline_metrics.py
pytest tests/test_ablation_eval.py
```

结果：

```text
tests/test_mmr_rerank.py: 2 passed
tests/test_offline_metrics.py: 2 passed
tests/test_ablation_eval.py: 2 passed
```

pytest 中有 `pytest_asyncio` 默认配置的弃用提醒，不影响本阶段测试结果。

## 在线链路说明

本阶段没有修改：

```text
FastAPI 推荐接口
Vue 前端
在线召回服务
在线排序服务
现有 FeaturePipeline
现有线上模型文件
```

所有新增产物均为离线旁路产物。

## 长尾说明

本阶段没有引入：

```text
long_tail_score
novelty_score
is_long_tail_movie
LongTailRatio
长尾推荐逻辑
```

当前主题仍然是标准电影个性化推荐系统中的多样性重排和离线评估。

## 下一步建议

下一阶段可以做：

```text
1. 推荐理由生成：基于 genres、tags、recall_source_count、rank_score 生成可解释文本。
2. 前端评估页面：展示 Precision/Recall/NDCG/Diversity 对比表和 Top10 推荐结果。
3. MMR 参数扫描：比较 lambda_rel = 0.5 / 0.6 / 0.7 / 0.8 的相关性与多样性权衡。
4. 改进 XGBoost 排序训练：优化负采样、增加交叉特征、调参后重新评估。
```
