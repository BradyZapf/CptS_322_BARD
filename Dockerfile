# Public demo of the BARD web page, for the deploy assignment (Docker Hub + Railway).
#
# It shows ONLY a made-up demo archive, built below by deploy/make_demo_archive.py. Never
# copy a real archive (~/BARD) or a Canvas token into this image: mission rules 2 and 7.
#
# Build and run locally:
#   docker build -t bard-demo .
#   docker run --rm -p 8080:8080 -e BARD_WEB_SECRET=<32+ characters> bard-demo
#   then open http://localhost:8080/<the same secret>/

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Only what the package needs: the source, not the tests, docs or .git.
COPY pyproject.toml ./
COPY code/backend/src ./code/backend/src
COPY code/frontend/src ./code/frontend/src
RUN pip install .

# Run as an ordinary user, not root.
RUN useradd --create-home --uid 10001 bard
USER bard

# The archive bard-web shows (User reads BARD_HOME), and the container settings
# bard-web reads. BARD_WEB_SECRET is NOT set here: it is a secret, so the platform
# (Railway) supplies it at run time, and bard-web refuses to start without it.
ENV BARD_HOME=/home/bard/demo-archive \
    BARD_WEB_HOST=0.0.0.0 \
    PORT=8080

COPY --chown=bard deploy/make_demo_archive.py ./deploy/make_demo_archive.py
RUN python deploy/make_demo_archive.py "$BARD_HOME"

EXPOSE 8080
CMD ["bard-web"]
