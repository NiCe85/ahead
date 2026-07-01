# Use official lightweight Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy packaging configuration and docs
COPY pyproject.toml README.md ./

# Copy the source code
COPY src/ ./src/

# Install the package and its dependencies
RUN pip install --no-cache-dir .

# Expose port (useful if running MCP over streamable-HTTP)
EXPOSE 8000

# Set environment defaults
ENV PYTHONUNBUFFERED=1

# Run the MCP server over stdio by default
CMD ["python", "-m", "src.mcp_server"]
