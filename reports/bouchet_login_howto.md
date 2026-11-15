# Bouchet — How to Actually Log In (day-to-day)

*Companion to `reports/yale_cluster_request.md` (which covers getting the account in the first place).
This doc covers the mechanics of connecting once the account exists. Keep it updated as the setup evolves —
future Claude sessions should be able to SSH in from this alone.*

- **NetID:** `ak2876`
- **Account status:** approved (as of 2026-09-28)

## 0. HARD RULE: everything lives under `pi_btk22` project space — no exceptions

**User directive, 2026-09-28: ALL work must live under
`/nfs/roberts/project/pi_btk22/ak2876/` — nothing is ever set up under the home directory
(`/nfs/roberts/home/ak2876`), full stop.** This includes the repo, the Python venv, the `uv`
package cache, and the `uv`/`uvx` binaries themselves (reinstalled via
`PYTHONUSERBASE=/nfs/roberts/project/pi_btk22/ak2876/.local`, not plain `pip install --user`).

Why: home is `drwx------` (mode 700, `ak2876:ak2876`) — **private to this one account, invisible
to Kelly and the rest of the lab.** `/nfs/roberts/project/pi_btk22/` is `drwxr-s---`
(`root:pi_btk22`, group-readable) and the `ak2876` subdir under it is `drwxr-sr-x` — i.e. explicitly
shared/visible to Kelly's PI group, which is the entire point of "working under his account."
Verified via `stat -c "%A %U:%G %n"` on 2026-09-28.

This holds even though project storage is tight (89% of quota, 81% of file-count limit, shared
group-wide — see §3) — that tradeoff was raised and the user overrode it explicitly. Do not
default back to home for convenience or quota-avoidance reasons.

## 1. VPN (required off Yale network)

Bouchet's hostname doesn't resolve at all off-campus — confirmed 2026-09-28 (`ssh: Could not resolve
hostname bouchet.ycrc.yale.edu`). You need Yale VPN connected first unless you're on Yale wifi/ethernet.

- Client: **Cisco Secure Client** (rebranded AnyConnect), already installed at
  `/Applications/Cisco/Cisco Secure Client.app`. CLI binary also exists at
  `/opt/cisco/secureclient/bin/vpn` but connecting requires NetID password + Duo push — do this
  yourself via the GUI app, not something to script/automate.
- VPN profile/server: `access.yale.edu`
- Flow: open the app → connect to `access.yale.edu` → NetID + password → approve Duo push on phone.

## 2. SSH — two paths, use the browser one for now

**Raw `ssh` from a terminal (`ssh ak2876@bouchet.ycrc.yale.edu`) is NOT reliably working yet.**
Confirmed 2026-09-28: the local key (`~/.ssh/id_ed25519`, fingerprint
`SHA256:Qg1CruC+ONrh2LNG0z2hVbMcsU8EEi9pU7ziDEX3S0g`) IS correctly uploaded and on file at
https://sshkeys.ycrc.yale.edu/ (verified by comparing fingerprints — matches exactly). But direct SSH
still gets `Permission denied (keyboard-interactive)`. Root cause: Bouchet requires **key + Duo**
two-factor for external SSH; pubkey gets a "partial success" and the connection then needs an
interactive Duo prompt (push notification / passcode selection), which a non-interactive client
(`BatchMode=yes`, or a scripted call) can't satisfy. This needs a real interactive terminal session
where you personally approve the Duo push — not something to automate. If you want this fixed for
convenience (so scripted rsync/git from your laptop works), look at SSH `ControlMaster`/multiplexing
so Duo only fires once per session — not done yet.

**Working path: Open OnDemand's browser shell.** This authenticates via your existing Yale CAS/SSO
browser session (no separate SSH key/Duo dance per command):
1. https://ood-bouchet.ycrc.yale.edu → log in with NetID (Duo once, browser-based)
2. Top menu → **Bouchet Shell Access** → opens a full shell on `login1.bouchet.ycrc.yale.edu` in a
   new tab, already authenticated as `ak2876`.

This is what was used to do the initial setup below (driven via Playwright browser automation).

## 3. First-login sanity checks — real values, confirmed 2026-09-28

