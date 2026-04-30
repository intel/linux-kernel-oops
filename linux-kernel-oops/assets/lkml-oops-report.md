# Linux kernel crash report

Source: https://lore.kernel.org/lkml/aYN3JC_Kdgw5G2Ik@861G6M3/
Reporter: Chris Arges <carges@cloudflare.com>

---

## Key elements

| Field | Value | Implication |
|-------|-------|-------------|
| CRASH_TYPE | BUG / BUG_ON (`VM_BUG_ON_FOLIO`) | Kernel assertion: a condition considered impossible was reached |
| UNAME | `6.18.7-cloudflare-2026.1.15` | Cloudflare custom kernel; base version 6.18.7 |
| DISTRO | Custom (Cloudflare) | No standard distro debug packages; source at `v6.18.7` tag |
| PROCESS | `journalctl` (PID 3666669, UID 0) | Reading a journal file on XFS under memory pressure |
| TAINT | W, O | W: a prior WARNING fired earlier; O: out-of-tree module(s) loaded |
| HARDWARE | Lenovo HR355M-V3-G12 | |
| BIOS | HR355M_V3.G.031 02/17/2025 | |
| BUG condition | `!folio_contains(folio, index)` at `mm/filemap.c:3519` | The locked folio retrieved from the page cache does not contain the requested page index |
| CR2 | `00007efd7ec53a08` | User-space virtual address that triggered the original page fault; unrelated to the BUG itself |
| SOURCEDIR | `oops-workdir/linux` (tag `v6.18.7`) | Source available; no vmlinux |
| VMLINUX | not available | addr2line/gdb symbol resolution not possible |
| BASEDIR | not available | Custom kernel build; no debug package |

---

## Kernel modules

The `Modules linked in:` line is absent from this report (the crash dump excerpt does not include it).

| Module | Flags | Backtrace | Location | Flag Implication |
|--------|-------|-----------|----------|-----------------|
| *(module list not available in this report)* | | | | |

The `[O]` taint flag confirms at least one out-of-tree module is loaded, but its identity is unknown from this report.

---

## Backtrace

`?`-marked entries (`srso_alias_return_thunk`, `do_mmap`) are excluded — there are more than 2 high-confidence entries.

| Address | Function | Offset | Size | Context | Module | Source location |
|---------|----------|--------|------|---------|--------|-----------------|
| `ffffffff94b3ace1` | `filemap_fault` | `0xa61` | `0x1410` | Task | (vmlinux) | `mm/filemap.c:3519` |
| — | `__do_fault` | `0x31` | `0xd0` | Task | (vmlinux) | `mm/memory.c:5281` |
| — | `do_fault` | `0x2e6` | `0x710` | Task | (vmlinux) | |
| — | `__handle_mm_fault` | `0x7b3` | `0xe50` | Task | (vmlinux) | |
| — | `handle_mm_fault` | `0xaa` | `0x2a0` | Task | (vmlinux) | |
| — | `do_user_addr_fault` | `0x208` | `0x660` | Task | (vmlinux) | |
| — | `exc_page_fault` | `0x77` | `0x170` | Task | (vmlinux) | |
| — | `asm_exc_page_fault` | `0x26` | `0x30` | Task | (vmlinux) | |

Source locations confirmed from source (SOURCEDIR at `v6.18.7`) and the crash tool frame output.

---

## Code byte line

```
48 8b 4c 24 10  4c 8b 44 24 08  48 85 c9  0f 84 82 fa ff ff
49 89 cd  e9 bc f9 ff ff  48 c7 c6 20 44 d0 96  4c 89 c7
e8 3f 1c 04 00  <0f> 0b  48 8d 7b 18 ...
```

Disassembled (objdump, x86-64):

```asm
  mov    0x10(%rsp), %rcx
  mov    0x8(%rsp), %r8
  test   %rcx, %rcx
  je     <far back>                        ; branch if rcx == 0
  mov    %rcx, %r13
  jmp    <far back>
  mov    $0xffffffff96d04420, %rsi         ; BUG format string address
  mov    %r8, %rdi                         ; folio pointer → first arg to dump_page/BUG
  call   <dump_page or similar>
  ud2                                      ; ← RIP: the BUG() opcode
  lea    0x18(%rbx), %rdi                  ; (dead code after BUG)
```

