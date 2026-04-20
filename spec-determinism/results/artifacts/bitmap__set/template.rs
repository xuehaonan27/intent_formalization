// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_set_equal(r1: Result<(), Error>, r2: Result<(), Error>, post1_self_: BitmapView, post2_self_: BitmapView) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (r1->Ok_0 == r2->Ok_0)))
    && ((post1_self_.num_bits == post2_self_.num_bits) && (post1_self_.set_bits == post2_self_.set_bits))
}

proof fn det_set(pre_self_: Bitmap, index: usize, post1_self_: Bitmap, r1: Result<(), Error>, post2_self_: Bitmap, r2: Result<(), Error>)
    requires (pre_self_.inv()),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(()) => {
                    &&& index < post1_self_@.num_bits
                    &&& post1_self_@.is_bit_set(index as int)
                    &&& !pre_self_@.is_bit_set(index as int)
                    &&& post1_self_@.num_bits == pre_self_@.num_bits
                    // Frame.
                    &&& forall|i: int|
                        0 <= i < post1_self_@.num_bits && i != (index as int) ==> post1_self_@.is_bit_set(i)
                            == pre_self_@.is_bit_set(
                            i,
                        )
                    // Set-based frame.
                    &&& post1_self_@.set_bits == pre_self_@.set_bits.insert(index as int)
                    &&& post1_self_@.usage() == pre_self_@.usage() + 1
                },
                Err(_) => {
                    &&& index >= pre_self_@.num_bits || pre_self_@.is_bit_set(index as int)
                    &&& post1_self_ == pre_self_
                },
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(()) => {
                    &&& index < post2_self_@.num_bits
                    &&& post2_self_@.is_bit_set(index as int)
                    &&& !pre_self_@.is_bit_set(index as int)
                    &&& post2_self_@.num_bits == pre_self_@.num_bits
                    // Frame.
                    &&& forall|i: int|
                        0 <= i < post2_self_@.num_bits && i != (index as int) ==> post2_self_@.is_bit_set(i)
                            == pre_self_@.is_bit_set(
                            i,
                        )
                    // Set-based frame.
                    &&& post2_self_@.set_bits == pre_self_@.set_bits.insert(index as int)
                    &&& post2_self_@.usage() == pre_self_@.usage() + 1
                },
                Err(_) => {
                    &&& index >= pre_self_@.num_bits || pre_self_@.is_bit_set(index as int)
                    &&& post2_self_ == pre_self_
                },
            })
        }) ==> det_set_equal(r1, r2, post1_self_@, post2_self_@),
{
}