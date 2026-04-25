# Pushing this Space to Hugging Face (`hf` remote)

Hugging Face **rejects normal Git blobs** for PNGs in many Space repos unless they go through **Xet** or you **do not ship those binaries** in the Git pack you push.

You have **two** workable paths.

---

## Option A — Keep PNGs in the Space repo (use Git Xet)

Official fix: install **Git Xet** so PNGs upload through Xet storage.

1. Install **Git LFS**: [git-lfs.com](https://git-lfs.com/)
2. Install **Git Xet** (Linux / macOS):

   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/huggingface/xet-core/refs/heads/main/git_xet/install.sh | sh
   ```

   Or Homebrew: `brew install git-xet && git xet install`

3. In **this repo**:

   ```bash
   cd /path/to/openenv-email-triage
   git xet install
   git xet --version
   ```

4. Push:

   ```bash
   git push hf main
   ```

Docs: [Using Xet Storage (Git)](https://huggingface.co/docs/hub/xet/using-xet-storage#git)

---

## Option B — No Xet: push code only, images stay on GitHub (recommended if A is blocked)

Your README now uses **`raw.githubusercontent.com/.../main/plots/`** and **`.../main/proofs/`** so the Space README can show images **without** storing PNGs in the Space Git repo.

1. **Push GitHub first** (so those raw URLs return 200):

   ```bash
   git push origin main
   ```

2. **Force-push a lite tree** to the Space (drops `plots/` and `proofs/` from the pack you send to `hf`):

   ```bash
   chmod +x scripts/push_hf_lite.sh
   ./scripts/push_hf_lite.sh
   ```

   Non-interactive: `./scripts/push_hf_lite.sh --yes`

This creates a **new single-commit history** on `hf main` (force). Your **GitHub** repo keeps the full history including PNGs for judges and for `raw.githubusercontent.com`.

---

## Note on duplicate `Plots/`

Only **`plots/`** (lowercase) is used. **`Plots/`** was removed; **`Plots/`** is in `.gitignore` so it is not re-added by mistake.
