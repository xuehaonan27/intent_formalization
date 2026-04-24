// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_layout_to_allocator_equal(r1: Result<SlabSize, AllocError>, r2: Result<SlabSize, AllocError>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0 as int) == (r2->Ok_0 as int))))
}

proof fn det_layout_to_allocator(layout: Layout, r1: Result<SlabSize, AllocError>, r2: Result<SlabSize, AllocError>)
    ensures
        ({
            &&& (match r1 {
                Ok(slab_size) => {
                    &&& (slab_size as usize == 8
                        || slab_size as usize == 16
                        || slab_size as usize == 32
                        || slab_size as usize == 64
                        || slab_size as usize == 128
                        || slab_size as usize == 256
                        || slab_size as usize == 512)
                    &&& slab_size as usize >= spec_layout_size(layout)
                    &&& (slab_size as usize == 16 ==> spec_layout_size(layout) > 8)
                    &&& (slab_size as usize == 32 ==> spec_layout_size(layout) > 16)
                    &&& (slab_size as usize == 64 ==> spec_layout_size(layout) > 32)
                    &&& (slab_size as usize == 128 ==> spec_layout_size(layout) > 64)
                    &&& (slab_size as usize == 256 ==> spec_layout_size(layout) > 128)
                    &&& (slab_size as usize == 512 ==> spec_layout_size(layout) > 256)
                },
                Err(_) => {
                    spec_layout_size(layout) == 0
                        || spec_layout_size(layout) > 512
                },
            })
            &&& (match r2 {
                Ok(slab_size) => {
                    &&& (slab_size as usize == 8
                        || slab_size as usize == 16
                        || slab_size as usize == 32
                        || slab_size as usize == 64
                        || slab_size as usize == 128
                        || slab_size as usize == 256
                        || slab_size as usize == 512)
                    &&& slab_size as usize >= spec_layout_size(layout)
                    &&& (slab_size as usize == 16 ==> spec_layout_size(layout) > 8)
                    &&& (slab_size as usize == 32 ==> spec_layout_size(layout) > 16)
                    &&& (slab_size as usize == 64 ==> spec_layout_size(layout) > 32)
                    &&& (slab_size as usize == 128 ==> spec_layout_size(layout) > 64)
                    &&& (slab_size as usize == 256 ==> spec_layout_size(layout) > 128)
                    &&& (slab_size as usize == 512 ==> spec_layout_size(layout) > 256)
                },
                Err(_) => {
                    spec_layout_size(layout) == 0
                        || spec_layout_size(layout) > 512
                },
            })
        }) ==> det_layout_to_allocator_equal(r1, r2),
{
}