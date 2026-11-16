# Public demo deployment (Docker Hub + Railway)

For the course assignment "Building and Deploying Your Software Engineering Project's Web
Application". The deployed site shows **only made-up demo courses**, built into the image by
`make_demo_archive.py`. It never holds anyone's real coursework or a Canvas token.

How it fits together:

```
push to main ──> GitHub Actions (.github/workflows/docker.yml)
                   build image ─> smoke test ─> push to Docker Hub
                                                   │
                                Railway pulls <username>/bard-demo:latest and runs it
```

On a pull request, the workflow only builds and smoke-tests the image. It pushes only from `main`.

## One-time setup (one person on the team)

### 1. Docker Hub
1. Sign in at hub.docker.com (a free account is enough).
2. **Account settings → Personal access tokens → Generate new token.** Access: **Read & Write**.
   Copy the token; Docker Hub shows it once.
3. The repository `<username>/bard-demo` is created by the first push. Make sure it is public, so
   Railway can pull it without a login.

### 2. GitHub secrets
In this repo: **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `DOCKERHUB_USERNAME` | your Docker Hub username |
| `DOCKERHUB_TOKEN` | the access token from step 1 (never your password) |

Then **Actions → Docker → Run workflow** on `main`, or merge any PR. The run's summary says
which tags it pushed: `latest` and `sha-<first 7 characters of the commit>`.

### 3. Railway
1. **New Project → Deploy a Docker Image**, image `docker.io/<username>/bard-demo:latest`.
2. **Variables:** add `BARD_WEB_SECRET` = a random string of at least 32 characters
   (for example the output of `openssl rand -hex 32`, or `python -c "import secrets; print(secrets.token_hex(32))"`).
   Do not set `PORT`: Railway sets it, and `bard-web` listens on it.
3. **Settings → Networking → Generate Domain.**
4. Open `https://<your-domain>/<BARD_WEB_SECRET>/`. The root URL without the secret answers 403
   on purpose.
5. To redeploy after a new push, use **Redeploy** in Railway (or turn on automatic image updates
   if your plan offers it).

### Check it works (and what to screenshot for the PDF)
- The course list shows `DEMO-BIO-101` and `DEMO-CS-200`.
- **Core feature:** search for `greenhouse`. The result "Greenhouse lab moved" links to its item.
- Try it in a private browser window, as the assignment asks.

## Run the image on your own computer
```
docker build -t bard-demo .
docker run --rm -p 8080:8080 -e BARD_WEB_SECRET=$(openssl rand -hex 32) bard-demo
```
Then open `http://localhost:8080/<the same secret>/`.

## Rules
- Never copy a real archive (`~/BARD`) or `~/.bard/config.json` into the image. `.dockerignore`
  keeps them out of the build.
- Keep the Railway logs to the team: Flask logs each request path, and the path includes the secret.
- When a feature needs a system package (OCR needs Tesseract, for example), add it to the
  `Dockerfile` in that feature's pull request.
