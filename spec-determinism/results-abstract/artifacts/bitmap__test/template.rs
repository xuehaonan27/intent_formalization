// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_test_equal(r1: Result<bool, Error>, r2: Result<bool, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> (r1->Ok_0 == r2->Ok_0)))
}

proof fn det_test(self_: Bitmap, index: usize, r1: Result<bool, Error>, r2: Result<bool, Error>)
    requires (self_.inv()),
    ensures
        ({
            &&& (match r1 {
                Ok(b) => {
                    &&& index < self_@.num_bits
                    &&& b == self_@.is_bit_set(index as int)
                },
                Err(_) => index >= self_@.num_bits,
            })
            &&& (match r2 {
                Ok(b) => {
                    &&& index < self_@.num_bits
                    &&& b == self_@.is_bit_set(index as int)
                },
                Err(_) => index >= self_@.num_bits,
            })
        }) ==> det_test_equal(r1, r2),
{
}