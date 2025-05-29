# Python 3.10 slim 베이스 이미지 사용
FROM python:3.10-slim

# OS 패키지 설치 (konlpy 의존성)
RUN apt-get update && apt-get install -y \
    default-jdk \
    gcc \
    g++ \
    python3-dev \
    build-essential \
    && apt-get clean

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# Flask 기본 포트
EXPOSE 5000

# Flask 앱 실행 (gunicorn 사용, 로깅 옵션 추가)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level", "debug", "--capture-output", "--enable-stdio-inheritance", "app:app"]