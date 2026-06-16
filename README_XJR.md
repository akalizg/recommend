# RecipeRecommend 增量修改说明（XJR）

本文档用于补充说明本次在 `D:\PythonWeb\recommend-main` 项目中新增和完善的功能，不替换原有 `README.md`。

## 1. 本次修改概览

本次主要围绕“饭搭子 Taste Twin”社区化推荐功能进行扩展，同时对推荐对话页、菜品详情页、记录页等前端交互做了补充完善。

核心目标：

- 新增饭搭子页面，支持寻找口味相似用户。
- 支持查看饭搭子的公开主页、高分菜谱、避雷菜谱。
- 支持基于双方偏好生成双人菜单。
- 支持饭搭子菜谱收藏、取消收藏、记录查看与记录删除。
- 扩展饭搭子候选池，便于本地验证匹配效果。
- 优化推荐对话页的历史保留、固定滚动对话框和即时反馈补位。
- 修复菜品详情页相似菜谱点击跳转后不刷新详情的问题。

## 2. 新增饭搭子功能

### 2.1 页面与路由

新增前端页面：

- `frontend/src/views/TasteTwin.vue`
- `frontend/src/views/TasteTwinProfile.vue`
- `frontend/src/views/TasteTwinRecords.vue`

新增前端路由：

- `/taste-twin`
- `/taste-twin/:userId`
- `/taste-twin/records`

导航栏新增“饭搭子”入口，用户可以从主导航进入饭搭子页面。

### 2.2 社区发现设置

饭搭子页面支持：

- 查看当前社区发现状态。
- 开启或关闭社区发现。
- 设置匿名吃货代号。
- 手动输入偏好标签。
- 从可滚动下拉面板选择偏好标签。
- 点击“确认”后保存设置，并实时刷新下方饭搭子推荐。

当前逻辑调整为：

- 真实用户默认开启社区发现。
- 初始偏好标签为空。
- 用户手动修改标签后，只有点击“确认”才会保存。
- 保存后后端会重建饭搭子用户索引，前端会重新拉取匹配结果。

### 2.3 饭搭子匹配

饭搭子匹配基于 LightGCN 用户向量和 FAISS 相似度检索实现。

后端启动时加载：

- `data/lightgcn/lightgcn_user_embeddings.npy`
- `data/lightgcn/lightgcn_user_ids.npy`

然后构建 User FAISS Index，用于快速查找口味向量相似的用户。

匹配流程：

1. 当前用户进入饭搭子页面。
2. 后端检查用户是否允许社区发现。
3. 使用当前用户 LightGCN 向量在 FAISS 中检索相似用户。
4. 根据用户反馈和评分记录做轻量重排。
5. 返回 Top 10 饭搭子候选。
6. 前端每次展示 5 个，点击“重新寻找”切换另一组。

### 2.4 候选池扩展

为了便于本地验证饭搭子效果，候选池已从“仅真实登录用户”扩展为：

- 真实登录用户。
- `ratings_clean.csv` 中有评分记录的 Food.com 用户。
- LightGCN 中有用户向量的用户。

同时保留排除规则：

- `taste_twin_demo_%` 演示用户不再参与匹配。
- 已手动关闭社区发现的真实账号绑定用户不参与匹配。

这样既能保持真实用户的社区开关语义，又能利用完整评分数据验证饭搭子匹配效果。

### 2.5 推荐用户卡片

饭搭子页面中的用户卡片展示：

- 匿名代号。
- 口味契合度。
- 共同偏好标签或 Top 偏好标签。
- 本命菜谱。
- 避雷菜谱。
- 查看主页按钮。
- 生成双人菜单按钮。

本命菜谱和避雷菜谱：

- 两个区域宽度一致。
- 每个区域只显示一行。
- 菜品卡片大小一致。
- 每个区域最多展示 3 个菜谱。
- 菜品卡片可点击跳转到对应菜品详情页。

### 2.6 搭子公开主页

点击饭搭子卡片中的“查看主页”进入公开主页。

公开主页展示：

- 饭搭子匿名代号。
- 口味契合度。
- Top 偏好标签。
- Ta 觉得好吃而当前用户还没看过的菜谱。
- 高分评价列表。
- 避雷列表。