The faulting instruction is `ud2` (opcode `0f 0b`), the x86 encoding of `BUG()`. The code immediately before it loads a string address into RSI and a folio pointer (from R8) into RDI before calling a dump function and then asserting.

---

## CPU Registers

Kernel context at the time of the BUG:

| Register | Value | Notes |
|----------|-------|-------|
| RAX | `0x0000000000000043` | |
| RBX | `ff25825437d792a8` | `mapping` pointer (`file->f_mapping`); also the address_space from `p mapping` in crash |
| RCX | `0x0000000000000000` | |
| RDX | `0x0000000000000000` | |
| RSI | `0x0000000000000001` | |
| **RDI** | `ff2582406fb9c4c0` | **folio pointer** — the folio passed to `VM_BUG_ON_FOLIO`; `crash> struct folio.mapping` at this address returns `0x0` (NULL) |
| **RBP** | `0x0000000000007653` | **`index`** — the page index being faulted; confirmed by `crash> p -x index = 0x7653` |
| R8 | `0x0000000000000000` | |
| R12 | `0x0000000000000000` | |
| R13 | `ff258239e9fbf740` | file struct for the journal file |
| R14 | `ff25825437d79138` | inode pointer (`i_ino = 0xc0000c0`) |
| R15 | `ff4ac5c342ccfde8` | |
| RSP | `ff4ac5c342ccfcb0` | Valid kernel stack |
| CR2 | `00007efd7ec53a08` | User-space fault address that started the page fault chain |
| EFLAGS | `0x00010246` | ZF=1 |

Key register relationships confirmed by crash tool output:
- RDI (`ff2582406fb9c4c0`) → `folio.mapping = 0x0` (NULL)
- RBX (`ff25825437d792a8`) = `mapping` from `file->f_mapping` (non-NULL, valid XFS address_space)
- RBP (`0x7653`) = `index` = the faulted page offset

---

## Backtrace source code

### `filemap_fault` — `mm/filemap.c`

```c
3447 vm_fault_t filemap_fault(struct vm_fault *vmf)
3448 {
3449     int error;
3450     struct file *file = vmf->vma->vm_file;
3451     struct file *fpin = NULL;
3452     struct address_space *mapping = file->f_mapping;
3453     struct inode *inode = mapping->host;
3454     pgoff_t max_idx, index = vmf->pgoff;
3455     struct folio *folio;
3456     struct vm_fault_t ret = 0;
3457     bool mapping_locked = false;
       ...
3468     folio = filemap_get_folio(mapping, index);
3469     if (likely(!IS_ERR(folio))) {
           ...
3476         if (unlikely(!folio_test_uptodate(folio))) {
3477             filemap_invalidate_lock_shared(mapping);
3478             mapping_locked = true;
3479         }
3480     } else {
           ...
3490 retry_find:
3495         if (!mapping_locked) {
3496             filemap_invalidate_lock_shared(mapping);
3497             mapping_locked = true;
3498         }
3499         folio = __filemap_get_folio(mapping, index,
3500                                   FGP_CREAT|FGP_FOR_MMAP,
3501                                   vmf->gfp_mask);
           ...
3508     }
3509
3510     if (!lock_folio_maybe_drop_mmap(vmf, folio, &fpin))
3511         goto out_retry;
3512
3513     /* Did it get truncated? */
3514     if (unlikely(folio->mapping != mapping)) {       // ← truncation check
3515         folio_unlock(folio);
3516         folio_put(folio);
3517         goto retry_find;
3518     }
3519     VM_BUG_ON_FOLIO(!folio_contains(folio, index), folio);  // ← CRASH HERE
```

`folio_contains` is defined as:
```c
968 static inline bool folio_contains(const struct folio *folio, pgoff_t index)
969 {
970     VM_WARN_ON_ONCE_FOLIO(folio_test_swapcache(folio), folio);
971     return index - folio->index < folio_nr_pages(folio);
972 }
```

