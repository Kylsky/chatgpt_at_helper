# 使用ARM兼容的Python基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

RUN apt-get update && apt-get install -y --fix-missing \
    wget \
    gnupg \
    curl \
    unzip \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置Chrome路径环境变量
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMIUM_PATH=/usr/bin/chromium

# 复制requirements.txt
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制turnstilePatch扩展目录（如果存在的话）
COPY plugins/turnstilePatch /app/plugins/turnstilePatch/
# 复制应用代码
COPY app.py .
COPY pages .

# 修改app.py中的Chrome路径
RUN sed -i 's|/user/bin/google-chrome|/usr/bin/chromium|g' app.py

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 运行应用
CMD ["python", "app.py"]