高分和避雷列表支持分页：

- 每页最多 12 个。
- 不再无限向下追加卡片。
- 没有数据时展示空状态提示。

### 2.7 一键收藏与取消收藏

搭子主页中的菜品支持：

- 一键收藏。
- 已收藏状态展示。
- 再次点击取消收藏。

后端会同步写入或删除：

- `auth_users.db` 中的 `taste_twin_collections`
- `recommendations.db` 中对应的反馈日志

### 2.8 我的记录页面

新增“我的记录”页面，支持查看：

- 收藏。
- 喜欢。
- 不喜欢。
- 避雷。
- 评分。

记录页功能：

- 按类型筛选。
- 分页查看。
- 点击菜品卡片跳转详情页。
- 记录标签和时间悬浮在菜品图片底部。
- 操作按钮用于取消对应记录，例如取消收藏、取消喜欢、取消评分。
- 操作后同步数据库并刷新当前页。

### 2.9 今日双人菜单

在饭搭子用户卡片中点击“生成双人菜单”，会在当前用户卡片内部展示双人菜单。

双人菜单逻辑：

1. 优先查找当前用户和饭搭子双方都高分评价过的菜谱。
2. 如果没有共同高分菜谱，则根据双方偏好标签、菜品评分、热度等信息生成候选。
3. 后端返回候选集合。
4. 前端每次展示 5 道菜。
5. 点击“换一换”切换下一组 5 道。

双人菜单不会再出现在页面最底部，而是显示在对应饭搭子的卡片内部。

## 3. 后端新增模块

新增独立饭搭子模块：

- `taste_twin/schemas.py`
- `taste_twin/service.py`
- `taste_twin/router.py`
- `taste_twin/user_index.py`

主要职责：

- Pydantic 数据结构定义。
- 饭搭子用户设置读取与保存。
- User FAISS Index 构建与检索。
- 饭搭子匹配。
- 搭子主页数据查询。
- 双人菜单生成。
- 收藏与取消收藏。
- 我的记录查询与删除。

### 3.1 新增接口

新增 API 路由前缀：

```text
/taste-twin
```

主要接口：

```text
GET    /taste-twin/settings/{user_id}
PATCH  /taste-twin/settings/{user_id}
GET    /taste-twin/{user_id}/matches
GET    /taste-twin/{user_id}/profiles/{twin_user_id}
POST   /taste-twin/{user_id}/copy/{movie_id}
GET    /taste-twin/{user_id}/joint-menu/{twin_user_id}
GET    /taste-twin/{user_id}/records
DELETE /taste-twin/{user_id}/records
```

本地演示搭子接口已禁用：

```text
POST /taste-twin/{user_id}/demo-twins
```

调用该接口会返回演示搭子已关闭的提示。

### 3.2 应用生命周期初始化

饭搭子服务在 FastAPI 应用启动阶段初始化。

初始化内容：

- 确保数据库字段存在。
- 加载评分、菜品画像、用户画像。
- 加载 LightGCN 用户向量。
- 构建 User FAISS Index。

这样后续匹配请求可以直接使用内存中的索引，避免每次请求重复加载向量。

## 4. 数据库相关调整

### 4.1 `auth_users.db`

路径：

```text
data/auth_users.db
```

用途：

- 登录账号。
- 社区开关。
- 匿名代号。
- 偏好标签。
- 饭搭子收藏。

新增或使用字段：

```text
is_discoverable
community_alias
preference_tags
```

新增表：

```text
taste_twin_collections
```

当前逻辑：

- 真实用户默认 `is_discoverable = 1`。
- 初始 `preference_tags = ''`。
- `taste_twin_demo_%` 用户已关闭，不参与匹配。

### 4.2 `recommendations.db`

路径：

```text
data/recommendations.db
```

用途：

- 推荐系统用户。
- 评分。
- 推荐日志。
- 反馈日志。
- 用户画像。
- 菜品画像。
- 离线指标。

注意：

`recommendations.db.users` 不是登录账号表，而是推荐算法中的用户实体表。

饭搭子不会直接把其中所有用户都当作真实社区用户，而是结合评分数据和 LightGCN 向量，将有评分、有向量的数据用户纳入候选池，用于本地验证匹配效果。

