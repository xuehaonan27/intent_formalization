// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_deallocate_equal(r1: Result<(), AllocError>, r2: Result<(), AllocError>, post1_self_: KheapView, post2_self_: KheapView) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (r1->Ok_0 == r2->Ok_0)))
    && ((post1_self_.slabs == post2_self_.slabs))
}

proof fn det_deallocate(pre_self_: Kheap, ptr: *mut u8, layout: Layout, post1_self_: Kheap, r1: Result<(), AllocError>, post2_self_: Kheap, r2: Result<(), AllocError>)
    requires (pre_self_.inv()),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(()) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-4b: pointer was allocated in the correct slab
                    &&& opt_idx.is_some()
                    &&& pre_self_@.slabs[opt_idx.unwrap()].allocated_addrs.contains(ptr as usize)
                    // FN-4c: exact state transition
                    &&& post1_self_@ == pre_self_@.spec_deallocate(opt_idx.unwrap(), ptr as usize)
                }
                Err(_) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-4f: state preserved on error
                    &&& post1_self_@ == pre_self_@
                    // FN-4e: error iff size unsupported or ptr not allocated
                    &&& (opt_idx.is_none()
                        || !pre_self_@.slabs[opt_idx.unwrap()].allocated_addrs
                            .contains(ptr as usize))
                }
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(()) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-4b: pointer was allocated in the correct slab
                    &&& opt_idx.is_some()
                    &&& pre_self_@.slabs[opt_idx.unwrap()].allocated_addrs.contains(ptr as usize)
                    // FN-4c: exact state transition
                    &&& post2_self_@ == pre_self_@.spec_deallocate(opt_idx.unwrap(), ptr as usize)
                }
                Err(_) => {
                    let opt_idx = spec_slab_for_size(spec_layout_size(layout) as int);
                    // FN-4f: state preserved on error
                    &&& post2_self_@ == pre_self_@
                    // FN-4e: error iff size unsupported or ptr not allocated
                    &&& (opt_idx.is_none()
                        || !pre_self_@.slabs[opt_idx.unwrap()].allocated_addrs
                            .contains(ptr as usize))
                }
            })
        }) ==> det_deallocate_equal(r1, r2, post1_self_@, post2_self_@),
{
}