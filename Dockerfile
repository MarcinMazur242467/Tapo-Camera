# Use an official Python runtime as a parent image
FROM python:3.13.7-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2. Install uv
COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /uvx /bin/

# 3. Create app directory and user
WORKDIR /app

# 4. Copy dependency files
# Copy the files that define your project and its locked dependencies
COPY pyproject.toml uv.lock ./

# 5. Install dependencies
# This now works because uv.lock is present
RUN uv sync --locked

# 6. Copy the rest of the application code
COPY . .

# 7. Expose the port
EXPOSE 5000

# 8. Set the run command
CMD ["uv", "run", "run.py", "--host", "0.0.0.0", "--port", "5000"]