// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_deallocate_equal(r1: Result<(), AllocError>, r2: Result<(), AllocError>, post1_self_: KheapView, post2_self_: KheapView) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (r1->Ok_0 == r2->Ok_0)))
    && ((post1_self_.allocations == post2_self_.allocations))
}

proof fn det_deallocate(pre_self_: Kheap, ptr: *mut u8, layout: Layout, post1_self_: Kheap, r1: Result<(), AllocError>, post2_self_: Kheap, r2: Result<(), AllocError>)
    requires (pre_self_.inv()), (spec_layout_size(layout) > 0),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(()) => {
                    &&& pre_self_@.allocations.dom().contains(ptr as int)
                    &&& post1_self_@ =~= pre_self_@.spec_deallocate(ptr as int)
                },
                Err(_) => post1_self_@ == pre_self_@,
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(()) => {
                    &&& pre_self_@.allocations.dom().contains(ptr as int)
                    &&& post2_self_@ =~= pre_self_@.spec_deallocate(ptr as int)
                },
                Err(_) => post2_self_@ == pre_self_@,
            })
        }) ==> det_deallocate_equal(r1, r2, post1_self_@, post2_self_@),
{
}