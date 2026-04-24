// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_allocate_chk_equal(r1: Result<*mut u8, Error>, r2: Result<*mut u8, Error>, post1_self_: SlabView, post2_self_: SlabView) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (true /* raw pointer: opaque by default */)))
    && ((post1_self_.block_size == post2_self_.block_size) && (post1_self_.start_addr == post2_self_.start_addr) && (post1_self_.end_addr == post2_self_.end_addr) && (post1_self_.allocated_addrs == post2_self_.allocated_addrs) && (post1_self_.free_addrs == post2_self_.free_addrs))
}

proof fn det_allocate_chk(pre_self_: Slab, post1_self_: Slab, r1: Result<*mut u8, Error>, post2_self_: Slab, r2: Result<*mut u8, Error>)
    requires (pre_self_.inv()),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(ptr) => {
                    let addr = ptr as usize;
                    &&& pre_self_@.free_addrs.contains(addr)
                    &&& addr % post1_self_@.block_size == 0
                    &&& post1_self_@ == SlabView {
                        allocated_addrs: pre_self_@.allocated_addrs.insert(addr),
                        free_addrs: pre_self_@.free_addrs.remove(addr),
                        ..pre_self_@
                    }
                },
                Err(_) => {
                    &&& pre_self_@.free_addrs == Set::<usize>::empty()
                    &&& post1_self_@ == pre_self_@
                },
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(ptr) => {
                    let addr = ptr as usize;
                    &&& pre_self_@.free_addrs.contains(addr)
                    &&& addr % post2_self_@.block_size == 0
                    &&& post2_self_@ == SlabView {
                        allocated_addrs: pre_self_@.allocated_addrs.insert(addr),
                        free_addrs: pre_self_@.free_addrs.remove(addr),
                        ..pre_self_@
                    }
                },
                Err(_) => {
                    &&& pre_self_@.free_addrs == Set::<usize>::empty()
                    &&& post2_self_@ == pre_self_@
                },
            })
        }) ==> det_allocate_chk_equal(r1, r2, post1_self_@, post2_self_@),
{
}