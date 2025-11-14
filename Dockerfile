# Dockerfile
FROM python:3.11-slim

# best practice: create non-root user
ENV APP_HOME=/app
WORKDIR $APP_HOME

# copy only requirements first for cache
COPY requirements.txt .

RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# copy entire repo
COPY . .

# ensure service.py is executable
RUN chmod +x /app/service.py

EXPOSE 8080
CMD ["python", "service.py"]
