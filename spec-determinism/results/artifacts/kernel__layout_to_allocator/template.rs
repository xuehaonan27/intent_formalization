// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_layout_to_allocator_equal(r1: Result<SlabSize, AllocError>, r2: Result<SlabSize, AllocError>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0 as int) == (r2->Ok_0 as int))))
}

proof fn det_layout_to_allocator(layout: Layout, r1: Result<SlabSize, AllocError>, r2: Result<SlabSize, AllocError>)
    ensures
        ({
            &&& (match r1 {
                Ok(ss) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-1a: size is supported
                    &&& opt_idx.is_some()
                    // FN-1b: the matching slab tier is large enough
                    &&& block_sizes()[opt_idx.unwrap()] >= spec_layout_size(layout) as int
                    // FN-1c: returned SlabSize corresponds to the correct index
                    &&& opt_idx.unwrap() == spec_slab_size_to_index(ss)
                    // FN-1c strengthened: tightest fit — all smaller tiers are too small
                    &&& forall|j: int| 0 <= j < opt_idx.unwrap() ==>
                        block_sizes()[j] < spec_layout_size(layout) as int
                }
                // FN-1d: error iff size is unsupported
                Err(_) => spec_slab_for_size(spec_layout_size(layout) as int).is_none(),
            })
            &&& (match r2 {
                Ok(ss) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-1a: size is supported
                    &&& opt_idx.is_some()
                    // FN-1b: the matching slab tier is large enough
                    &&& block_sizes()[opt_idx.unwrap()] >= spec_layout_size(layout) as int
                    // FN-1c: returned SlabSize corresponds to the correct index
                    &&& opt_idx.unwrap() == spec_slab_size_to_index(ss)
                    // FN-1c strengthened: tightest fit — all smaller tiers are too small
                    &&& forall|j: int| 0 <= j < opt_idx.unwrap() ==>
                        block_sizes()[j] < spec_layout_size(layout) as int
                }
                // FN-1d: error iff size is unsupported
                Err(_) => spec_slab_for_size(spec_layout_size(layout) as int).is_none(),
            })
        }) ==> det_layout_to_allocator_equal(r1, r2),
{
}