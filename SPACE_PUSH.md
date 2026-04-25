# Pushing this Space to Hugging Face (`hf` remote)

Hugging Face **rejects normal Git blobs** for PNG and other binaries on the Hub. You must use **Git Xet** so those files go through Xet storage.

## One-time setup (Linux / macOS)

1. Install **Git LFS** if you do not have it: [git-lfs.com](https://git-lfs.com/)

2. Install **Git Xet** (pick one):

   **Install script (Linux / macOS amd64 or aarch64):**

   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/huggingface/xet-core/refs/heads/main/git_xet/install.sh | sh
   ```

   **Homebrew (macOS):**

   ```bash
   brew install git-xet
   git xet install
   ```

3. Register the filter in **this repo** (run inside the project root):

   ```bash
   cd /path/to/openenv-email-triage
   git xet install
   ```

4. Confirm:

   ```bash
   git xet --version
   ```

## Push to the Space

```bash
git push hf main
```

Use your real branch name if it is not `main`.

## If you still see Xet errors

- Upgrade: `pip install -U "huggingface_hub>=0.32"` (pulls in `hf_xet` for Python workflows).
- Docs: [Using Xet Storage (Git)](https://huggingface.co/docs/hub/xet/using-xet-storage#git)

## Note on duplicate `Plots/`

The repo keeps training images under **`plots/`** (lowercase) only. The old **`Plots/`** folder was removed to avoid two copies of the same PNGs.
