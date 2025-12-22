# 启动指南

## 方法 1: 使用批处理文件（推荐）

### 启动后端
双击运行 `start_backend.bat`
- 后端将在 http://localhost:8000 运行
- 保持这个窗口打开

### 启动前端
双击运行 `start_frontend.bat`（在新的终端窗口）
- 前端将在 http://localhost:5173 运行
- 保持这个窗口打开

### 访问界面
打开浏览器访问: **http://localhost:5173**

---

## 方法 2: 手动启动

### 1. 启动后端
打开终端，运行：
```bash
cd backend
python run.py
```

### 2. 启动前端（新终端窗口）
```bash
cd frontend
npm run dev
```

### 3. 访问界面
打开浏览器访问: **http://localhost:5173**

---

## 检查服务器状态

### 后端检查
访问 http://localhost:8000/ 应该看到：
```json
{"message":"OfferClick API"}
```

### 前端检查
访问 http://localhost:5173/ 应该看到 OfferClick 界面

### API 检查
访问 http://localhost:8000/jobs 应该看到职位列表（JSON 格式）

---

## 常见问题

### 1. 端口被占用
如果 8000 或 5173 端口被占用，需要：
- 关闭占用端口的程序
- 或者修改端口配置

### 2. 依赖未安装
如果看到 "ModuleNotFoundError"：
```bash
cd backend
pip install -r requirements.txt
```

### 3. 前端依赖未安装
```bash
cd frontend
npm install
```

### 4. 看不到职位数据
检查 `../data/daily/good_jobs.csv` 文件是否存在

---

## 使用说明

### 键盘快捷键
- `J` / `K`: 上下导航职位列表
- `Enter`: 选择职位
- `A`: 申请职位
- `S`: 跳过职位
- `Shift + S`: 星标/取消星标

### 界面布局
- **左侧**: 职位队列（可排序、筛选）
- **中间**: 职位详情（公司、JD、技术栈）
- **右侧**: 匹配分析 + 简历工具

