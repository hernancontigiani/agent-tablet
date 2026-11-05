# Deliberately not built yet

Each entry is a decision to defer, not an oversight, listed with the **trigger** that should reopen
it. A piece with no consumer is deferred here instead of being designed blind.

What a plan will build in its turn does not belong here: the roadmap is `plans/00-STATUS.md`. This
file is for what was considered and consciously left out.

An entry is:

```
### <What is not built>

Why it is deferred, and what would go wrong if it were built now.

**Trigger:** the concrete situation that reopens it, and the first question to answer then.
```

### A packaged release (`.deb`, PyPI)

Installation is from source (`data/install.sh`) until there is a first stable version: a package is
a promise of upgrades, and every rename in plan 01 would break it. `debian/` and
`scripts/build_deb.sh` are kept and rebranded so they are ready; the original's AUR, PPA and PyPI
publishing were removed.

**Trigger:** the human calls a version stable. First question: which Ubuntu releases the `.deb`
targets, given the Python 3.12 floor.

### A documentation site

The original's VitePress site was removed with the fork; `README.md` is the user guide.

**Trigger:** the README stops fitting on a few screens, or someone outside the human uses the app.