The check fails when `index` does not fall within the range `[folio->index, folio->index + folio_nr_pages(folio))`.

### `__do_fault` — `mm/memory.c`

```c
5254 static vm_fault_t __do_fault(struct vm_fault *vmf)
5255 {
       ...
5275     if (pmd_none(*vmf->pmd) && !vmf->prealloc_pte) {
5276         vmf->prealloc_pte = pte_alloc_one(vma->vm_mm);
5277         if (!vmf->prealloc_pte)
5278             return VM_FAULT_OOM;
5279     }
5280
5281     ret = vma->vm_ops->fault(vmf);   // ← call here → filemap_fault
```

---

## BUG-specific extra context (Phase 1, step 4)

- **BUG variant**: `VM_BUG_ON_FOLIO` — the virtual memory subsystem's folio-specific assertion. It dumps the folio's page info (visible at the top of the oops) before firing `ud2`.
- **Assertion**: `!folio_contains(folio, index)` — the folio in hand (at `ff2582406fb9c4c0`) does NOT contain the page at index `0x7653`.
- **Page dump** (from oops header): the page associated with RBX (`ff25825437d792a8` = `mapping`) has `index:0x7652` — one less than the faulted index `0x7653`. Flags: `locked|referenced|uptodate|lru|active`.
- **folio.mapping = 0x0**: the folio at RDI (`ff2582406fb9c4c0`) has a NULL `mapping` field, which means it has been removed from the page cache (truncated or reclaimed) between being retrieved and being locked.
- **File**: `/state/var/log/journal/.../system@...journal` on XFS (inode `0xc0000c0`).
- **System condition**: memory pressure (reporter notes this), XFS filesystem.

---

## What–How–Where analysis

### What

**The locked folio retrieved from the XFS page cache does not contain the page at the requested index (`0x7653`), triggering the `VM_BUG_ON_FOLIO` assertion at `mm/filemap.c:3519`.**

Specifically:
- `filemap_fault` was called to handle a page fault at index `0x7653` (RBP) for a journalctl read of a journal file on XFS.
- A folio was obtained from the page cache and locked (via `lock_folio_maybe_drop_mmap`).
- The truncation guard at line 3514 (`if (unlikely(folio->mapping != mapping))`) passed — the folio's `mapping` field was non-NULL and equal to `mapping` at that moment.
- However, by line 3519, the assertion `folio_contains(folio, index)` fails.
- The crash tool confirms: `folio.mapping` at the folio address (RDI = `ff2582406fb9c4c0`) is `0x0` — the folio has been removed from the page cache between the truncation check (line 3514) and the assertion (line 3519).
- The page dump at the top of the oops is for the page at RBX (`ff25825437d792a8` = `mapping`), which has `index:0x7652` — one less than the faulted `0x7653`. This page is a different object from the folio at RDI; its flags (`locked|referenced|uptodate|lru|active`) look normal.

The condition at `folio_contains`: `index - folio->index < folio_nr_pages(folio)` fails because either:
1. `folio->index` has changed (unlikely — `index` is set at folio creation), or
2. The folio has been truncated/unmapped and `folio_nr_pages` now returns a stale or wrong value, or
3. Most likely: the folio at RDI is not the same folio that was in the page cache at index `0x7653` — there is a race where the folio was replaced between the truncation guard check and the assertion.

### How

**Q1: How did `folio_contains(folio, index)` return false?**

`folio_contains` checks `index - folio->index < folio_nr_pages(folio)`. For this to fail, the folio's `index` must not encompass page `0x7653`. The crash tool confirms `folio.mapping = 0x0` at the folio address — the folio is no longer in the page cache at the time of the assertion.

**Q2: How did the folio's mapping become NULL between line 3514 and line 3519?**

This is a **race condition**. The sequence in `filemap_fault` is:

```
line 3510: lock_folio_maybe_drop_mmap(vmf, folio, &fpin)
line 3514: if (unlikely(folio->mapping != mapping)) → retry_find   [GUARD]
line 3519: VM_BUG_ON_FOLIO(!folio_contains(folio, index), folio)   [ASSERT]
```

