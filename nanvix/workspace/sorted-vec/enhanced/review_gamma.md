# Gamma Review — Sorted-Vec

## Confirmed: #1, #2, #7, #8, #10, #11, #12
## Rejected: #4 (counting argument — forced to be sv_eq to value, duplicate of #1)
## Downgraded (correct): #5, #9
## Withdrawn (correct): #3
## Duplicate: #6 (same as #1)

## NEW GAP FOUND
**Remove return value not pinned to old sequence.**
remove ensures sv_eq(result.unwrap(), *value) but NOT old(self)@.contains(result.unwrap()).
The returned value could be any element sv_eq to value, not necessarily one that was in the sequence.
Compare with insert which DOES have old(self)@.contains(result.unwrap()).

## Key Insight from #4 rejection
With length constraint (N+1) + frame preserving N structural elements + strict sorting,
the extra slot is forced to be sv_eq to value. No truly spurious element can appear.
The only gap is that it needn't be structurally == value (which is #1).
