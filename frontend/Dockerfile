# 使用 Node.js 官方镜像作为基础
FROM node:22-alpine

# 设置工作目录
WORKDIR /app

# 复制 package.json 和 package-lock.json (或 npm-shrinkwrap.json)
COPY package*.json ./

# 安装项目依赖
RUN npm install

# 复制项目所有文件
COPY . .

# 暴露前端开发服务器运行的端口
EXPOSE 5172

# 容器启动时运行的命令
CMD ["npm", "start"]
