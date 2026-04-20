// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_deallocate_equal(r1: Result<(), Error>, r2: Result<(), Error>, post1_self_: SlabView, post2_self_: SlabView) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (r1->Ok_0 == r2->Ok_0)))
    && ((post1_self_.block_size == post2_self_.block_size) && (post1_self_.start_addr == post2_self_.start_addr) && (post1_self_.end_addr == post2_self_.end_addr) && (post1_self_.allocated_addrs == post2_self_.allocated_addrs) && (post1_self_.free_addrs == post2_self_.free_addrs))
}

proof fn det_deallocate(pre_self_: Slab, ptr: *const u8, post1_self_: Slab, r1: Result<(), Error>, post2_self_: Slab, r2: Result<(), Error>)
    requires (pre_self_.inv()),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(()) => {
                    &&& pre_self_@.allocated_addrs.contains(ptr as usize)
                    &&& post1_self_@ == (SlabView {
                        allocated_addrs: pre_self_@.allocated_addrs.remove(ptr as usize),
                        free_addrs: pre_self_@.free_addrs.insert(ptr as usize),
                        ..pre_self_@
                    })
                },
                Err(_) => {
                    &&& !pre_self_@.allocated_addrs.contains(ptr as usize)
                    &&& post1_self_@ == pre_self_@
                },
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(()) => {
                    &&& pre_self_@.allocated_addrs.contains(ptr as usize)
                    &&& post2_self_@ == (SlabView {
                        allocated_addrs: pre_self_@.allocated_addrs.remove(ptr as usize),
                        free_addrs: pre_self_@.free_addrs.insert(ptr as usize),
                        ..pre_self_@
                    })
                },
                Err(_) => {
                    &&& !pre_self_@.allocated_addrs.contains(ptr as usize)
                    &&& post2_self_@ == pre_self_@
                },
            })
        }) ==> det_deallocate_equal(r1, r2, post1_self_@, post2_self_@),
{
}