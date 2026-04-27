// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False [custom_body in use]
pub open spec fn det_alloc_equal(r1: Result<usize, Error>, r2: Result<usize, Error>, post1_self_: BitmapView, post2_self_: BitmapView) -> bool {
    ((r1 is Ok) == (r2 is Ok)) && (post1_self_@.num_bits == post2_self_@.num_bits) && (post1_self_@.set_bits.len() == post2_self_@.set_bits.len())
}

proof fn det_alloc(pre_self_: Bitmap, post1_self_: Bitmap, r1: Result<usize, Error>, post2_self_: Bitmap, r2: Result<usize, Error>)
    requires (pre_self_.inv()),
    ensures
        ({
            &&& (post1_self_.inv())
            &&& (match r1 {
                Ok(index) => {
                    &&& 0 <= index < post1_self_@.num_bits
                    &&& post1_self_@.num_bits == pre_self_@.num_bits
                    &&& !pre_self_@.is_bit_set(index as int)
                    &&& post1_self_@.is_bit_set(index as int)
                    &&& forall|i: int|
                        0 <= i < post1_self_@.num_bits && i != index ==> post1_self_@.is_bit_set(i) == pre_self_@.is_bit_set(i)
                    &&& post1_self_@.set_bits == pre_self_@.set_bits.insert(index as int)
                    &&& post1_self_@.usage() == pre_self_@.usage() + 1
                },
                Err(_) => {
                    &&& pre_self_@.is_full()
                    &&& post1_self_@ == pre_self_@
                },
            })
            &&& (post2_self_.inv())
            &&& (match r2 {
                Ok(index) => {
                    &&& 0 <= index < post2_self_@.num_bits
                    &&& post2_self_@.num_bits == pre_self_@.num_bits
                    &&& !pre_self_@.is_bit_set(index as int)
                    &&& post2_self_@.is_bit_set(index as int)
                    &&& forall|i: int|
                        0 <= i < post2_self_@.num_bits && i != index ==> post2_self_@.is_bit_set(i) == pre_self_@.is_bit_set(i)
                    &&& post2_self_@.set_bits == pre_self_@.set_bits.insert(index as int)
                    &&& post2_self_@.usage() == pre_self_@.usage() + 1
                },
                Err(_) => {
                    &&& pre_self_@.is_full()
                    &&& post2_self_@ == pre_self_@
                },
            })
        }) ==> det_alloc_equal(r1, r2, post1_self_@, post2_self_@),
{
}