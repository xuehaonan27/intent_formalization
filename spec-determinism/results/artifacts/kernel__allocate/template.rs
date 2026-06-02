// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_allocate_equal(r1: Result<*mut u8, AllocError>, r2: Result<*mut u8, AllocError>, post1_self_: Kheap, post2_self_: Kheap) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (true /* raw pointer: opaque by default */)))
    && (((post1_self_.slab_8_bytes)@ == (post2_self_.slab_8_bytes)@) && ((post1_self_.slab_16_bytes)@ == (post2_self_.slab_16_bytes)@) && ((post1_self_.slab_32_bytes)@ == (post2_self_.slab_32_bytes)@) && ((post1_self_.slab_64_bytes)@ == (post2_self_.slab_64_bytes)@) && ((post1_self_.slab_128_bytes)@ == (post2_self_.slab_128_bytes)@) && ((post1_self_.slab_256_bytes)@ == (post2_self_.slab_256_bytes)@) && ((post1_self_.slab_512_bytes)@ == (post2_self_.slab_512_bytes)@) && ((post1_self_.alloc_map)@ =~= (post2_self_.alloc_map)@))
}

proof fn det_allocate(pre_self_: Kheap, layout: Layout, post1_self_: Kheap, r1: Result<*mut u8, AllocError>, post2_self_: Kheap, r2: Result<*mut u8, AllocError>)
    requires (pre_self_.inv()),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(ptr) => {
                    &&& ptr as usize != 0
                    &&& !pre_self_@.allocations.dom().contains(ptr as int)
                    &&& post1_self_@.allocations[ptr as int] == spec_layout_size(layout) as nat
                    &&& post1_self_@ =~= pre_self_@.spec_allocate(
                        ptr as int,
                        spec_layout_size(layout) as nat,
                    )
                    &&& (ptr as int) % (spec_layout_align(layout) as int) == 0
                },
                Err(_) => {
                    &&& post1_self_@ == pre_self_@
                    &&& !(pre_self_@.allocations =~= Map::<int, nat>::empty())
                        || spec_layout_align(layout) > spec_layout_size(layout)
                        || spec_layout_size(layout) > 512
                },
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(ptr) => {
                    &&& ptr as usize != 0
                    &&& !pre_self_@.allocations.dom().contains(ptr as int)
                    &&& post2_self_@.allocations[ptr as int] == spec_layout_size(layout) as nat
                    &&& post2_self_@ =~= pre_self_@.spec_allocate(
                        ptr as int,
                        spec_layout_size(layout) as nat,
                    )
                    &&& (ptr as int) % (spec_layout_align(layout) as int) == 0
                },
                Err(_) => {
                    &&& post2_self_@ == pre_self_@
                    &&& !(pre_self_@.allocations =~= Map::<int, nat>::empty())
                        || spec_layout_align(layout) > spec_layout_size(layout)
                        || spec_layout_size(layout) > 512
                },
            })
        }) ==> det_allocate_equal(r1, r2, post1_self_, post2_self_),
{
}