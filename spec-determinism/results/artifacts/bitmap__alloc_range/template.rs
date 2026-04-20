// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=True
spec fn det_alloc_range_chk_equal(r1: Result<usize, Error>, r2: Result<usize, Error>, post1_self_: BitmapView, post2_self_: BitmapView) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> true))
    && ((post1_self_.num_bits == post2_self_.num_bits) && (post1_self_.set_bits == post2_self_.set_bits))
}

proof fn det_alloc_range_chk(pre_self_: Bitmap, size: usize, post1_self_: Bitmap, r1: Result<usize, Error>, post2_self_: Bitmap, r2: Result<usize, Error>)
    requires (pre_self_.inv()), (size > 0), (size <= pre_self_@.num_bits),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(start) => {
                    &&& 0 <= start < post1_self_@.num_bits
                    &&& 0 < size <= post1_self_@.num_bits
                    &&& start + (size as int) <= post1_self_@.num_bits
                    &&& post1_self_@.num_bits == pre_self_@.num_bits
                    &&& post1_self_@.all_bits_set_in_range(start as int, start + (size as int))
                    &&& pre_self_@.all_bits_unset_in_range(
                        start as int,
                        start + (size as int),
                    )
                    // Frame: only the allocated range changed.
                    &&& forall|i: int|
                        0 <= i < post1_self_@.num_bits && (i < start || i >= start + (size as int))
                            ==> post1_self_@.is_bit_set(i) == pre_self_@.is_bit_set(
                            i,
                        )
                    // Set-based frame.
                    &&& post1_self_@.set_bits == pre_self_@.set_bits.union(
                        BitmapView::range_set(start as int, start + (size as int)),
                    )
                    &&& post1_self_@.usage() == pre_self_@.usage() + (size as int)
                },
                Err(_) => {
                    &&& !pre_self_@.exists_contiguous_free_range(size as int)
                    &&& post1_self_@ == pre_self_@
                },
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(start) => {
                    &&& 0 <= start < post2_self_@.num_bits
                    &&& 0 < size <= post2_self_@.num_bits
                    &&& start + (size as int) <= post2_self_@.num_bits
                    &&& post2_self_@.num_bits == pre_self_@.num_bits
                    &&& post2_self_@.all_bits_set_in_range(start as int, start + (size as int))
                    &&& pre_self_@.all_bits_unset_in_range(
                        start as int,
                        start + (size as int),
                    )
                    // Frame: only the allocated range changed.
                    &&& forall|i: int|
                        0 <= i < post2_self_@.num_bits && (i < start || i >= start + (size as int))
                            ==> post2_self_@.is_bit_set(i) == pre_self_@.is_bit_set(
                            i,
                        )
                    // Set-based frame.
                    &&& post2_self_@.set_bits == pre_self_@.set_bits.union(
                        BitmapView::range_set(start as int, start + (size as int)),
                    )
                    &&& post2_self_@.usage() == pre_self_@.usage() + (size as int)
                },
                Err(_) => {
                    &&& !pre_self_@.exists_contiguous_free_range(size as int)
                    &&& post2_self_@ == pre_self_@
                },
            })
        }) ==> det_alloc_range_chk_equal(r1, r2, post1_self_@, post2_self_@),
{
}