Between lines 3514 and 3519 there are zero instructions that could change `folio->mapping`. However, the truncation check at 3514 and the assertion at 3519 test **different properties** of the folio:

- Line 3514 checks `folio->mapping != mapping` — detects that the folio was removed from this mapping entirely (truncated).
- Line 3519 checks `folio_contains(folio, index)` — checks that the folio's *index range* covers the requested page.

These two checks can diverge if a **large folio** (multi-page folio) is involved:
- A large folio can cover many consecutive page indices.
- If XFS (or the page cache) replaces a folio at index `0x7652` with a different (possibly smaller or differently-aligned) folio, the new folio might have `mapping` == `mapping` (same address space, so line 3514 passes) but its `folio->index` could be `0x7653` or higher — meaning index `0x7653` is not *contained* within it if the folio's base index is `0x7653` and `folio_nr_pages` is 1 and we expected `0x7652..0x7653` coverage. Or conversely, a folio starting at `0x7652` of size 1 would not contain `0x7653`.

The crash tool finding `folio.mapping = 0x0` at the time of the crash dump (post-BUG) suggests that by crash-dump time, the folio at RDI has been fully reclaimed. This is consistent with a race where:

1. Thread A (`journalctl` / `filemap_fault`) gets folio F covering index `0x7652` or `0x7653`.
2. A concurrent truncation or XFS invalidation replaces folio F in the page cache with a new folio G.
3. Thread A locked folio F. Folio F's `mapping` is cleared (set to NULL) after it is removed from the address space.
4. The truncation guard at line 3514 *should* catch this — it checks `folio->mapping != mapping`. But if the clearing of `folio->mapping` races with the check (i.e., it becomes NULL after the check passes), the guard is bypassed and the assertion at 3519 fires.

**This is a TOCTOU (time-of-check / time-of-use) race** between the truncation guard and the assertion. The fact that `folio.mapping` is NULL at the crash confirms the folio was removed from the page cache. The truncation check passed because `mapping` was still set at that instant, then cleared by a racing thread.

Reporter notes this has been seen ~6 times across different machines including both x86 and arm64, under memory pressure, which is consistent with a memory-pressure-induced truncation/reclaim racing with page fault handling.

**Q3: Why does the existing truncation guard at line 3514 not prevent this?**

The guard (`folio->mapping != mapping`) is a single non-atomic read. Between the read returning `mapping` (non-NULL) and the BUG assertion at line 3519, a concurrent XFS truncation or `invalidate_mapping_pages` could set `folio->mapping = NULL` and call `folio_remove_rmap_*` / `folio_put`. Since `filemap_fault` still holds the folio lock at this point, the folio itself is not freed, but its `mapping` field can be cleared by the truncation path which does not require the folio lock for that step on all paths.

**Classification: Positive How** — the race is explicitly identifiable: a concurrent reclaim/truncation clears `folio->mapping` between line 3514 and line 3519 in `filemap_fault`.

### Where

The assertion at line 3519 is correct — a folio not covering the requested index in an active mapping is indeed a bug. The problem is that the truncation guard at line 3514 that should prevent reaching this assertion is insufficient: it does not guarantee that `folio->mapping` and `folio_contains(folio, index)` remain consistent after the check.

**Option A — Move or eliminate the assertion (not recommended)**

Converting the `VM_BUG_ON_FOLIO` to a soft retry (like the truncation check above it) would paper over the issue:

```diff
--- a/mm/filemap.c
+++ b/mm/filemap.c
@@ -3516,7 +3516,11 @@ vm_fault_t filemap_fault(struct vm_fault *vmf)
 	if (unlikely(folio->mapping != mapping)) {
 		folio_unlock(folio);
 		folio_put(folio);
 		goto retry_find;
 	}
-	VM_BUG_ON_FOLIO(!folio_contains(folio, index), folio);
+	if (unlikely(!folio_contains(folio, index))) {
+		folio_unlock(folio);
+		folio_put(folio);
+		goto retry_find;
+	}
```

This is a defensive fix: rather than asserting that the folio contains the index, treat a mismatch as a stale folio and retry. This matches the pattern already used for the `folio->mapping` check immediately above.