```
groups            → ak2876 pi_btk22 pi_xz532        # pi_btk22 = Kelly's group; pi_xz532 = unrelated (old coursework)
mydirectories     → Home:     /nfs/roberts/home/ak2876
                     pi_btk22 project: /nfs/roberts/project/pi_btk22/ak2876
                     pi_btk22 scratch: /nfs/roberts/scratch/pi_btk22/ak2876
getquota          → home:    12 / 125 GiB used   (plenty of room)
                     pi_btk22 project: 3664 / 4096 GiB (89% — GROUP-WIDE, other lab members' usage;
                       81% of file-count limit too — mind this, don't dump huge file counts there)
                     pi_btk22 scratch: 4927 / 10240 GiB (purges files >30 days old — don't use for
                       anything we need to keep)
```
**Storage plan (superseded 2026-09-28, see §0): everything goes under `pi_btk22` project space,
never home — this is a hard user directive, not a quota-driven default.** The 89%/81% tightness is
real and still worth watching (don't leave giant scratch-able junk there), but it does not override
the rule. Original path was briefly `/nfs/roberts/home/ak2876/thesis-polymarket` on first setup —
corrected same day, see status log.

## 4. Environment setup — corrected 2026-09-28, all paths under project space

```bash
module load miniconda          # gives Python 3.12.8 + pip

# uv itself must be rooted under project space too — NOT plain `pip install --user`
# (that would land in ~/.local, i.e. home). Use PYTHONUSERBASE to redirect it:
mkdir -p /nfs/roberts/project/pi_btk22/ak2876/.local
PYTHONUSERBASE=/nfs/roberts/project/pi_btk22/ak2876/.local pip install --user -q uv
export PATH=/nfs/roberts/project/pi_btk22/ak2876/.local/bin:$PATH

# uv's package cache also needs to live under project (set this in ~/.bashrc or before every session)
export UV_CACHE_DIR=/nfs/roberts/project/pi_btk22/ak2876/.cache/uv

git clone https://github.com/avikabra/polymarket-hawkes.git \
  /nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket   # public repo, no auth needed
cd /nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket
uv sync   # creates .venv inside this same project-space directory
```
Note: `Python/3.12.3-GCCcore-13.3.0` module also exists and is the "system" default, but `module load
miniconda` is simpler (bundles pip) and is what was actually used. `uv sync` satisfies
`requires-python = ">=3.11"`; the `torch<2.3` constraint in `[tool.uv] constraint-dependencies` (set
for Intel Mac compatibility) still applies here — standard Linux PyPI torch<2.3 wheels bundle CUDA
support by default, so this should NOT block GPU use, but verify with `torch.cuda.is_available()`
after sync completes (not yet verified as of this writing).

**Set `UV_CACHE_DIR` and `PATH` every session** (add to `~/.bashrc` on Bouchet, or source a small
`env.sh` at the top of every `.sbatch` script) — without it, a fresh shell's `uv`/`pip` silently
fall back to caching under home again.

Required env vars (put in `.env` on Bouchet, not shell history):
- `GOOGLE_APPLICATION_CREDENTIALS` — path to GCP service account JSON (for GDELT/BigQuery scripts)
- `OPENWEIGHT_LLM_API_KEY` — only needed for script 09 `--openweight` once a vLLM/TGI server is up

## 5. Slurm basics

```bash
sbatch my_job.sh
squeue --me
sacct -j <jobid>
```
Partitions: `day` (default, ≤1h), `devel` (interactive), `week` (≤7d), `gpu`, `mpi`.
Use `--account=<kelly_group>` (secondary group) — find the exact group name via `groups` above.

No `.sbatch` scripts exist in this repo yet — see `reports/bouchet_deferred_compute.md` for which
scripts (07, 09, 11) need GPU sbatch jobs; those need to be written.

## Status log
- 2026-09-28: Account confirmed active. Off-VPN SSH attempt failed (DNS unresolved, expected — no VPN
  connected). Cisco Secure Client confirmed installed. Waiting on user to connect VPN + approve Duo.
- 2026-09-28: VPN connected, Bouchet OnDemand browser shell working. Initial setup (repo clone, `uv`
  install, `uv sync`) done under home directory (`~/thesis-polymarket`) as a quota-avoidance default.
- 2026-09-28: **User caught this** — home is private (mode 700), invisible to Kelly's group, which
  defeats the point of working under his PI account. Corrected: moved the in-progress repo (incl.
  partial `.venv` with torch already installed) and the `uv` cache (incl. the already-downloaded
  torch wheel — 720MB/15min was the single slowest step so far, not worth repeating) via
  `rsync -a --remove-source-files` from home to `/nfs/roberts/project/pi_btk22/ak2876/`. Reinstalled
  `uv` itself rooted under project via `PYTHONUSERBASE` (not moved — cheap to just reinstall).
- 2026-09-28: **Move + cleanup verified complete.** One file (`script07_data.zip`, the uploaded
  input data for script 07) was missed by the first repo `rsync` — it finished uploading at 18:36,
  after that rsync had already taken its file listing at 18:18 — caught by an explicit
  `find ~/thesis-polymarket -type f` sweep afterward and moved separately. Final state, verified by
  direct `ls`/`stat`/size comparison:
  - Home: zero session-added content remains (`~/thesis-polymarket` and `~/.cache/uv` both fully
    removed). Only pre-existing material is left (`.conda`, `.jupyter`, `prob5_cnn.ipynb`, an old
    `torch`/`torchvision` install under `~/.local` dated Feb 15 2026 — all predate this session and
    were explicitly left alone; confirmed via `stat` timestamps before touching anything near them).
  - Project (`/nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket`): all files present, group-owned
    by `pi_btk22` (`drwxr-sr-x`), `script07_data.zip` byte-identical to the original (488,351,276
    bytes). Total added to project quota: ~9.35GB (2.4G repo+venv, 6.9G `uv` cache, 50M `uv` tool) —
    against the 4TB group quota this is a negligible bump (89.45%→~89.68%), not a real risk.
  - `uv sync` was killed mid-install when the move started (safe — no completed venv existed yet) and
    has NOT been re-run from the new location yet. Next step: re-run `uv sync` from
    `/nfs/roberts/project/pi_btk22/ak2876/thesis-polymarket` with `UV_CACHE_DIR` set (per §4) — should
    be fast since it reuses the moved cache instead of re-downloading torch.
