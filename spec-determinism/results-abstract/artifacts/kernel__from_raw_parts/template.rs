// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_from_raw_parts_equal(r1: Result<Kheap, Error>, r2: Result<Kheap, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)))
}

proof fn det_from_raw_parts(addr: usize, size: usize, r1: Result<Kheap, Error>, r2: Result<Kheap, Error>)
    requires (addr + size <= usize::MAX), (size <= isize::MAX as usize), (addr > 0),
    ensures
        ({
            &&& (match r1 {
                Ok(kheap) => {
                    &&& kheap.inv()
                    &&& kheap@ =~= KheapView::spec_new()
                },
                Err(e) => e.code == ErrorCode::InvalidArgument,
            })
            &&& (match r2 {
                Ok(kheap) => {
                    &&& kheap.inv()
                    &&& kheap@ =~= KheapView::spec_new()
                },
                Err(e) => e.code == ErrorCode::InvalidArgument,
            })
        }) ==> det_from_raw_parts_equal(r1, r2),
{
}