## 5. 对话推荐页面修改

修改文件：

- `frontend/src/views/Recommend.vue`

### 5.1 对话历史保留

原问题：

- 页面跳转或刷新后，推荐对话历史丢失。

原因：

- 对话状态只存在 Vue 组件内存中。

修改后：

- 使用 `localStorage` 保存最近 10 条对话记录。
- 按用户隔离存储。
- 未登录用户使用 guest 会话。

存储内容包括：

- 对话消息。
- 当前推荐卡片。
- 当前场景模式。
- 食材、目标、时间等筛选条件。
- 喜欢、减少类似等前端即时状态。

该功能只影响前端展示，不会改变后端推荐算法。

### 5.2 固定高度对话框

原问题：

- 对话变多后，整个页面被不断向下撑开。

修改后：

- 对话框固定高度。
- 消息区域内部滚动。
- 输入框固定在对话框底部。
- 对话框后方灰色底板已移除，页面只保留一个独立对话框。

### 5.3 减少类似即时补位

原问题：

- 点击“减少类似”后后端报错。
- 原本卡片应立即替换，但没有补位。

原因：

- 前端提交了 `less_similar`，后端允许的反馈类型是 `not_interested`。

修改后：

- 前端展示仍叫“减少类似”。
- 提交给后端时映射为 `not_interested`。
- 当前卡片会立即移除，并从候选池中补入新的菜品卡片。

## 6. 菜品详情页修改

修改文件：

- `frontend/src/views/MovieDetail.vue`

### 6.1 相似菜谱可跳转详情

相似菜谱卡片复用 `MovieCard`，支持点击跳转：

```text
/recipe/{movieId}
```

### 6.2 同组件路由刷新

原问题：

- 在详情页底部点击相似菜谱时，URL 变化但详情内容可能不刷新。

原因：

- Vue Router 会复用同一个详情组件，`onMounted` 不会再次执行。

修改后：

- 监听 `route.params.movieId`。
- 当 `movieId` 变化时重新加载菜品详情和相似菜谱。

该修改不影响相似菜谱算法，只修复前端路由刷新问题。

## 7. 前端 API 封装

修改文件：

- `frontend/src/api/index.js`

新增饭搭子 API 调用：

```js
getTasteTwinSettings(userId)
updateTasteTwinSettings(userId, payload)
getTasteTwinMatches(userId, limit)
getTasteTwinProfile(userId, twinUserId, highPage, lowPage, pageSize)
copyTasteTwinRecipe(userId, movieId)
getTasteTwinJointMenu(userId, twinUserId, offset)
getTasteTwinRecords(userId, recordType, page, pageSize)
deleteTasteTwinRecord(userId, recordId)
```

## 8. 设计约束说明

本次修改遵循最小侵入原则：

- 未修改多路召回核心逻辑。
- 未修改 XGBoost 排序逻辑。
- 未修改 MMR 重排逻辑。
- 饭搭子功能独立封装在 `taste_twin` 模块。
- 前端新增页面独立维护，通过路由接入。
- 对话推荐页修改仅涉及前端展示状态和反馈类型映射。
- 菜品详情页修改仅涉及前端路由参数变化后的重新加载。

## 9. 使用与验证建议

### 9.1 重启后端

饭搭子用户索引在应用启动时构建，因此修改候选池或社区开关逻辑后，需要重启 FastAPI 后端：

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 9.2 重启或刷新前端

前端修改后建议重新运行：

```powershell
cd frontend
npm.cmd run dev
```

或至少浏览器硬刷新页面。

### 9.3 构建验证

本次修改已使用以下命令验证：

```powershell
npm.cmd run build
```

后端关键 Python 文件也已通过语法检查。

## 10. 当前注意事项

1. 饭搭子候选池已包含 Food.com 评分数据用户，因此本地测试时可看到更多饭搭子。
2. 这些数据用户不一定是系统真实登录账号，但有评分和向量数据，适合验证口味匹配效果。
3. 真实登录用户如果手动关闭社区发现，其绑定的 `recipe_user_id` 不会参与匹配。
4. 偏好标签最多保存 12 个，防止用户卡片展示过长。
5. 对话推荐历史仅保存在当前浏览器本地，不会同步到后端。
