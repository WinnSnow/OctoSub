# 使用官方的 Python 基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
# --no-cache-dir: 不缓存包，减小镜像体积
# -r requirements.txt: 从文件安装
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端所有代码到工作目录
COPY . .

# 暴露后端服务运行的端口
EXPOSE 8001

# 容器启动时运行的命令
CMD ["python", "timestamped_stdout.py", "--", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