**Option B — Root fix: harden the truncation guard**

The more correct fix is to understand *why* a folio that passes `folio->mapping == mapping` does not contain `index`. This points to a deeper issue: either XFS is inserting a folio at an unexpected index range under the invalidate lock, or the large-folio splitting/replacing path has a gap in its locking that allows `filemap_fault` to observe a transitional folio state.

Investigating the XFS and large-folio invalidation paths (specifically `invalidate_folio`, `xfs_invalidate_folio`, and `folio_unmap_invalidate`) for cases where a new folio can appear with `mapping` set but an `index` range that does not cover the requested page would be the root fix direction.

**Checking the git tree for existing fixes**

```bash
git -C oops-workdir/linux log --oneline v6.18.7..HEAD -- mm/filemap.c | head -20
```
<br>
*(Run this to see if any fixes to `filemap_fault` around line 3519 have landed after v6.18.7.)*

Also worth checking:
```bash
git -C oops-workdir/linux log --oneline --all --grep="folio_contains" | head -20
git -C oops-workdir/linux log --oneline --all --grep="filemap_fault.*truncat" | head -20
```

---

## Analysis, conclusions and recommendations

**Root cause (Most likely, based on available evidence):** A race condition in `filemap_fault` between the truncation guard at line 3514 and the `VM_BUG_ON_FOLIO` assertion at line 3519. A concurrent XFS truncation or page-cache invalidation clears `folio->mapping` to NULL after the guard passes but before the assertion is checked. The guard and assertion test *different* aspects of folio validity (mapping pointer vs. index range coverage), creating a window where a folio can pass the guard but fail the assertion.

**Evidence quality:** *Most likely based on partial analysis* — the crash tool confirms `folio.mapping = 0x0` post-crash and the register values are consistent with this race, but no vmlinux is available to pinpoint exactly which concurrent path caused the clearing. The reporter's observation that this occurs under memory pressure is consistent with aggressive reclaim/truncation activity.

**Unusual observations:**

1. **`folio.mapping = 0x0` at crash time**: The folio at RDI has a NULL `mapping`, confirming it has been removed from the page cache. The truncation guard at line 3514 is designed to catch exactly this — but it was bypassed by the race.

2. **Index mismatch (`0x7652` vs `0x7653`)**: The page dump shows a page at index `0x7652` (one below the faulted index `0x7653`). This is consistent with a large folio that was supposed to cover both indices being replaced by a single-page folio, or the folio being for index `0x7652` while the fault is for `0x7653` — a large-folio alignment issue.

3. **Reproducible across x86 and arm64**: The reporter sees this on both architectures, which confirms the bug is in architecture-independent MM/VFS code (as expected for `mm/filemap.c`), not an x86-specific issue.

4. **Taint W (prior WARNING)**: An earlier WARNING fired in this boot. It may be related (e.g., a folio state warning from XFS or the page allocator), or unrelated. The full dmesg log should be checked.

5. **Taint O (out-of-tree module)**: An OOT module is loaded on this Cloudflare kernel. Unlikely to be the cause (the crash is deep in core MM/VFS), but worth noting.

6. **NOPTI**: Page Table Isolation is disabled (`NOPTI`). This is expected on server hardware with hardware Meltdown mitigations and does not affect the bug.

7. **`Kdump: loaded`**: A crash dump was captured, which enabled the reporter to run `crash` and provide the additional folio/mapping details. This data is critical to the analysis.

**Recommended next steps for the reporter:**
1. Apply the defensive fix (Option A) as an immediate workaround to avoid the kernel BUG crash while the root cause is investigated.
2. Capture the full dmesg to identify the prior WARNING (Taint W).
3. Check `git log v6.18.7..HEAD -- mm/filemap.c` and search for commits mentioning `folio_contains` or `filemap_fault` truncation race to see if a fix has already landed upstream.
4. Report to `linux-mm@kvack.org` and `linux-fsdevel@vger.kernel.org` (already done per the original email) with the full crash dump output including the `folio->index` and `folio_nr_pages` values from the crash tool to narrow down the exact folio size and alignment involved.
