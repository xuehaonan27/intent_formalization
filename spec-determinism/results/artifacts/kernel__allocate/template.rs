// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=True
spec fn det_allocate_equal(r1: Result<*mut u8, AllocError>, r2: Result<*mut u8, AllocError>, post1_self_: KheapView, post2_self_: KheapView) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> true))
    && ((post1_self_.slabs == post2_self_.slabs))
}

proof fn det_allocate(pre_self_: Kheap, layout: Layout, post1_self_: Kheap, r1: Result<*mut u8, AllocError>, post2_self_: Kheap, r2: Result<*mut u8, AllocError>)
    requires (pre_self_.inv()),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(ptr) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-3b: address was free in the correct slab
                    &&& opt_idx.is_some()
                    &&& pre_self_@.slabs[opt_idx.unwrap()].free_addrs.contains(ptr as usize)
                    // FN-3c: pointer is block-aligned
                    &&& ptr as usize % pre_self_@.slabs[opt_idx.unwrap()].block_size == 0
                    // FN-3d: exact state transition
                    &&& post1_self_@ == pre_self_@.spec_allocate(opt_idx.unwrap(), ptr as usize)
                }
                Err(_) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-3g: state preserved on error
                    &&& post1_self_@ == pre_self_@
                    // FN-3f: error iff size unsupported or slab exhausted
                    &&& (opt_idx.is_none()
                        || pre_self_@.slabs[opt_idx.unwrap()].free_addrs
                            == Set::<usize>::empty())
                }
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(ptr) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-3b: address was free in the correct slab
                    &&& opt_idx.is_some()
                    &&& pre_self_@.slabs[opt_idx.unwrap()].free_addrs.contains(ptr as usize)
                    // FN-3c: pointer is block-aligned
                    &&& ptr as usize % pre_self_@.slabs[opt_idx.unwrap()].block_size == 0
                    // FN-3d: exact state transition
                    &&& post2_self_@ == pre_self_@.spec_allocate(opt_idx.unwrap(), ptr as usize)
                }
                Err(_) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-3g: state preserved on error
                    &&& post2_self_@ == pre_self_@
                    // FN-3f: error iff size unsupported or slab exhausted
                    &&& (opt_idx.is_none()
                        || pre_self_@.slabs[opt_idx.unwrap()].free_addrs
                            == Set::<usize>::empty())
                }
            })
        }) ==> det_allocate_equal(r1, r2, post1_self_@, post2_self_@),
{
}