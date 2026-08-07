mkdir -p /opt/tinyPlatform/{scripts,backend/app/{routers,models,utils},mcp,frontend/{css,js},.github/workflows}
cd /opt/tinyPlatform && touch \
  README.md .gitignore docker-compose.yml \
  scripts/sys_check.sh scripts/get_time.sh \
  backend/app/__init__.py backend/app/main.py \
  backend/app/routers/__init__.py backend/app/routers/tools.py \
  backend/app/models/__init__.py backend/app/models/tool_models.py \
  backend/app/utils/__init__.py backend/app/utils/executor.py \
  backend/requirements.txt backend/Dockerfile backend/.env.example \
  mcp/server.py mcp/requirements.txt mcp/Dockerfile mcp/.env.example \
  frontend/index.html frontend/css/style.css frontend/js/app.js \
  frontend/nginx.conf frontend/Dockerfile \
  .github/workflows/build.yml

tree /opt/tinyPlatform
