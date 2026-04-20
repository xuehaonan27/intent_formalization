// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_number_of_bits_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_number_of_bits(self_: Bitmap, r1: usize, r2: usize)
    requires (self_.inv()),
    ensures
        ({
            &&& (r1 as int == self_@.num_bits)
            &&& (r1 > 0)
            &&& (r1 < u32::MAX as usize)
            &&& (r2 as int == self_@.num_bits)
            &&& (r2 > 0)
            &&& (r2 < u32::MAX as usize)
        }) ==> det_number_of_bits_equal(r1, r2),
{
}